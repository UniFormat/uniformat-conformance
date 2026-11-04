#!/usr/bin/env python3
"""Construit la table code d'encodage -> nom SAS -> encodage standard (WHATWG / encoding_rs) de 30_formats_encodages.md.

Entrees : evidence/encodages_sources_publiques.tsv (tables de ReadStat, pandas, Parso : HYPOTHESES publiques), codes observes dans
les en-tetes du corpus (calcules ici), correspondance vers les noms WHATWG ecrite a la main ci-dessous.
Usage : python3 -I rea_output/tools/make_encoding_table.py <dossier corpus> > fragment.md
Verifie aussi que tout code observe dans le corpus figure dans la table (sortie code 1 sinon).
"""
import collections
import csv
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_reader  # noqa: E402

ALIAS = {"latin1": "iso-8859-1", "latin2": "iso-8859-2", "latin3": "iso-8859-3", "latin4": "iso-8859-4", "cyrillic": "iso-8859-5",
         "arabic": "iso-8859-6", "greek": "iso-8859-7", "hebrew": "iso-8859-8", "latin5": "iso-8859-9", "latin6": "iso-8859-10",
         "latin9": "iso-8859-15", "ascii": "us-ascii", "big5": "big-5", "x-iso-8859-11": "iso-8859-11", "shift_jis": "cp932",
         "shift-jis": "cp932", "ms932": "cp932", "euc-cn": "gb18030"}
# nom canonique -> (libelle WHATWG / encoding_rs, remarque) ; None = pas d'equivalent WHATWG
WHATWG = {
    "utf-8": ("utf-8", ""), "us-ascii": ("windows-1252", "ASCII strict absent de WHATWG : le label « ascii » donne windows-1252"),
    "iso-8859-1": ("windows-1252", "WHATWG remplace ISO-8859-1 par windows-1252 (octets 0x80 à 0x9F différents)"),
    "iso-8859-2": ("iso-8859-2", ""), "iso-8859-3": ("iso-8859-3", ""), "iso-8859-4": ("iso-8859-4", ""), "iso-8859-5": ("iso-8859-5", ""),
    "iso-8859-6": ("iso-8859-6", ""), "iso-8859-7": ("iso-8859-7", ""), "iso-8859-8": ("iso-8859-8", ""),
    "iso-8859-9": ("windows-1254", "WHATWG remplace ISO-8859-9 par windows-1254"), "iso-8859-10": ("iso-8859-10", ""),
    "iso-8859-11": ("windows-874", "WHATWG remplace ISO-8859-11 par windows-874"), "iso-8859-13": ("iso-8859-13", ""),
    "iso-8859-14": ("iso-8859-14", ""), "iso-8859-15": ("iso-8859-15", ""), "cp874": ("windows-874", ""), "cp866": ("ibm866", ""),
    "windows-1250": ("windows-1250", ""), "windows-1251": ("windows-1251", ""), "windows-1252": ("windows-1252", ""),
    "windows-1253": ("windows-1253", ""), "windows-1254": ("windows-1254", ""), "windows-1255": ("windows-1255", ""),
    "windows-1256": ("windows-1256", ""), "windows-1257": ("windows-1257", ""), "windows-1258": ("windows-1258", ""),
    "macroman": ("macintosh", ""), "maccyrillic": ("x-mac-cyrillic", ""), "cp950": ("big5", "Big5 de WHATWG = cp950 étendu"),
    "big-5": ("big5", ""), "gb18030": ("gb18030", ""), "cp936": ("gbk", "gbk de WHATWG = cp936 étendu"), "euc-jp": ("euc-jp", ""),
    "cp932": ("shift_jis", "Shift_JIS de WHATWG = windows-31j (cp932)"), "euc-kr": ("euc-kr", "euc-kr de WHATWG = cp949"), "cp949": ("euc-kr", "euc-kr de WHATWG = cp949"),
    "iso-2022-jp": ("iso-2022-jp", ""),
}


def canon(name):
    n = name.strip().lower().replace("_", "-")
    if n.startswith("x-ibm"):
        n = "cp" + n[5:]
    elif n.startswith("ibm"):
        n = "cp" + n[3:].lstrip("0")
    n = n.replace("x-mac", "mac")
    if n.startswith("mac") and n[3:] in ("roman", "cyrillic"):
        n = n.replace("-", "")
    for a, b in (("x-windows-949", "cp949"), ("x-windows-950", "cp950"), ("x-euc-tw", "euc-tw"), ("iso2022-", "iso-2022-"), ("x-iso2022-cn-gb", "iso-2022-cn"),
                 ("x-iso2022-cn-cns", "iso-2022-cn-ext"), ("latin8", "iso-8859-14"), ("iso8859-", "iso-8859-"), ("x-mswin-936", "cp936"),
                 ("windows-936", "cp936"), ("mac-", "mac"), ("macromania", "macromanian"), ("maciceland", "maciceland")):
        if n.startswith(a) or n == a:
            n = b + n[len(a):] if n.startswith(a) else b
    if n.startswith("cp125") and len(n) == 6:
        n = "windows-" + n[2:]
    return ALIAS.get(n, n)


def observed(corpus):
    seen = collections.defaultdict(list)
    for p in sorted(glob.glob(os.path.join(corpus, "files", "*", "*.sas7bdat")) + glob.glob(os.path.join(corpus, "external", "*", "*.sas7bdat"))):
        try:
            sf = ref_reader.SasFile(open(p, "rb").read())
        except Exception:
            continue
        seen[sf.encoding_code].append(os.path.relpath(p, corpus))
    return seen


def main(argv):
    corpus = argv[1]
    rows = list(csv.DictReader(open(os.path.join(HERE, "..", "evidence", "encodages_sources_publiques.tsv"), encoding="utf-8"), delimiter="\t"))
    obs = observed(corpus)
    codes = {int(r["code"]): r for r in rows}
    missing = [c for c in obs if c not in codes]
    out = ["| code | ReadStat | pandas | Parso | accord des 3 sources | standard (WHATWG / `encoding_rs`) | fichiers du corpus | confiance |", "|---|---|---|---|---|---|---|---|"]
    for c in sorted(codes):
        r = codes[c]
        names = [canon(r[k]) for k in ("readstat", "pandas", "parso") if r[k]]
        agree = ("1 source seulement" if len(names) == 1 else "oui (3 sources)" if len(set(names)) == 1 and len(names) == 3 else
                 f"oui ({len(names)} sources)" if len(set(names)) == 1 else "NON : " + " / ".join(sorted(set(names))))
        ref = next((r[k] for k in ("readstat", "pandas", "parso") if r[k]), "")
        wh = WHATWG.get(canon(ref))
        std = f"`{wh[0]}`" + (f" ({wh[1]})" if wh[1] else "") if wh else "aucun équivalent WHATWG (IANA : " + (ref or "?") + ")"
        files = obs.get(c)
        proof = f"{len(files)} fichier(s), ex. `{files[0]}`" if files else "aucun"
        conf = "inféré (fichiers + sources publiques)" if files and c in (20, 29, 62, 138) else ("inféré (fichiers, contenu non discriminant)" if files else "inféré (sources publiques seules)")
        out.append(f"| {c} | {r['readstat'] or '—'} | {r['pandas'] or '—'} | {r['parso'] or '—'} | {agree} | {std} | {proof} | {conf} |")
    print("\n".join(out))
    for c in sorted(obs):
        print(f"<!-- code observé {c} : {len(obs[c])} fichiers -->")
    if missing:
        print("CODES ABSENTS DE LA TABLE :", missing, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
