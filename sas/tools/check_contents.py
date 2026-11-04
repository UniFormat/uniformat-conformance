#!/usr/bin/env python3
"""Compare les metadonnees de colonnes lues par ref_reader.py a la sortie PROC CONTENTS du corpus.

Usage : python3 -I rea_output/tools/check_contents.py <dossier racine contenant files/> [motif de nom]
Pour chaque <table>.sas7bdat avec <table>.contents.txt voisin, compare par variable : numero (ordre de
creation), nom, type, longueur, format (nom, largeur, decimales), informat, label. Le format et l'informat de
PROC CONTENTS sont ecrits "NOM" + largeur + "." + decimales (ex. DATE9. , $CHAR20. , BEST12.).
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util  # noqa: E402

_path = os.environ.get("REF_READER") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_reader.py")
_spec = importlib.util.spec_from_file_location("ref_reader_under_test", _path)
ref_reader = importlib.util.module_from_spec(_spec)  # lecteur teste : variable d'environnement REF_READER (defaut ref_reader.py)
_spec.loader.exec_module(ref_reader)


def parse_contents(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    seg = text.split("Alphabetic List of Variables and Attributes")[-1].splitlines()
    head = next((l for l in seg if "Variable" in l and "Type" in l and "Len" in l), None)
    if head is None:
        return None
    cols = {k: head.index(k) for k in ("Variable", "Type", "Len", "Format", "Informat", "Label") if k in head}
    starts = sorted(cols.values())
    res = {}
    pos = seg.index(head) + 1
    for l in seg[pos:]:
        m = re.match(r"^\s*(\d+)\s+(\S+)\s+(Num|Char)\s+(\d+)", l)
        if not m:
            continue
        extra = len(m.group(2).encode("utf-8")) - len(m.group(2))  # SAS remplit la colonne Variable en octets : les colonnes suivantes reculent

        def cut(k):
            if k not in cols:
                return ""
            s = cols[k] - extra
            nxt = [x - extra for x in starts if x - extra > s]
            return l[s:(nxt[0] if nxt else len(l))].strip()
        res[m.group(2)] = dict(num=int(m.group(1)), type="n" if m.group(3) == "Num" else "c", length=int(m.group(4)),
                               format=cut("Format"), informat=cut("Informat"), label=cut("Label"))
    return res


def fmt_str(name, width, dec):
    if not name:
        return ""
    if name.startswith("$"):
        base = name
    else:
        base = name
    return f"{base}{width if width else ''}.{dec if dec else ''}"


def check(path):
    sf = ref_reader.SasFile(open(path, "rb").read())
    ref = parse_contents(path[: -len(".sas7bdat")] + ".contents.txt")
    errs = []
    if ref is None:
        return ["contents illisible"]
    if len(ref) != len(sf.columns):
        errs.append(f"nombre de variables : contents={len(ref)} lecteur={len(sf.columns)}")
    for j, c in enumerate(sf.columns, 1):
        r = ref.get(c.name)
        if r is None:
            errs.append(f"variable {c.name!r} absente de PROC CONTENTS")
            continue
        got = dict(num=j, type=c.type, length=c.length, label=c.label)
        for k in ("num", "type", "length", "label"):
            if k == "label" and got[k].startswith(r[k]) and len(r[k]) >= 60 and len(got[k]) > len(r[k]):
                continue  # le listing PROC CONTENTS (linesize=200) tronque les labels tres longs
            if r[k] != got[k]:
                errs.append(f"{c.name}.{k} : contents={r[k]!r} lecteur={got[k]!r}")
        for k, nm, w, d in (("format", c.format, c.fmt_width, c.fmt_dec), ("informat", c.informat, c.inf_width, c.inf_dec)):
            want = r[k]
            g = fmt_str(nm, w, d)
            if want != g and (want or nm):
                errs.append(f"{c.name}.{k} : contents={want!r} lecteur={g!r}")
    return errs


def main(argv):
    pat = argv[2] if len(argv) > 2 else ""
    total = bad = 0
    for p in sorted(glob.glob(os.path.join(argv[1], "**", "*.sas7bdat"), recursive=True)):
        if pat not in os.path.basename(p) or not os.path.exists(p[: -len(".sas7bdat")] + ".contents.txt"):
            continue
        total += 1
        try:
            errs = check(p)
        except Exception as e:  # noqa: BLE001
            errs = [f"exception {type(e).__name__}: {e}"]
        if errs:
            bad += 1
            print(f"ECART {os.path.basename(p)} : {errs[0]}" + (f" (+{len(errs) - 1})" if len(errs) > 1 else ""))
    print(f"--- {total} fichiers, {total - bad} OK, {bad} avec ecart")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
