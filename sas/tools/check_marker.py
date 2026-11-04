#!/usr/bin/env python3
"""Decode et verifie la page marqueur 0x9000 des tables compressees (hypothese de rea_output/15_compression.md, 5.x).

Usage : python3 -I rea_output/tools/check_marker.py fichier.sas7bdat [...]   (affiche un resume par fichier, code 1 si un ecart)

Modele verifie (64 bits little endian) :
  - la page marqueur suit la premiere page de donnees (page 0) ; type 0x9000 ;
  - blocs = sous-en-tetes + 1 ; sous-en-tetes = nombre de pages de donnees (hors marqueur) ;
  - octet +24 de la page = 1 ; zone des pointeurs de sous-en-tetes a zero ;
  - A = min(longueur de page, 32767) ; la zone des enregistrements est [A - 18*n, A) ; champ u16 a +38 = A - 18*n - 48 ;
  - n enregistrements de 18 octets, dans l'ordre DECROISSANT des pages de donnees :
      u64 BIG endian  : nombre cumule de lignes jusqu'a cette page incluse (pas de limite a 65535)
      u64 little endian : numero de la page dans le fichier (base 1, marqueur compte)
      u16 little endian : indice du dernier sous-en-tete de la page (nombre de blocs - 1)
"""
import struct
import sys


def S_chk(pl, n):
    return min(pl, 32767) - 18 * n + 6


def analyse(path):
    b = open(path, "rb").read()
    if b[32] != 0x33 or b[37] != 1:
        return None, "non 64 bits little endian"
    a1 = 4
    hl = struct.unpack_from("<I", b, 196 + a1)[0]
    pl = struct.unpack_from("<I", b, 200 + a1)[0]
    pc = struct.unpack_from("<Q", b, 204 + a1)[0]
    pages = []
    for k in range(pc):
        p = b[hl + k * pl: hl + (k + 1) * pl]
        t, bc, sc, fld = struct.unpack_from("<HHHH", p, 32)
        pages.append((p, t, bc, sc, fld))
    marks = [k for k, x in enumerate(pages) if x[1] == 0x9000]
    if not marks:
        return None, "pas de page 0x9000"
    errs = []
    if marks != [1]:
        errs.append(f"marqueur en pages {marks} (attendu [1])")
    k = marks[0]
    p, t, bc, sc, fld = pages[k]
    data = [i for i in range(pc) if i != k]
    n = len(data)
    if fld != S_chk(pl, n) - 54:
        errs.append(f"champ +38={fld} attendu {S_chk(pl, n) - 54}")
    if sc != n:
        errs.append(f"sous-en-tetes={sc} attendu {n}")
    if bc != sc + 1:
        errs.append(f"blocs={bc} attendu {sc + 1}")
    if struct.unpack_from("<Q", p, 24)[0] != 1:
        errs.append("octet +24 different de 1")
    A = min(pl, 32767)
    S = A - 18 * n
    if any(p[40: S - 1]):
        pass
    got = []
    cum = 0
    for j, pg in enumerate(reversed(data)):
        r = S + 18 * j
        rows = int.from_bytes(p[r: r + 8], "big")
        num = int.from_bytes(p[r + 8: r + 16], "little")
        last = int.from_bytes(p[r + 16: r + 18], "little")
        got.append((rows, num, last))
    exp = []
    # lignes par page de donnees : page 0 = blocs - 12 ; autres = blocs  (12 sous-en-tetes de metadonnees sur la page 0)
    return dict(path=path, pl=pl, hl=hl, pc=pc, n=n, fld=fld, S=S, A=A, got=got, blocs=[pages[i][2] for i in data], errs=errs, p=p), None


def main(argv):
    bad = 0
    for f in argv[1:]:
        r, e = analyse(f)
        if r is None:
            print(f"{f}: {e}")
            continue
        got, blocs = r["got"], r["blocs"]
        # attendu : pages dans l'ordre decroissant ; numero 1-base = indice de page + 1
        pages_idx = [i for i in range(r["pc"]) if i != 1]
        errs = list(r["errs"])
        for j, i in enumerate(reversed(pages_idx)):
            rows, num, last = got[j]
            if num != i + 1:
                errs.append(f"triplet {j}: page {num} attendu {i + 1}")
            if last != blocs[len(pages_idx) - 1 - j] - 1:
                errs.append(f"triplet {j}: dernier indice {last} attendu {blocs[len(pages_idx) - 1 - j] - 1}")
        # cumul decroissant : le premier triplet (dernier en page) porte le total ; les lignes cumulees sont croissantes avec l'indice de page
        cums = [g[0] for g in reversed(got)]
        if any(cums[i] >= cums[i + 1] for i in range(len(cums) - 1)):
            errs.append(f"cumuls non croissants {cums}")
        d = r["fld"] - r["S"]
        print(f"{f.split('/')[-1]}: P={r['pl']} pages={r['pc']} n={r['n']} cumul(dernier)={cums[-1]} champ+38-debut={d} {'OK' if not errs else 'ECART ' + '; '.join(errs)}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
