"""Thicc Tool 1.9B: conservative WWMI structural diagnostics.

Independent implementation. Does not execute INI commands or modify geometry.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SEC = re.compile(r"^\s*\[([^\]]+)\]\s*$")
COMP = re.compile(r"^textureoverridecomponent(\d+)$", re.I)
DRAW = re.compile(r"^\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*(-?\d+))?\s*$")
RESOURCE = re.compile(r"^resource", re.I)
BINDING = re.compile(r"^(?:ib|vb\d+|ps-t\d+)$", re.I)
VARIABLE = re.compile(r"\$([a-z_]\w*)", re.I)

def read_sections(path, seen=None):
    path=Path(path).resolve()
    seen=set() if seen is None else seen
    if path in seen:
        raise ValueError("Repeated/recursive INI include: "+str(path))
    seen.add(path)
    sections={}
    current=None
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(),1):
        line=raw.strip()
        if not line: continue
        if not line.startswith(";"): line=line.split(";",1)[0].strip()
        match=SEC.match(line)
        if match:
            current=match.group(1).lower()
            if current in sections: raise ValueError("Duplicate section: "+current)
            sections[current]=[]
        elif current is not None:
            sections[current].append((number,line,str(path)))
    includes=sections.pop("include",[])
    for _,line,_ in includes:
        if line.startswith(";") or "=" not in line: continue
        key,value=(x.strip() for x in line.split("=",1))
        target=(path.parent/value.strip('"').replace("\\","/")).resolve()
        if key.lower()=="include":
            files=[target]
        elif key.lower()=="include_recursive":
            files=sorted(target.rglob("*.ini"))
        else: continue
        for file in files:
            for name,items in read_sections(file,seen).items():
                if name in sections: raise ValueError("Duplicate included section: "+name)
                sections[name]=items
    return sections

def section_values(lines):
    return {k.strip().lower():v.strip() for _,line,_ in lines
            if not line.startswith(";") and "=" in line
            for k,v in [line.split("=",1)]}

def analyze(ini):
    ini=Path(ini).resolve()
    sections=read_sections(ini)
    resources={name:section_values(lines) for name,lines in sections.items() if RESOURCE.match(name)}
    variables={}
    for _,line,_ in sections.get("constants",[]):
        m=re.match(r"global\s+(?:persist\s+)?\$(\w+)(?:\s*=\s*(-?\d+(?:\.\d+)?))?",line,re.I)
        if m: variables[m.group(1).lower()]=m.group(2) or "0"
    toggles={}
    for name,lines in sections.items():
        if not name.startswith("key"): continue
        for _,line,_ in lines:
            m=re.match(r"\$(\w+)\s*=\s*(-?\d+(?:\.\d+)?(?:\s*,\s*-?\d+(?:\.\d+)?)*)$",line,re.I)
            if m and m.group(1).lower() in variables:
                toggles.setdefault(m.group(1).lower(),set()).update(x.strip() for x in m.group(2).split(","))
    warnings=[]
    draws=[]
    def walk(section,component,stack,bindings,conditions,depth=0):
        if depth>20:
            warnings.append("CommandList nesting exceeded: "+section)
            return
        if section in stack:
            warnings.append("Recursive CommandList: "+" -> ".join(stack+[section]))
            return
        lines=sections.get(section)
        if lines is None:
            warnings.append("Missing CommandList: "+section)
            return
        guards=list(conditions)
        branch_stack=[]
        label=""
        for number,line,source in lines:
            if line.startswith(";"):
                m=re.match(r";\s*draw\s+(.+)",line,re.I)
                if m: label=m.group(1)
                continue
            low=line.lower()
            if low.startswith("if "):
                expr=line[3:].strip()
                branch_stack.append({"previous":[expr],"current":expr})
                guards.append(expr)
                continue
            if low.startswith("else if ") or low.startswith("elif "):
                if not branch_stack:
                    warnings.append("Orphan branch in "+section)
                    continue
                expr=line[8 if low.startswith("else if ") else 5:].strip()
                branch_stack[-1]["current"]=expr
                branch_stack[-1]["previous"].append(expr)
                guards[-1]=expr
                continue
            if low=="else":
                if branch_stack:
                    expr="NOT ("+" OR ".join(branch_stack[-1]["previous"])+")"
                    branch_stack[-1]["current"]=expr
                    guards[-1]=expr
                continue
            if low=="endif":
                if branch_stack: branch_stack.pop(); guards.pop()
                else: warnings.append("Orphan endif in "+section)
                continue
            if "=" not in line: continue
            key,value=(x.strip().lower() for x in line.split("=",1))
            if BINDING.match(key):
                bindings[key]=value
            elif key=="run":
                if value in sections and value not in ("commandlistmergeskeleton","commandlistcleanupsharedresources"):
                    walk(value,component,stack+[section],dict(bindings),guards,depth+1)
                elif value not in sections and not value.startswith("commandlist\\rabbitfx"):
                    warnings.append("Unresolved run: "+value)
            elif key=="drawindexed":
                m=DRAW.match(value)
                if not m:
                    warnings.append("Unsupported DrawIndexed: "+value)
                    continue
                deps=sorted(set(VARIABLE.findall(" ".join(guards))))
                draws.append(dict(component=component,source_section=section,source_file=source,
                    source_line=number,label=label,count=int(m[1]),start=int(m[2]),
                    base_vertex=int(m[3] or 0),conditions=list(guards),toggle_dependencies=deps,
                    bindings=dict(bindings)))
        if branch_stack: warnings.append("Unclosed conditional: "+section)
    for section in sections:
        m=COMP.match(section)
        if m: walk(section,int(m[1]),[],{},[])
    # This is a conservative potential-alternatives grouping, not proof of exclusivity.
    groups={}
    for draw in draws:
        key=(draw["component"],draw["start"],draw["count"],draw["base_vertex"])
        groups.setdefault(key,[]).append(draw)
    alternatives=[]
    for key,items in groups.items():
        if len(items)>1:
            alternatives.append(dict(geometry_key=list(key),
                draw_sources=[f'{x["source_section"]}:{x["source_line"]}' for x in items],
                conditions=[x["conditions"] for x in items],
                classification="potential_shared_geometry_not_confirmed_alternative"))
    return dict(schema="thicc_wwmi_structure_1.9b",ini=str(ini),
        ini_sha256=hashlib.sha256(ini.read_bytes()).hexdigest(),
        sections=len(sections),resources=resources,variables=variables,
        toggle_domains={k:sorted(v) for k,v in toggles.items()},
        draws=draws,potential_shared_geometry=alternatives,
        warnings=sorted(set(warnings)),
        limitations=["Symbolic guards are not evaluated; runtime state is not simulated.",
                     "Bindings within conditional branches are not state-isolated.",
                     "Draws sharing geometry are not necessarily mutually exclusive.",
                     "No anatomical or skin/garment classification is inferred."])

def main():
    parser=argparse.ArgumentParser(description="Thicc Tool WWMI structural report (read-only)")
    parser.add_argument("ini",type=Path)
    parser.add_argument("-o","--output",type=Path)
    args=parser.parse_args()
    report=analyze(args.ini)
    data=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(data,encoding="utf-8")
        print(f'{len(report["draws"])} draws; {len(report["warnings"])} warnings; {args.output}')
    else: print(data)
if __name__=="__main__": main()
