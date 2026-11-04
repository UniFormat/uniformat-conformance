#!/usr/bin/env python3
"""Genere corpus/gen/probe/fmt/existence.sas : une etape DATA par nom de format ou d'informat candidat (une erreur de
compilation n'arrete que son etape). Le journal liste les noms absents de sas_small (ERROR 48-59 / 48-58)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fmt_candidates as C

out = ["options nodate nonumber linesize=200;"]
def fname(n):
    return n if n.startswith("$") else n
for n in C.NUM_FORMATS:
    out.append(f"data _null_; x=1; length s $200; s=put(x,{n}.); run;")
for n in C.CHAR_FORMATS:
    out.append(f'data _null_; x="ab"; length s $200; s=put(x,{n}.); run;')
for n in C.NUM_INFORMATS:
    out.append(f'data _null_; length s 8; s=input("1",{n}.); run;')
for n in C.CHAR_INFORMATS:
    out.append(f'data _null_; length s $200; s=input("ab",{n}.); run;')
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe", "fmt")
os.makedirs(d, exist_ok=True)
open(os.path.join(d, "existence.sas"), "w").write("\n".join(out) + "\n")
print(len(out) - 1, "etapes")
