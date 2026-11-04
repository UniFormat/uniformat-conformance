#!/usr/bin/env python3
"""Verificateur d'encodage : decode les colonnes caractere des fichiers non UTF-8 du corpus avec l'encodage deduit du code d'en-tete
(table de 30_formats_encodages.md, section 6) et compare au CSV de reference (texte affiche par l'oracle, converti en UTF-8).

Usage : python3 -I rea_output/tools/check_encoding.py <dossier corpus>
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_csv  # noqa: E402
import ref_reader  # noqa: E402


def main(root):
    bad = n = 0
    for p in sorted(glob.glob(os.path.join(root, "files", "*", "*.sas7bdat")) + glob.glob(os.path.join(root, "external", "*", "*.sas7bdat"))):
        sf = ref_reader.SasFile(open(p, "rb").read(), raw=True)
        if sf.encoding_code == 20 or not compare_csv.csv_for(p):
            continue
        has_text = any(c.type == "c" for c in sf.columns)
        if not has_text:
            continue
        n += 1
        compare_csv.notes.clear()
        errs = compare_csv.compare(p)
        note = "; ".join(sorted(compare_csv.notes))
        bad += bool(errs)
        print(f"code {sf.encoding_code:3} {os.path.relpath(p, root)} : {'ECART ' + errs[0] if errs else 'texte identique a l oracle'}{' [' + note + ']' if note else ''}")
    print(f"--- {n} fichiers non UTF-8 avec colonnes caractere, {bad} avec ecart")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
