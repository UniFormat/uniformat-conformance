#!/usr/bin/env python3
"""Extrait du corpus les vecteurs (ligne brute, ligne compressee) pour COMPRESS=CHAR (RLE) et COMPRESS=BINARY (RDC).

Usage : python3 -I rea_output/tools/make_vectors.py <dossier corpus> <dossier de sortie>
Pour chaque fichier compresse du corpus (litteral SASYZCRL ou SASYZCR2 dans le bloc de texte) :
  * les lignes compressees sont les pointeurs de sous-en-tete de type 1 dont l'octet de compression a le bit 2 (valeurs vues : 4, 6, 13) ;
  * les lignes brutes stockees comme sous-en-tetes sont les pointeurs de type 1, d'octet de compression 0, 2 ou 9, dont la
    longueur est celle de la ligne et la signature inconnue ;
  * la ligne brute de reference vient de la table _no de meme nom (tronquee a la longueur de ligne du fichier compresse :
    SAS aligne sur 8 les lignes non compressees seulement).
Sortie : <sortie>/char.tsv, binary.tsv (un vecteur par ligne) ; format decrit dans compression_vectors/README.md.
"""
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inspect_sas7bdat as I  # noqa: E402
import ref_reader  # noqa: E402

ALL_ROWS = ("compression_runs",)  # famille de bornes de longueur : toutes les lignes sont gardees
MAX_PER_FILE = 12


def rows_of(path, raw_row_length=None):
    """(sf, [(kind, octets)]) : lignes brutes d'une table non compressee, ou lignes (compression, octets) d'une compressee."""
    b = open(path, "rb").read()
    sf = ref_reader.SasFile(b)
    h = I.parse_header(b)
    w = sf.int_len
    po = 32 if sf.u64 else 16
    ps = 24 if sf.u64 else 12
    out = []
    for off, pt, bc, sc in I.parse_pages(b, h):
        if sf.compression:
            if pt & 0xFF00 != 0:
                continue
            for o, l, c, t in I.pointers(b, h, off, sc):
                if c & 4 and t == 1 and l:
                    out.append(("compressed", bytes(b[off + o: off + o + l])))
                elif c != 1 and t == 1 and l == sf.row_length and l >= 2 * w:
                    sg, _ = I.signature(b, h, off, o)
                    if I.SIGS.get(sg) is None:
                        out.append(("raw", bytes(b[off + o: off + o + l])))
        else:
            k = pt & 0xF00
            if k not in (0x100, 0x200):
                continue
            start = off + (((po + 8 + sc * ps) + 7) // 8 * 8 if k == 0x200 else po + 8)
            n = bc - (sc if k == 0x200 else 0)
            for i in range(n):
                out.append(("raw", bytes(b[start + i * sf.row_length: start + (i + 1) * sf.row_length])))
    return sf, out


def pick(n, name):
    if any(name.startswith(a) for a in ALL_ROWS) or n <= MAX_PER_FILE:
        return list(range(n))
    step = (n - 1) / (MAX_PER_FILE - 1)
    return sorted({round(i * step) for i in range(MAX_PER_FILE)})


def main(argv):
    corpus, outdir = argv[1], argv[2]
    os.makedirs(outdir, exist_ok=True)
    lines = {"CHAR": [], "BINARY": []}
    count = 0
    for path in sorted(glob.glob(os.path.join(corpus, "files", "*", "*.sas7bdat")) + glob.glob(os.path.join(corpus, "external", "*", "*.sas7bdat"))):
        sf, comp = rows_of(path)
        if not sf.compression:
            continue
        algo = "CHAR" if sf.compression == "RLE" else "BINARY"
        base = os.path.basename(path)[: -len(".sas7bdat")]
        src_rel = os.path.relpath(path, corpus)
        reference = None
        for suf in ("_char", "_binary"):
            if base.endswith(suf):
                ref_path = path[: -len(suf + ".sas7bdat")] + "_no.sas7bdat"
                if os.path.exists(ref_path):
                    _, reference = rows_of(ref_path)
        for i in pick(len(comp), base):
            kind, data = comp[i]
            raw = reference[i][1][: sf.row_length] if reference and i < len(reference) else None
            category = ("externe-sans-brut" if raw is None else
                        "bornes-de-longueur" if base.startswith("compression_runs") else
                        "incompressible" if base.startswith("compression_noise") else
                        "ligne-quasi-uniforme" if base.startswith(("compression_zeros", "compression_blank")) else "corpus")
            lines[algo].append("\t".join([f"{algo.lower()}-{count:04d}", algo, src_rel, str(i), kind, category, str(sf.row_length),
                                          raw.hex() if raw is not None else "", data.hex()]))
            count += 1
    for algo, rows in lines.items():
        with open(os.path.join(outdir, algo.lower() + ".tsv"), "w", encoding="utf-8") as f:
            f.write("id\talgorithme\tfichier\tligne\tstockage\tcategorie\tlongueur_ligne\tbrut_hex\tstocke_hex\n")
            f.write("\n".join(rows) + "\n")
        print(f"{algo}: {len(rows)} vecteurs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
