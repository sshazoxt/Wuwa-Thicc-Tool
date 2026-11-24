param([ValidateSet('Launch','Check','Repair','Change','Rebuild','Info','Clear')][string]$Mode='Launch')
$ErrorActionPreference='Stop'
$Root=$PSScriptRoot
Set-Location -LiteralPath $Root
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$Cache=Join-Path $Root 'thicc_environment_cache.json'
$Venv=Join-Path $Root '.venv'
$Py=Join-Path $Venv 'Scripts\python.exe'
$Pyw=Join-Path $Venv 'Scripts\pythonw.exe'
$Req=Join-Path $Root 'requirements.txt'
$env:QT_API='pyside6'
$env:PYTHONUTF8='1'
$env:PIP_DISABLE_PIP_VERSION_CHECK='1'
$env:PIP_NO_INPUT='1'
function Log([string]$s) { Write-Host $s }
function Ask([string]$s) { [System.Windows.Forms.MessageBox]::Show($s,'Thicc Tool 007',[System.Windows.Forms.MessageBoxButtons]::YesNo,[System.Windows.Forms.MessageBoxIcon]::Question) -eq 'Yes' }
function Hash([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }
function Finger([string]$p) { $f=Get-Item -LiteralPath $p; "$($f.FullName)|$($f.Length)|$($f.LastWriteTimeUtc.Ticks)" }
function ReadCache { try { Get-Content -LiteralPath $Cache -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $null } }
function SaveCache($data) {
    $temp=$Cache+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
    try {
        [IO.File]::WriteAllText($temp,($data | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
        if ([IO.File]::Exists($Cache)) { [IO.File]::Replace($temp,$Cache,$null) } else { [IO.File]::Move($temp,$Cache) }
    } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force } }
}
function SetupHash { (Hash (Join-Path $Root 'bootstrap.ps1'))+':'+(Hash (Join-Path $Root 'environment_check.py')) }
function CacheValid($c) {
    try {
        if ($null -eq $c -or $c.schema -ne 1 -or $c.status -ne 'ready') { return $false }
        if ($c.root -ne $Root -or $c.setup_hash -ne (SetupHash) -or $c.requirements_hash -ne (Hash $Req)) { return $false }
        if (!(Test-Path -LiteralPath $Pyw -PathType Leaf) -or !(Test-Path -LiteralPath (Join-Path $Venv 'Lib\site-packages') -PathType Container)) { return $false }
        if (!$c.module_files) { return $false }
        foreach ($name in @('numpy','scipy','PySide6','pyvista','pyvistaqt','vtk')) {
            $entry=$c.module_files.PSObject.Properties[$name]
            if (!$entry -or !(Test-Path -LiteralPath $entry.Value -PathType Leaf)) { return $false }
        }
        return ($c.base_fingerprint -eq (Finger $c.base_python) -and $c.python_fingerprint -eq (Finger $Py) -and $c.pythonw_fingerprint -eq (Finger $Pyw) -and $c.venv_config_hash -eq (Hash (Join-Path $Venv 'pyvenv.cfg')))
    } catch { return $false }
}
function Probe([string]$path) {
    try {
        if (!$path -or $path -match '\\WindowsApps\\python(?:3)?\.exe$' -or !(Test-Path -LiteralPath $path -PathType Leaf)) { return }
        $code='import json,sys,struct,platform; print(json.dumps(dict(path=sys.executable,base=getattr(sys,''_base_executable'',sys.executable),version=platform.python_version(),major=sys.version_info.major,minor=sys.version_info.minor,bits=struct.calcsize(''P'')*8,machine=platform.machine(),impl=platform.python_implementation())))'
        $s=& $path -I -c $code 2>$null
        if ($LASTEXITCODE -ne 0) { return }
        $x=($s | Select-Object -Last 1) | ConvertFrom-Json
        if ($x.impl -eq 'CPython' -and $x.major -eq 3 -and $x.minor -ge 10 -and $x.minor -le 12 -and $x.bits -eq 64 -and $x.machine -match '^(AMD64|x86_64)$') { return $x }
        Log "[SKIP] $($x.version) $($x.bits)-bit: unsupported"
    } catch { Log "[SKIP] Cannot inspect $path" }
}
function Candidates($old) {
    $paths=New-Object 'System.Collections.Generic.List[string]'
    if ($old -and $old.base_python) { $paths.Add([string]$old.base_python) }
    if (Test-Path -LiteralPath $Py) { $p=Probe $Py; if ($p) { $paths.Add([string]$p.base) } }
    foreach ($cmd in @(Get-Command py.exe -All -ErrorAction SilentlyContinue)) {
        try { foreach ($line in @(& $cmd.Source -0p 2>$null)) { if ($line -match '(?i)([A-Z]:\\.*?python\.exe)\s*$') { $paths.Add($Matches[1]) } } } catch {}
    }
    foreach ($hive in @('CurrentUser','LocalMachine')) { foreach ($view in @('Registry64','Registry32')) {
        try {
            $base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]$hive,[Microsoft.Win32.RegistryView]$view)
            $reg=$base.OpenSubKey('Software\Python')
            if ($reg) { foreach ($company in $reg.GetSubKeyNames()) { $co=$reg.OpenSubKey($company); foreach ($tag in $co.GetSubKeyNames()) { $ip=$co.OpenSubKey($tag+'\InstallPath'); if ($ip) { $exe=$ip.GetValue('ExecutablePath'); if (!$exe -and $ip.GetValue('')) { $exe=Join-Path ($ip.GetValue('')) 'python.exe' }; if ($exe) { $paths.Add([string]$exe) }; $ip.Close() } }; $co.Close() }; $reg.Close() }; $base.Close()
        } catch {}
    }}
    foreach ($dir in @((Join-Path $env:LOCALAPPDATA 'Programs\Python'),$env:ProgramFiles,($env:SystemDrive+'\'))) {
        foreach ($d in @(Get-ChildItem -LiteralPath $dir -Directory -Filter 'Python*' -ErrorAction SilentlyContinue)) { $paths.Add((Join-Path $d.FullName 'python.exe')) }
    }
    foreach ($cmd in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)) { $paths.Add($cmd.Source) }
    $seen=@{}
    foreach ($path in ($paths | Select-Object -Unique)) {
        $x=Probe $path
        if ($x -and !$seen.ContainsKey([string]$x.base)) {
            $baseProbe=Probe $x.base
            if ($baseProbe) { $seen[[string]$x.base]=$true; Log "[FOUND] Python $($baseProbe.version) - $($baseProbe.path)"; $baseProbe }
        }
    }
}
function Pick($items) {
    $f=New-Object Windows.Forms.Form; $f.Text='Choose Python'; $f.StartPosition='CenterScreen'; $f.TopMost=$true; $f.ClientSize=New-Object Drawing.Size(670,270)
    $list=New-Object Windows.Forms.ListBox; $list.SetBounds(12,12,646,195)
    foreach ($p in $items) { [void]$list.Items.Add("Python $($p.version) x64 | $($p.path)") }
    if ($list.Items.Count -gt 0) { $list.SelectedIndex=0 }
    $use=New-Object Windows.Forms.Button; $use.Text='Use selected'; $use.SetBounds(12,220,125,35); $use.Add_Click({ if ($list.SelectedIndex -ge 0) { $f.DialogResult='OK' } })
    $manual=New-Object Windows.Forms.Button; $manual.Text='Browse python.exe'; $manual.SetBounds(145,220,150,35); $manual.Add_Click({ $f.DialogResult='Retry' })
    $cancel=New-Object Windows.Forms.Button; $cancel.Text='Cancel'; $cancel.SetBounds(550,220,108,35); $cancel.DialogResult='Cancel'
    $f.Controls.AddRange(@($list,$use,$manual,$cancel)); $r=$f.ShowDialog(); $idx=$list.SelectedIndex; $f.Dispose()
    if ($r -eq 'OK') { return $items[$idx] }
    if ($r -eq 'Retry') {
        $d=New-Object Windows.Forms.OpenFileDialog; $d.Filter='Python executable (python.exe)|python.exe'; $d.Title='Select Python 3.10-3.12 x64'; $r=$d.ShowDialog(); $path=$d.FileName; $d.Dispose()
        if ($r -eq 'OK') { $p=Probe $path; if ($p) { return (Probe $p.base) }; throw 'Selected interpreter is not compatible.' }
    }
    throw 'Python selection cancelled.'
}
function SelectPython($old,[bool]$manual) {
    Log '[CHECK] Searching for Python 3.10-3.12 x64...'
    $items=@(Candidates $old | Sort-Object @{Expression={ if ($_.minor -eq 12) { 0 } elseif ($_.minor -eq 11) { 1 } else { 2 } }}, @{Expression={[version]$_.version};Descending=$true})
    if ($manual) { return (Pick $items) }
    if ($items.Count -gt 0) { return $items[0] }
    Log '[WARNING] No compatible Python installation found.'
    $winget=Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget -and (Ask 'No compatible Python was found. Install Python 3.12 x64 for your user account through Windows Package Manager (winget)? Internet is required.')) {
        Log '[INSTALL] Installing Python 3.12 via winget...'
        & $winget.Source install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64 --accept-source-agreements --accept-package-agreements | Out-Host
        if ($LASTEXITCODE -eq 0) { $items=@(Candidates $null | Sort-Object @{Expression={$_.minor};Descending=$true}); if ($items.Count -gt 0) { return $items[0] } }
        Log '[WARNING] Automatic installation unavailable or not registered yet.'
    }
    if (Ask 'Open the official Python downloads page? Install Python 3.12 x64, then run Thicc_tool.bat again. Choose No to browse for an existing interpreter.') {
        Start-Process 'https://www.python.org/downloads/windows/'
        throw 'Install Python and restart the launcher.'
    }
    return (Pick @())
}
function RunPython([string]$exe,[string[]]$arguments) {
    $previous=$ErrorActionPreference
    try { $ErrorActionPreference='Continue'; & $exe @arguments 2>&1 | ForEach-Object { Write-Host $_ }; $code=$LASTEXITCODE } finally { $ErrorActionPreference=$previous }
    if ($code -ne 0) { throw "Python command failed (exit $code): $($arguments -join ' ')" }
}
function ValidateEnvironment {
    Log '[CHECK] Verifying package dependency consistency...'
    RunPython $Py @('-m','pip','check')
    Log '[CHECK] Verifying native libraries and imports...'
    $check=Join-Path $Root 'environment_check.py'
    $lines=& $Py $check
    if ($LASTEXITCODE -ne 0) { throw 'Python import validation failed.' }
    $result=($lines | Select-Object -Last 1) | ConvertFrom-Json
    foreach ($p in $result.packages.PSObject.Properties) { Log "[OK] $($p.Name) $($p.Value)" }
    return $result
}
function LaunchTool {
    Log '[START] Loading Thicc Tool and initializing the 3D engine...'
    $signal=Join-Path ([IO.Path]::GetTempPath()) ('thicc-ready-'+[guid]::NewGuid().ToString('N')+'.json')
    $env:THICC_READY_FILE=$signal
    try {
        $app=Start-Process -FilePath $Pyw -ArgumentList ('"'+(Join-Path $Root 'thicc_tool_gui.pyw')+'"') -WorkingDirectory $Root -PassThru
        $clock=[Diagnostics.Stopwatch]::StartNew()
        while ($true) {
            if (Test-Path -LiteralPath $signal -PathType Leaf) {
                $ready=Get-Content -LiteralPath $signal -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($ready.status -eq 'error') { throw "Thicc Tool failed: $($ready.message)" }
                if ($ready.status -eq 'ready') { Log "[READY] Thicc Tool started. 3D engine: $($ready.viewer)"; return }
            }
            $app.Refresh(); if ($app.HasExited) { throw "Thicc Tool exited before ready (exit $($app.ExitCode)). See gui_error.log if present." }
            if ($clock.Elapsed.TotalSeconds -gt 240) { throw 'Startup did not report ready within 240 seconds. The application was not terminated; inspect it and gui_error.log.' }
            Start-Sleep -Milliseconds 150
        }
    } finally { Remove-Item Env:THICC_READY_FILE -ErrorAction SilentlyContinue; Remove-Item -LiteralPath $signal -Force -ErrorAction SilentlyContinue }
}
$lock=$null
try {
    if ($PSVersionTable.PSVersion -lt [version]'5.1' -or ![Environment]::Is64BitOperatingSystem) { throw 'Windows 10/11 x64 and Windows PowerShell 5.1 are required.' }
    $os=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    if ([int]$os.CurrentBuildNumber -lt 17763) { throw 'Windows 10 version 1809 or newer is required.' }
    try { $lock=[IO.File]::Open((Join-Path $Root '.thicc_environment.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) } catch { throw 'Another setup/launcher process is active or the tool folder is not writable.' }
    $old=ReadCache
    if ($Mode -eq 'Info') { if ($old) { Log ($old | ConvertTo-Json -Depth 8); Log "[INFO] Cache valid: $(CacheValid $old)" } else { Log '[INFO] No environment cache exists.' }; exit 0 }
    if ($Mode -eq 'Clear') { Remove-Item -LiteralPath $Cache -Force -ErrorAction SilentlyContinue; Log '[OK] Environment cache cleared. Run launcher to validate again.'; exit 0 }
    if ($Mode -eq 'Launch' -and (CacheValid $old)) { Log '[CACHE HIT] Environment already validated.'; Log "[OK] Python $($old.python_version) | dependency check skipped"; LaunchTool; exit 0 }
    foreach ($running in @(Get-Process pythonw,python -ErrorAction SilentlyContinue)) {
        try { $runningPath=$running.Path } catch { $runningPath=$null }
        if ($runningPath -and $runningPath.StartsWith($Venv+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Close Thicc Tool before modifying its Python environment.' }
    }
    Log '[SETUP] Checking environment. First setup may download large packages.'
    $base=$null
    if ($Mode -ne 'Change' -and $old -and $old.base_python) { $base=Probe $old.base_python }
    if (!$base -and $Mode -ne 'Change' -and (Test-Path -LiteralPath $Py)) { $existing=Probe $Py; if ($existing) { $base=Probe $existing.base } }
    if (!$base) { $base=SelectPython $old ($Mode -eq 'Change') }
    if (!$base) { throw 'No compatible Python selected.' }
    Log "[SELECTED] Python $($base.version) x64 - $($base.path)"
    $existing=Probe $Py
    $rebuild=($Mode -eq 'Rebuild' -or $Mode -eq 'Change' -or ($old -and $old.root -ne $Root) -or !$existing -or ($existing.base -ne $base.path))
    if ($rebuild -and (Test-Path -LiteralPath $Venv)) {
        if (!(Ask 'The existing .venv must be rebuilt. It will be renamed to a backup directory, not deleted. Continue?')) { throw 'Environment rebuild cancelled.' }
        $backup=Join-Path $Root ('.venv.backup-'+[guid]::NewGuid().ToString('N').Substring(0,8))
        Move-Item -LiteralPath $Venv -Destination $backup
        Log "[BACKUP] $backup"
    }
    if ($rebuild -or !(Test-Path -LiteralPath $Py)) { Log '[SETUP] Creating isolated Python environment...'; RunPython $base.path @('-m','venv',$Venv) }
    Remove-Item -LiteralPath $Cache -Force -ErrorAction SilentlyContinue
    Log '[CHECK] Checking/installing pinned dependencies (only binary wheels)...'
    $argsInstall=@('-m','pip','install','--only-binary=:all:','-r',$Req)
    if ($Mode -eq 'Repair') { $argsInstall+= '--force-reinstall' }
    RunPython $Py $argsInstall
    $verified=ValidateEnvironment
    $data=[ordered]@{schema=1;status='ready';root=$Root;setup_hash=(SetupHash);requirements_hash=(Hash $Req);base_python=$base.path;python_version=$verified.python;base_fingerprint=(Finger $base.path);python_fingerprint=(Finger $Py);pythonw_fingerprint=(Finger $Pyw);venv_config_hash=(Hash (Join-Path $Venv 'pyvenv.cfg'));packages=$verified.packages;module_files=$verified.module_files;validated_utc=[DateTime]::UtcNow.ToString('o')}
    SaveCache $data
    Log '[OK] Environment validated and cached.'
    if ($Mode -eq 'Launch') { LaunchTool }
    exit 0
} catch { Log ('[ERROR] '+$_.Exception.Message); exit 1 }
finally { if ($lock) { $lock.Dispose() } }
