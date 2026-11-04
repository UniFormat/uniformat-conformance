#!/usr/bin/env python3
"""Diff binaire d'une paire de fichiers .sas7bdat : liste les offsets qui varient, rapportes a un champ.

Usage : python3 -I rea_output/tools/diff_pair.py reference.sas7bdat variante.sas7bdat [--max N]
  * en-tete : chaque difference est rapportee au champ de fields.header_fields (ou "hors champ") ;
  * pages   : pour chaque page, type et nombre d'octets differents ; pour les pages a sous-en-tetes, les
              sous-en-tetes de meme rang sont compares et les differences rapportees (structure, offset dans le sous-en-tete).
Deux fichiers produits par SAS different toujours par les horodatages (created/modified) et leurs derives
(created_low_*, file_code, created_copy, signatures de page) : ils sont marques "[derive de l'horodatage]".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fields  # noqa: E402
import inspect_sas7bdat as I  # noqa: E402

TIME_DERIVED = {"created", "modified", "created_low_copy", "created_low_xor_1", "created_low_xor_2", "created_low_xor_3",
                "file_code", "created_copy"}


def runs(a, b, lo, hi):
    out, i = [], lo
    while i < hi:
        if a[i] != b[i]:
            j = i
            while j + 1 < hi and a[j + 1] != b[j + 1]:
                j += 1
            out.append((i, j + 1 - i))
            i = j + 1
        else:
            i += 1
    return out


def field_of(a1, a2, off):
    for name, o, n in fields.header_fields(a1, a2):
        if o <= off < o + n:
            return name
    return "hors champ"


def main(argv):
    a, b = (open(p, "rb").read() for p in argv[1:3])
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else 40
    ha, hb = I.parse_header(a), I.parse_header(b)
    a1, a2 = fields.header_params(a)
    print(f"== en-tete ({os.path.basename(argv[1])} / {os.path.basename(argv[2])})")
    hl = min(ha.header_length, hb.header_length, len(a), len(b))
    for off, n in runs(a, b, 0, hl):
        f = field_of(a1, a2, off)
        tag = "  [derive de l'horodatage]" if f in TIME_DERIVED else ""
        print(f"  {off:#06x} +{n:<3} {f:<22} {a[off:off + n].hex()} / {b[off:off + n].hex()}{tag}")
    pa, pb = I.parse_pages(a, ha), I.parse_pages(b, hb)
    w = 8 if ha.u64 else 4
    for k in range(min(len(pa), len(pb))):
        oa, ta, bca, sca = pa[k]
        ob, tb, bcb, scb = pb[k]
        d = runs(a, b, oa, oa + ha.page_length) if ha.page_length == hb.page_length else []
        print(f"== page {k}: type {ta:#06x}/{tb:#06x}, blocs {bca}/{bcb}, sous-en-tetes {sca}/{scb}, {sum(n for _, n in d)} octet(s) differents")
        if sca and scb:
            for i, ((o1, l1, c1, t1), (o2, l2, c2, t2)) in enumerate(zip(I.pointers(a, ha, oa, sca), I.pointers(b, hb, ob, scb))):
                if (l1, c1, t1) != (l2, c2, t2):
                    print(f"  sous-en-tete {i}: longueur/compression/type {l1},{c1},{t1} / {l2},{c2},{t2}")
                    continue
                if l1 == 0:
                    continue
                s1, s2 = a[oa + o1: oa + o1 + l1], b[ob + o2: ob + o2 + l2]
                sg, _ = I.signature(a, ha, oa, o1)
                kind = I.SIGS.get(sg, "?")
                diffs = runs(s1, s2, 0, l1)
                for off, n in diffs[:limit]:
                    print(f"  sous-en-tete {i} {kind} +{off:#05x} +{n:<3} {s1[off:off + n].hex()} / {s2[off:off + n].hex()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
