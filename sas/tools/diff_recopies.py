#!/usr/bin/env python3
"""Comparaison octet a octet d'un fichier SAS du corpus avec le fichier equivalent ecrit par ref_writer.py (tache 2.2).

Usage : python3 -I rea_output/tools/diff_recopies.py <fichier.sas7bdat> [...]     (DIFF_WRITER=driver : rejoue avec le driver, J6)
Le fichier est relu (ref_reader.py), reecrit avec le meme schema et les memes lignes, puis compare : en-tete de fichier, en-tete de page 0, puis
chaque sous-en-tete apparie par signature. Chaque plage d'octets differente est listee avec son nom ; une plage non listee dans EXPLIQUE est
un champ « recopie sans explication » (code de sortie 1).
"""
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_reader  # noqa: E402
import ref_writer as W  # noqa: E402

# plages dont la difference est attendue et expliquee (20_ecriture.md section 5) : (zone, debut, fin) ; zone = "header", "page0" ou nom du sous-en-tete
EXPLIQUE = {
    "header": [(168, 184, "dates (libre)"), (296, 328, "zone derivee de la date (calcule)"), (328, 332, "code de fichier (calcule, aleatoire)"),
               (336, 344, "date (libre)"), (92, 124, "nom de table (libre)"), (248, 264, "version du systeme (libre)"), (280, 286, "machine (libre)"),
               (208, 216, "nombre de pages (calcule)"), (84, 92, "SAS FILE"), (0, 4, "")],
    "page0": [(0, 4, "signature de page (calcule)"), (24, 32, "free_bytes (libre)"), (32, 40, "compteurs de page (calcule)")],
    "RowSize": [(0x58, 0x60, "+0x58 non ecrit (libre)"), (0x1B8, 0x1BC, "signature de page (libre)"), (0x2FE, 0x300, "+0x2FE (libre)"),
                (0x10, 0x18, "+0x10 (libre)"), (0x78, 0x80, "capacite (calcule)"), (0x200, 0x250, "localisateurs (calcule)"),
                (0x2EE, 0x2F0, "longueur max des noms (libre)"), (0x60, 0x68, "+0x60 (libre)"), (0x2F8, 0x300, "+0x2F8..+0x2FF (libre)")],
    "SubheaderCounts": [(0x08, 0x10, "taille du texte (calcule)"), (0x10, 0x20, "compteurs d'en-tete (constante)"), (0xF8, 0x118, "entree ColumnList (absente)"),
                        (0x78, 0x98, "entree 0 : positions (calcule)"), (0xA0, 0xC0, "entree 1 : positions (calcule)"), (0xC8, 0xE8, "entree 2 : positions (calcule)")],
}


def regions(a, b):
    out, i, n = [], 0, min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def subs_of(data, hl, ps):
    t, bc, sc = struct.unpack_from("<HHH", data, hl + 32)
    out = {}
    for i in range(sc):
        o, ln, c, ty = struct.unpack_from("<QQBB", data, hl + 40 + 24 * i)
        if ln:
            sub = data[hl + o: hl + o + ln]
            out.setdefault(sub[:4].hex(), []).append(sub)
    return out


NAMES = {"f7f7f7f7": "RowSize", "f6f6f6f6": "ColumnSize", "00fcffff": "SubheaderCounts", "fdffffff": "ColumnText", "ffffffff": "ColumnName", "fcffffff": "ColumnAttributes",
         "feffffff": "ColumnList", "fefbffff": "FormatAndLabel"}


def main(argv):
    bad = 0
    for path in argv[1:]:
        real = open(path, "rb").read()
        sf = ref_reader.SasFile(real, raw=True)
        cols = []
        for c in sf.columns:
            col = W.Col(c.name, c.type, c.length, label=c.label or "")
            if c.format:
                col.fmt = (c.format, c.fmt_width, c.fmt_dec)
            if c.informat:
                col.informat = (c.informat, c.inf_width, c.inf_dec)
            cols.append(col)
        compress = "CHAR" if sf.compression == "RLE" else "BINARY" if sf.compression == "RDC" else None
        with tempfile.TemporaryDirectory() as td:
            mine_path = os.path.join(td, "w.sas7bdat")
            if os.environ.get("DIFF_WRITER") == "driver":  # J6 : rejouer la comparaison avec le driver (uniformat_io.sas.write_sas)
                from validate_write_driver import driver_write
                driver_write(mine_path, cols, [list(r) for r in sf.rows], compress=compress, page_length=sf.page_length, enc_code=sf.encoding_code, seed=1)
            else:
                W.write(mine_path, cols, [list(r) for r in sf.rows], compress=compress, page_length=sf.page_length, enc_code=sf.encoding_code, codec=sf.codec or "utf-8", seed=1)
            mine = open(mine_path, "rb").read()
        print(f"== {path.split('corpus/')[-1]} : {len(sf.rows)} lignes, {len(cols)} colonnes, compression={compress}")
        hl = sf.header_length
        todo = [("header", real[:hl], mine[:hl])]
        todo.append(("page0", real[hl: hl + 40], mine[hl: hl + 40]))
        ra, rb = subs_of(real, hl, sf.page_length), subs_of(mine, hl, sf.page_length)
        for sig, name in NAMES.items():
            la, lb = ra.get(sig, []), rb.get(sig, [])
            if len(la) != len(lb):
                print(f"   {name}: {len(la)} sous-en-tete(s) dans le fichier SAS, {len(lb)} dans le fichier ecrit")
            for x, y in zip(la, lb):
                if len(x) != len(y):
                    print(f"   {name}: longueur {len(x)} (SAS) / {len(y)} (ecrit)")
                todo.append((name, x, y))
        for zone, x, y in todo:
            if zone in ("ColumnName", "ColumnAttributes", "FormatAndLabel", "ColumnSize", "ColumnText") and len(x) != len(y):
                continue
            for a, b in regions(x, y):
                why = next((w for (s, e, w) in EXPLIQUE.get(zone, []) if s <= a and b <= e), None)
                if why is None:
                    bad += 1
                    why = "NON EXPLIQUE"
                print(f"   {zone:16} +{a:#06x}..{b:#06x}  SAS={x[a:b][:12].hex()}  ecrit={y[a:b][:12].hex()}  {why}")
    print("champs recopies sans explication :", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
