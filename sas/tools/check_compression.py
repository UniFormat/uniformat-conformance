#!/usr/bin/env python3
"""Verifications de la compression (rea_output/15_compression.md) sur le corpus.

Usage : python3 -I rea_output/tools/check_compression.py <dossier corpus> <mode>
  mode corpus   : pour chaque table generee dont la compression est effective, compare toutes les lignes lues par
                  ref_reader.py (decompression RLE ou RDC) a celles de la table _no de meme nom ;
  mode externes : fichiers publics compresses : compare au CSV de reference quand il existe, sinon verifie le nombre de lignes ;
  mode pointeurs: pour chaque fichier compresse, types de pages et pointeurs (compression, type) par page.
"""
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_csv  # noqa: E402
import inspect_sas7bdat as I  # noqa: E402
import ref_reader  # noqa: E402


def load(path, **kw):
    return ref_reader.SasFile(open(path, "rb").read(), **kw)


def corpus(root):
    bad = 0
    tot = collections.Counter()
    for path in sorted(glob.glob(os.path.join(root, "files", "*", "*.sas7bdat"))):
        base = os.path.basename(path)[:-9]
        if not base.endswith(("_char", "_binary")):
            continue
        sf = load(path)
        if not sf.compression:
            continue
        ref = load(path[: -len("_char.sas7bdat" if base.endswith("_char") else "_binary.sas7bdat")] + "_no.sas7bdat")
        ok = sf.rows == ref.rows and len(sf.rows) == sf.row_count
        raw = 0
        tot[sf.compression] += len(sf.rows)
        bad += not ok
        print(f"{sf.compression} {base} : {len(sf.rows)} lignes, {'identiques a la table _no' if ok else 'ECART'}")
    print(f"--- lignes decompressees : {dict(tot)} ; {bad} fichier(s) avec ecart")
    return 1 if bad else 0


def externes(root):
    bad = 0
    n = 0
    for path in sorted(glob.glob(os.path.join(root, "external", "*", "*.sas7bdat"))):
        sf = load(path, raw=True)
        if not sf.compression:
            continue
        n += 1
        csvp = compare_csv.csv_for(path)
        if csvp:
            errs = compare_csv.compare(path)
            ok, how = not errs, "CSV de reference"
        else:
            ok, how = len(sf.rows) == sf.row_count, "nombre de lignes (pas de CSV)"
        bad += not ok
        print(f"{sf.compression} {os.path.relpath(path, root)} : {len(sf.rows)} lignes, {how}, {'OK' if ok else 'ECART'}")
    print(f"--- {n} fichiers publics compresses, {bad} avec ecart")
    return 1 if bad else 0


def pointeurs(root):
    for path in sorted(glob.glob(os.path.join(root, "files", "*", "*.sas7bdat")) + glob.glob(os.path.join(root, "external", "*", "*.sas7bdat"))):
        b = open(path, "rb").read()
        sf = ref_reader.SasFile(b)
        if not sf.compression:
            continue
        h = I.parse_header(b)
        parts = []
        for k, (off, pt, bc, sc) in enumerate(I.parse_pages(b, h)):
            cnt = collections.Counter((c, t) for o, l, c, t in I.pointers(b, h, off, sc))
            parts.append(f"p{k}:{pt:#06x} blocs={bc} ptr=" + ",".join(f"({c},{t})x{v}" for (c, t), v in sorted(cnt.items())))
        print(f"{sf.compression} {os.path.relpath(path, root)} row_length={sf.row_length} " + " | ".join(parts))
    return 0


def litteraux(root):
    """Position absolue (fichier) du littéral SASYZCRL / SASYZCR2 dans chaque fichier qui le contient."""
    n = 0
    for path in sorted(glob.glob(os.path.join(root, "files", "*", "*.sas7bdat")) + glob.glob(os.path.join(root, "external", "*", "*.sas7bdat"))):
        b = open(path, "rb").read()
        for lit, algo in ((b"SASYZCRL", "RLE"), (b"SASYZCR2", "RDC")):
            pos = b.find(lit)
            if pos >= 0:
                n += 1
                print(f"{algo} {lit.decode()} {os.path.relpath(path, root)} offset={pos} (page 0 + {pos - I.parse_header(b).header_length:#x})")
    print(f"--- {n} fichiers contenant un littéral de compression")
    return 0


if __name__ == "__main__":
    fn = {"corpus": corpus, "externes": externes, "pointeurs": pointeurs, "litteraux": litteraux}[sys.argv[2]]
    sys.exit(fn(sys.argv[1]))
