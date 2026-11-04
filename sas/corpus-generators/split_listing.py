#!/usr/bin/env python3
"""Decoupe le listing d'un programme du corpus en un fichier par table et par procedure.

Chaque PROC CONTENTS / PROC PRINT est precedee, dans le programme, d'un titre
"@@@ <table> contents|print". Ce script ecrit corpus/files/<famille>/<table>.contents.txt
et <table>.print.txt (la ligne de titre-marqueur est conservee en tete de fichier).

Usage : python3 -I corpus/gen/split_listing.py corpus/out/<programme>.lst [dossier]
        dossier = sous-dossier de corpus/ recevant les fichiers (defaut files ; files_sas_small pour sas_small)
"""
import os
import re
import sys

MARK = re.compile(r"^\s*@@@ (\S+) (contents|print)\s*$")
lst = sys.argv[1]
files_dir = sys.argv[2] if len(sys.argv) > 2 else "files"
corpus = os.path.dirname(os.path.dirname(os.path.abspath(lst)))  # .../corpus
with open(lst, encoding="utf-8", errors="replace") as f:
    lines = f.read().replace("\f", "\n").split("\n")

cur, buf, n = None, [], 0


def flush():
    global n
    if cur and buf:
        fam = cur[0].split("_")[0]
        d = os.path.join(corpus, files_dir, fam)
        os.makedirs(d, exist_ok=True)
        while buf and not buf[-1].strip():
            buf.pop()
        with open(os.path.join(d, f"{cur[0]}.{cur[1]}.txt"), "w", encoding="utf-8") as g:
            g.write("\n".join(buf) + "\n")
        n += 1


for line in lines:
    m = MARK.match(line)
    if m:
        key = (m.group(1), m.group(2))
        if key != cur:
            flush()
            cur, buf = key, [line]
        continue  # titre repete sur une page suivante : ignore
    if cur is not None:
        buf.append(line)
flush()
print(f"{n} sections ecrites depuis {lst}")
