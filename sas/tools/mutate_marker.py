#!/usr/bin/env python3
"""Mutations de la page marqueur 0x9000 d'une table compressee a trois pages de lignes, relues par SAS (oracle sas_small).

Usage : python3 -I rea_output/tools/mutate_marker.py
Base : 300 lignes de 448 octets de texte (COMPRESS=CHAR), pages de 65 536 octets -> pages : 0 (lignes), 1 (marqueur), 2 et 3 (lignes).
Chaque mutation modifie un champ de la page marqueur et classe la reaction de SAS (PROC CONTENTS + etape DATA) :
  ignore / modifie / rejet (voir mutate_write.py).  Resultat : rea_output/evidence/write/mutations_marqueur.tsv
"""
import concurrent.futures
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mutate_write as M  # noqa: E402
import ref_writer as W  # noqa: E402

PL = 65536
REPO = M.REPO
OUTTSV = os.path.join(REPO, "rea_output", "evidence", "write", "mutations_marqueur.tsv")


def base():
    rnd = random.Random(5)
    alpha = "abcdefghijklmnopqrstuvwxyz0123456789"
    cols = [W.Col("i", "n", 8), W.Col("a", "c", 440)]
    rows = [[k, "".join(rnd.choice(alpha) for _ in range(440))] for k in range(1, 301)]
    p = os.path.join(M.DIR, "mm_base.sas7bdat")
    W.write(p, cols, rows, compress="CHAR", seed=3)
    data = open(p, "rb").read()
    os.remove(p)
    return cols, data


def find_marker(b):
    n = struct.unpack_from("<Q", b, 208)[0]
    for k in range(n):
        if struct.unpack_from("<H", b, PL + k * PL + 32)[0] == 0x9000:
            return PL + k * PL
    raise SystemExit("pas de page marqueur")


def put(b, off, fmt, v):
    out = bytearray(b)
    struct.pack_into(fmt, out, off, v)
    return bytes(out)


def mutants(b):
    m = find_marker(b)
    n = struct.unpack_from("<H", b, m + 36)[0]
    S = min(PL, 32767) - 18 * n
    out = []

    def add(name, data):
        out.append((name, data))

    for v in (0, 2):
        add(f"hdr24={v}", put(b, m + 24, "<Q", v))
    cur = struct.unpack_from("<H", b, m + 34)[0]
    for d in (-1, 1):
        add(f"blocs{d:+d}", put(b, m + 34, "<H", cur + d))
    for d in (-1, 1):
        add(f"sous-en-tetes{d:+d}", put(b, m + 36, "<H", n + d))
    f38 = struct.unpack_from("<H", b, m + 38)[0]
    for name, v in (("0", 0), ("-1", f38 - 1), ("+1", f38 + 1), ("ffff", 0xFFFF)):
        add(f"champ38={name}", put(b, m + 38, "<H", v))
    for j in range(n):
        o = m + S + 18 * j
        cum = struct.unpack_from(">Q", b, o)[0]
        pno = struct.unpack_from("<Q", b, o + 8)[0]
        last = struct.unpack_from("<H", b, o + 16)[0]
        for nm, v in (("-1", cum - 1), ("+1", cum + 1), ("0", 0), ("ffff", 0xFFFF), ("2^32", 1 << 32)):
            add(f"t{j}.cum{nm}", put(b, o, ">Q", v))
        for nm, v in (("-1", pno - 1), ("+1", pno + 1), ("0", 0)):
            add(f"t{j}.page{nm}", put(b, o + 8, "<Q", v))
        for nm, v in (("-1", last - 1), ("+1", last + 1), ("0", 0)):
            add(f"t{j}.last{nm}", put(b, o + 16, "<H", v))
    # tous les triplets a zero ; type de page change
    z = bytearray(b)
    z[m + S: m + S + 18 * n] = bytes(18 * n)
    add("triplets=0", bytes(z))
    for v in (0x0000, 0x4000):
        add(f"type={v:#06x}", put(b, m + 32, "<H", v))
    return out


def main(argv):
    os.makedirs(M.EVID, exist_ok=True)
    cols, b = base()
    jobs = [("mm_ref", cols, b)]
    names = ["reference"]
    for k, (name, data) in enumerate(mutants(b)):
        jobs.append((f"mm_{k:02d}", cols, data))
        names.append(name)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        results = list(ex.map(M.run_one, jobs))
    ref = results[0]
    lines = ["mutation\treaction\tdetail"]
    for name, (bad, lst, csv) in zip(names, results):
        if name == "reference":
            react, det = ("ok" if not bad else "rejet"), (bad[0][:90] if bad else "journal propre")
        elif bad:
            react, det = "rejet", bad[0][:110]
        elif csv != ref[2] or lst != ref[1]:
            react, det = "modifie", "CSV ou metadonnees differents"
        else:
            react, det = "ignore", ""
        lines.append(f"{name}\t{react}\t{det}")
        print(lines[-1], flush=True)
    open(OUTTSV, "w").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
