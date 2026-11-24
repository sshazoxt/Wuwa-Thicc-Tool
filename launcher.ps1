param([switch]$Maintenance)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$root=$PSScriptRoot
$script:worker=$null
$script:outFile=$null
$script:errFile=$null
$script:logFile=$null
$script:mode='Launch'
$script:finished=$false
$script:tail=''
$script:logSaved=$false
$form=New-Object Windows.Forms.Form
$form.Text='Thicc Tool 007 | Launcher'
$form.StartPosition='CenterScreen'
$form.FormBorderStyle='FixedSingle'
$form.MaximizeBox=$false
$form.BackColor=[Drawing.ColorTranslator]::FromHtml('#171717')
$form.ForeColor=[Drawing.ColorTranslator]::FromHtml('#eeeeee')
$form.AutoScaleMode='None'
$screen=[Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$width=[int][Math]::Min(960,[Math]::Min($screen.Width-60,($screen.Height-180)*16/9))
$width=[Math]::Max(400,$width)
$height=[int]($width*9/16)
$form.ClientSize=New-Object Drawing.Size($width,($height+136))
$pic=New-Object Windows.Forms.PictureBox
$pic.SetBounds(0,0,$width,$height)
$pic.SizeMode='StretchImage'
$pic.Image=[Drawing.Image]::FromFile((Join-Path $root 'assets\launcher.jpg'))
$form.Controls.Add($pic)
$status=New-Object Windows.Forms.Label
$status.SetBounds(12,($height+7),($width-24),21)
$status.Font=New-Object Drawing.Font('Segoe UI',10,[Drawing.FontStyle]::Bold)
$status.ForeColor=[Drawing.ColorTranslator]::FromHtml('#e8c18d')
$status.Text='Preparing launcher...'
$form.Controls.Add($status)
$log=New-Object Windows.Forms.TextBox
$log.Multiline=$true; $log.ReadOnly=$true; $log.WordWrap=$false; $log.ScrollBars='Vertical'; $log.BorderStyle='FixedSingle'
$log.SetBounds(12,($height+31),($width-24),66)
$log.BackColor=[Drawing.ColorTranslator]::FromHtml('#242424'); $log.ForeColor=[Drawing.ColorTranslator]::FromHtml('#d9d9d9')
$log.Font=New-Object Drawing.Font('Consolas',9)
$log.Text='[START] Thicc Tool 007'; $form.Controls.Add($log)
$bar=New-Object Windows.Forms.ProgressBar
$bar.SetBounds(12,($height+102),($width-240),5); $bar.Style='Marquee'; $bar.MarqueeAnimationSpeed=25; $form.Controls.Add($bar)
$open=New-Object Windows.Forms.Button; $open.Text='Open log'; $open.SetBounds(($width-225),($height+101),100,28); $open.Enabled=$false; $form.Controls.Add($open)
$close=New-Object Windows.Forms.Button; $close.Text='Close'; $close.SetBounds(($width-115),($height+101),103,28); $close.Enabled=$false; $form.Controls.Add($close)
$close.Add_Click({ $form.Close() })
$open.Add_Click({ if ($script:logFile -and (Test-Path -LiteralPath $script:logFile)) { Start-Process notepad.exe -ArgumentList ('"'+$script:logFile+'"') } })
$form.Add_FormClosing({ param($sender,$e) if ($script:worker -and !$script:worker.HasExited) { $e.Cancel=$true; $status.Text='Setup is still running; finish or cancel the current installer dialog.' } })
function ChooseMode {
    $d=New-Object Windows.Forms.Form; $d.Text='Thicc Tool | Environment maintenance'; $d.StartPosition='CenterParent'; $d.ClientSize=New-Object Drawing.Size(440,295); $d.FormBorderStyle='FixedDialog'; $d.MaximizeBox=$false; $d.MinimizeBox=$false
    $label=New-Object Windows.Forms.Label; $label.Text='Choose an operation:'; $label.SetBounds(12,10,416,24); $d.Controls.Add($label)
    $combo=New-Object Windows.Forms.ListBox; $combo.SetBounds(12,40,416,180)
    $options=@('Check / install missing dependencies','Repair (reinstall pinned dependencies)','Change Python interpreter','Rebuild virtual environment','Show environment information','Clear environment cache','Launch Thicc Tool')
    $modes=@('Check','Repair','Change','Rebuild','Info','Clear','Launch')
    foreach ($o in $options) { [void]$combo.Items.Add($o) }; $combo.SelectedIndex=0; $d.Controls.Add($combo)
    $go=New-Object Windows.Forms.Button; $go.Text='Continue'; $go.SetBounds(222,238,100,32); $go.DialogResult='OK'; $d.Controls.Add($go)
    $no=New-Object Windows.Forms.Button; $no.Text='Cancel'; $no.SetBounds(328,238,100,32); $no.DialogResult='Cancel'; $d.Controls.Add($no)
    $result=$d.ShowDialog($form); $idx=$combo.SelectedIndex; $d.Dispose(); if ($result -eq 'OK') { return $modes[$idx] }; return $null
}
function ReadLog([string]$p) {
    if (!$p -or !(Test-Path -LiteralPath $p)) { return '' }
    try {
        $s=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
        try { $r=New-Object IO.StreamReader($s,[Text.Encoding]::UTF8,$true); try { return $r.ReadToEnd() } finally { $r.Dispose() } } finally { $s.Dispose() }
    } catch { return '' }
}
function UpdateLog {
    $out=ReadLog $script:outFile; $err=ReadLog $script:errFile
    $all=$out+"`r`n"+$err
    $lines=@($all -split '[\r\n]+' | Where-Object { $_.Trim() })
    $tail=($lines | Select-Object -Last 4) -join "`r`n"
    if ($tail -and $tail -ne $script:tail) { $script:tail=$tail; $log.Text=$tail; $log.SelectionStart=$log.TextLength; $log.ScrollToCaret() }
    $last=@($lines | Where-Object { $_ -match '^\[(SETUP|CHECK|CACHE HIT|START|READY|INSTALL|ERROR|WARNING|OK|SELECTED)\]' } | Select-Object -Last 1)
    if ($last.Count -gt 0) { $status.Text=$last[0]; if ($last[0] -match '^\[(CACHE HIT|READY)\]') { $status.ForeColor=[Drawing.ColorTranslator]::FromHtml('#91d3ac') } else { $status.ForeColor=[Drawing.ColorTranslator]::FromHtml('#e8c18d') } }
    return $all
}
$timer=New-Object Windows.Forms.Timer; $timer.Interval=150
$timer.Add_Tick({
    try {
        $all=UpdateLog
        if ($script:worker -and $script:worker.HasExited) {
            $timer.Stop(); $script:finished=$true
            [IO.File]::WriteAllText($script:logFile,$all,[Text.UTF8Encoding]::new($false)); $script:logSaved=$true
            $open.Enabled=$true; $close.Enabled=$true; $bar.Style='Blocks'; $bar.MarqueeAnimationSpeed=0
            if ($script:worker.ExitCode -eq 0) {
                $bar.Value=100; $status.ForeColor=[Drawing.ColorTranslator]::FromHtml('#91d3ac')
                if ($script:mode -eq 'Launch') { $status.Text='Ready — Thicc Tool is open'; $form.Close() } else { $status.Text='Maintenance finished. Open log for details.' }
            } else { $status.ForeColor=[Drawing.ColorTranslator]::FromHtml('#f0a4a4'); $status.Text='Setup or startup failed — see log.' }
        }
    } catch { $timer.Stop(); $status.Text='Launcher error: '+$_.Exception.Message; $close.Enabled=$true; $open.Enabled=($script:logFile -and (Test-Path -LiteralPath $script:logFile)) }
})
$form.Add_Shown({
    try {
        if ($Maintenance) { $script:mode=ChooseMode; if (!$script:mode) { $form.Close(); return } }
        $logs=Join-Path $root 'logs'; [void](New-Item -ItemType Directory -Path $logs -Force)
        $id=[DateTime]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8)
        $script:outFile=Join-Path $logs ('setup-'+$id+'.stdout.log'); $script:errFile=Join-Path $logs ('setup-'+$id+'.stderr.log'); $script:logFile=Join-Path $logs ('setup-'+$id+'.log')
        $ps=Join-Path $PSHOME 'powershell.exe'; $bootstrap=Join-Path $root 'bootstrap.ps1'
        $argsLine='-NoProfile -ExecutionPolicy Bypass -STA -File "'+$bootstrap+'" -Mode '+$script:mode
        $script:worker=Start-Process -FilePath $ps -ArgumentList $argsLine -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $script:outFile -RedirectStandardError $script:errFile -PassThru
        $timer.Start()
    } catch { $status.Text='Launcher error: '+$_.Exception.Message; $status.ForeColor=[Drawing.ColorTranslator]::FromHtml('#f0a4a4'); $close.Enabled=$true; $bar.Style='Blocks' }
})
try { [void]$form.ShowDialog() } finally {
    $timer.Stop(); $timer.Dispose(); if ($pic.Image) { $pic.Image.Dispose() }; $form.Dispose()
    if ($script:logSaved) { Remove-Item -LiteralPath $script:outFile,$script:errFile -Force -ErrorAction SilentlyContinue }
}
