#!/usr/bin/env python3
"""Regenere avec ref_writer les tables compressees du corpus complementaire et compare la disposition des pages a celle de SAS.

Usage : python3 -I rea_output/tools/compare_multipage.py [dossier files_complement]
Compare, pour chaque table : nombre de pages, (type, blocs) de chaque page, lignes cumulees et numeros de page de la page marqueur.
Ecarts attendus : la page 0 de SAS a 1 bloc de plus (sous-en-tete ColumnList, omis par l'ecrivain : W05) ; avec COMPRESS=BINARY le
compresseur de reference produit des flots plus courts que ceux de SAS, donc plus de lignes par page (sans effet sur la validite).
"""
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_writer as W

ALPHA = "abcdefghijklmnopqrstuvwxyz0123456789"


def comp_rows(n):
    return [(k, k / 4, "ligne %d" % (k % 7), "ababababab"[: 2 * (k % 5) + 2]) for k in range(1, n + 1)]


def big_rows(n):
    s, out = 12345, []
    for k in range(1, n + 1):
        a = []
        for _ in range(440):
            s = (s * 1103 + 12345) % 65521
            a.append(ALPHA[s % 36])
        out.append((k, "".join(a)))
    return out


def cols_comp():
    return [W.Col("i", "n", 8), W.Col("x", "n", 8), W.Col("a", "c", 40), W.Col("b", "c", 12)]


def cols_big():
    return [W.Col("i", "n", 8), W.Col("a", "c", 440)]


def layout(path):
    b = open(path, "rb").read()
    hl, pl = struct.unpack_from("<II", b, 200)
    pc = struct.unpack_from("<Q", b, 208)[0]
    res = []
    for k in range(pc):
        p = b[hl + k * pl: hl + (k + 1) * pl]
        t, bc, sc = struct.unpack_from("<HHH", p, 32)
        res.append((t, bc, sc))
    return res, b, hl, pl


def main(argv):
    d = argv[1] if len(argv) > 1 else "corpus/files_complement"
    cases = []
    for n in (255, 256, 257, 300, 1000, 10000):
        cases.append((f"comp_n{n}", cols_comp(), comp_rows(n), 65536))
    for n in (200, 300, 1000):
        cases.append((f"big_n{n}", cols_big(), big_rows(n), 65536))
    for bs in (4096, 8192, 16384):
        cases.append((f"pg{bs}", cols_comp(), comp_rows(300), bs))
    bad = 0
    tmp = tempfile.mkdtemp()
    for name, cols, rows, pl in cases:
        for algo, tag in (("CHAR", "char"), ("BINARY", "binary")):
            ref = f"{d}/{name}_{tag}.sas7bdat"
            out = f"{tmp}/{name}_{tag}.sas7bdat"
            for c in cols:
                c.offset = None
            W.write(out, cols, rows, compress=algo, page_length=pl, seed=1)
            lay_s, bs, hs, ps_ = layout(ref)
            lay_m, bm, hm, pm = layout(out)
            lay_s_adj = [(lay_s[0][0], lay_s[0][1] - 1, lay_s[0][2] - 1)] + lay_s[1:] if lay_s else lay_s  # ColumnList absent de la page 0 ecrite
            ok_l = lay_s_adj == lay_m
            mk = [k for k, x in enumerate(lay_s) if x[0] == 0x9000]
            ok_mk = True
            if mk and mk == [k for k, x in enumerate(lay_m) if x[0] == 0x9000]:
                k = mk[0]
                def tri(bb, hh, pp):
                    p = bb[hh + k * pp: hh + (k + 1) * pp]
                    n = struct.unpack_from("<H", p, 36)[0]
                    S = min(pp, 32767) - 18 * n
                    return [(int.from_bytes(p[S + 18 * j: S + 18 * j + 8], "big"), int.from_bytes(p[S + 18 * j + 8: S + 18 * j + 16], "little")) for j in range(n)]
                ok_mk = tri(bs, hs, ps_) == tri(bm, hm, pm)
            else:
                ok_mk = False
            print(f"{name}_{tag}: pages {len(lay_s)}/{len(lay_m)} disposition {'=' if ok_l else 'DIFF'} marqueur {'=' if ok_mk else 'DIFF'}")
            if not ok_l:
                print("   SAS    :", lay_s_adj[:6], "...")
                print("   ecrit  :", lay_m[:6], "...")
            bad += (not ok_l) + (not ok_mk)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
