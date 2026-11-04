#!/usr/bin/env python3
"""Compare, pour chaque table du corpus complementaire, les lignes lues par ref_reader.py au CSV de reference ecrit par SAS.

Usage : python3 -I rea_output/tools/check_complement_csv.py [dossier files_complement]
Les CSV sont ceux de build_complement.py (csv_step) : nombres en best32., chaines entre guillemets, separateur virgule.
"""
import csv
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_reader  # noqa: E402


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            rows.append(r)
    return rows


def norm(v):
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    if isinstance(v, float):
        return repr(float(v))
    return str(v).rstrip(" ")


def same(a, b):
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def main(argv):
    d = argv[1] if len(argv) > 1 else os.path.join(HERE, "..", "..", "corpus", "files_complement")
    tot = bad = 0
    for p in sorted(glob.glob(os.path.join(d, "*.sas7bdat"))):
        stem = os.path.basename(p)[:-9]
        m = re.match(r"(.*)_(no|char|binary)$", stem)
        if not m:
            continue
        base = m.group(1)
        csvp = os.path.join(d, "csv", base + ".csv")
        if not os.path.exists(csvp):
            continue
        ref = load(csvp)
        sf = ref_reader.SasFile(open(p, "rb").read())
        got = [[norm(v) for v in row] for row in sf.rows]
        exp = [[x.rstrip(" ") for x in r] for r in ref]
        ok = len(got) == len(exp) and all(len(a) == len(b) and all(same(x, y) for x, y in zip(a, b)) for a, b in zip(got, exp))
        tot += 1
        if not ok:
            bad += 1
            i = next((k for k, (a, b) in enumerate(zip(got, exp)) if a != b), None)
            print(f"ECART {stem}: {len(got)} lignes lues, {len(exp)} attendues ; premiere difference ligne {i}: {str(got[i])[:80] if i is not None else ''} / {str(exp[i])[:80] if i is not None else ''}")
    print(f"{tot} tables comparees, {bad} ecart(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
