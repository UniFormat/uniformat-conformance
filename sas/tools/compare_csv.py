#!/usr/bin/env python3
"""Compare la sortie de ref_reader.py au CSV de reference de chaque fichier du corpus.

Usage : python3 -I rea_output/tools/compare_csv.py <dossier racine contenant files/ ou external/> [motif de nom]
Pour chaque fichier .sas7bdat ayant un .csv voisin :
  - colonnes mises en correspondance par nom (l'ordre de l'en-tete du CSV n'est pas celui des variables) ;
  - numeriques : meme valeur flottante (le CSV est ecrit en BEST32.) ou meme code de manquant (. _ A-Z) ;
  - caracteres : meme texte, blancs de fin ignores.
Sortie : une ligne par fichier (OK ou nombre d'ecarts + premier ecart), puis un total. Code retour 1 si ecart.
"""
import csv
import glob
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util  # noqa: E402

_path = os.environ.get("REF_READER") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_reader.py")
_spec = importlib.util.spec_from_file_location("ref_reader_under_test", _path)
ref_reader = importlib.util.module_from_spec(_spec)  # lecteur teste : variable d'environnement REF_READER (defaut ref_reader.py)
_spec.loader.exec_module(ref_reader)

NUL = "\ue000"
notes = set()
MISSING = {"."} | {"_"} | {chr(c) for c in range(65, 91)}


def read_csv(path):
    raw = open(path, "rb").read()
    utf8 = True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text, utf8 = raw.decode("latin-1"), False
    text = text.replace("\x00", NUL)  # le module csv refuse les octets nuls
    rows = list(csv.reader(text.splitlines(keepends=True)))
    return rows[0], rows[1:], utf8


def same_number(ref, got):
    if ref == "":  # certains CSV publics n'ecrivent pas le code du manquant
        return isinstance(got, str)
    if isinstance(got, str):  # code de manquant
        return ref == got
    if ref in MISSING:
        return False
    try:
        x = float(ref)
    except ValueError:
        return False
    # BEST32. n'ecrit que 14 chiffres significatifs pour certaines valeurs extremes (1.7976931348623E308)
    return x == got or math.isclose(x, got, rel_tol=1e-13, abs_tol=0.0)


def csv_for(sas_path):
    """CSV voisin ; pour les fichiers datareader testN, le CSV du jeu A (test1.csv, N <= 15) ou B (test2.csv)."""
    d = os.path.dirname(sas_path)
    name = os.path.basename(sas_path)
    if os.path.basename(d) == "datareader" and name.startswith("test"):
        # les fichiers testN partagent les CSV test1.csv (jeu A, N <= 15) et test2.csv (jeu B, N >= 16)
        n = int(name[4:-len(".sas7bdat")])
        alt = os.path.join(d, "test1.csv" if n <= 15 else "test2.csv")
        return alt if os.path.exists(alt) else None
    own = sas_path[: -len(".sas7bdat")] + ".csv"
    return own if os.path.exists(own) else None


def compare(sas_path):
    csv_path = csv_for(sas_path)
    sf = ref_reader.SasFile(open(sas_path, "rb").read(), raw=True)
    head, rows, utf8 = read_csv(csv_path)
    errs = []
    notes.clear()
    names = [c.name for c in sf.columns]
    if sorted(head) != sorted(names):
        return [f"colonnes differentes : csv={head[:5]} lecteur={names[:5]}"]
    if len(rows) != len(sf.rows):
        errs.append(f"nombre de lignes : csv={len(rows)} lecteur={len(sf.rows)}")
    idx = {n: j for j, n in enumerate(names)}
    for r, (crow, srow) in enumerate(zip(rows, sf.rows)):
        for k, name in enumerate(head):
            c, v = crow[k], srow[idx[name]]
            col = sf.columns[idx[name]]
            if col.type == "n":
                ok = same_number(c, v)
            else:  # v est en octets : decodage selon l'encodage du fichier si le CSV est en UTF-8, sinon comparaison octet a octet
                txt = v.decode(sf.codec or "latin-1", "replace") if utf8 else v.decode("latin-1")
                ok = c.rstrip(" ") == txt.replace("\x00", NUL).rstrip(" ")
                if not ok and utf8 and v.decode("utf-8", "replace").rstrip(" ") == c.rstrip(" "):
                    ok = True  # octets UTF-8 sous un code d'encodage different (voir 10_format_sas7bdat.md, encodage)
                    notes.add(f"octets UTF-8 malgre le code d'encodage {sf.encoding_code}")
            if not ok:
                errs.append(f"ligne {r + 1} colonne {name} : csv={c!r} lecteur={v!r}")
                if len(errs) > 5:
                    return errs
    return errs


def main(argv):
    root = argv[1]
    pat = argv[2] if len(argv) > 2 else ""
    files = sorted(glob.glob(os.path.join(root, "**", "*.sas7bdat"), recursive=True))
    total = bad = skipped = 0
    for p in files:
        if pat not in os.path.basename(p) or not csv_for(p):
            continue
        total += 1
        try:
            errs = compare(p)
        except Exception as e:  # noqa: BLE001
            errs = [f"exception {type(e).__name__}: {e}"]
        if errs is None:
            skipped += 1
            print(f"SKIP  {os.path.basename(p)} (compresse)")
        elif errs:
            bad += 1
            print(f"ECART {os.path.basename(p)} : {errs[0]}" + (f" (+{len(errs) - 1})" if len(errs) > 1 else ""))
        else:
            print(f"OK    {os.path.basename(p)}" + (f"  [{'; '.join(sorted(notes))}]" if notes else ""))
    print(f"--- {total} fichiers, {total - bad - skipped} OK, {skipped} compresses (ignores), {bad} avec ecart")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
