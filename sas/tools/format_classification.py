#!/usr/bin/env python3
"""Classification des formats et informats (nom -> categorie logique -> type Arrow) et inventaire de 30_formats_encodages.md.

Usage : python3 -I rea_output/tools/format_classification.py [--table | --inventaire | --check]
  --table       fragment markdown de la table de classification (en tete du livrable)
  --inventaire  fragment markdown de l'inventaire (candidats de la documentation publique + presence dans l'oracle)
  --check       verifie que tout nom inventorie figure dans la classification (code retour 1 sinon)
Source des noms : corpus/gen/fmt_candidates.py (documentation publique SAS 9.4) ; presence : evidence/fmt_existence.log (oracle sas_small).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "corpus", "gen"))
import fmt_candidates as C  # noqa: E402

DAYS = "jours depuis 1960-01-01"
SECS = "secondes depuis 1960-01-01T00:00:00"
TOD = "secondes depuis minuit (peut être négative ou ≥ 86400)"

# (motif sur le nom, categorie, type Arrow, epoque / unite, ambiguite)
RULES = [
    (r"(DTDATE|DTMONYY|DTWKDATX|DTYEAR|DTYYQC)", "datetime (formaté en date)", "Timestamp(Second)", SECS, "la valeur stockée est un datetime ; seul l'affichage est une date"),
    (r"(DATETIME|DATEAMPM|NLDATM|ANYDTDTM|MDYAMPM|EURDFDT|E8601DT|E8601DZ|E8601LZ|B8601DT|B8601DZ|B8601LZ)", "datetime", "Timestamp(Second)", SECS, ""),
    (r"TOD", "datetime (formaté en heure)", "Timestamp(Second)", SECS, "ambigu : le format affiche l'heure d'un datetime ; repli : Timestamp(Second)"),
    (r"(TIME|TIMEAMPM|HHMM|HOUR|MMSS|NLTIME|STIMER|ANYDTTME|E8601TM|E8601TZ|B8601TM|B8601TZ)", "heure", "Time64(Microsecond) si 0 ≤ v < 86400, sinon Duration(Second)", TOD, "valeurs négatives et ≥ 24 h admises par SAS (observé : `-1`, `86400`, `90000`)"),
    (r"(DAY|MONTH|YEAR|QTR|QTRR|WEEKDAY|DOWNAME|MONNAME|JULDAY|WEEKU|WEEKV|WEEKW|NLDATEMN|EURDFDWN|EURDFMN|EURDFWKX)", "date (composante affichée)", "Date32", DAYS, "la valeur stockée est une date complète ; le format n'affiche qu'une composante (jour, mois, trimestre…)"),
    (r"(DATE|ANYDTDTE|DDMMYY[BCDNPS]?|MMDDYY[BCDNPS]?|YYMMDD[BCDNPS]?|YYMM[CDNPS]?|MMYY[CDNPS]?|MONYY|YYMON|YYQ[CDNPRSZ]?|YYQR[CDNPS]?|WORDDATE|WORDDATX|WEEKDATE|WEEKDATX|JULIAN|NENGO|MINGUO|PDFDATE|NLDATE|NLDATEYQ|EURDFDD|EURDFDE|EURDFDN|EURDFMY|EURDFWDX|E8601DA|E8601DN|B8601DA|B8601DN|PDJULG|PDJULI)", "date", "Date32", DAYS, ""),
    (r"(BEST|BESTX|BESTD|D|E|WEIGHT|FRACT|NEGPAREN|NEGPARENS|PERCENT|PERCENTN|PERCENTD|COMMA|COMMAX|COMMAXD|DOLLAR|DOLLARX|DOLLARD|DOLLARDX|EURO|EUROX|NLNUM|NLMNY|NLPCT|PVALUE|Z|ZD|NUMX|MGF)", "numérique (échelle fixe `d` si le format porte `.d`)", "Float64 (Decimal128(38, d) en option)", "valeur stockée inchangée (double IEEE)", "le format n'altère pas la valeur : l'échelle `d` est de l'affichage, pas du stockage"),
    (r"(BINARY|HEX|OCTAL|IB|IBR|IEEE|PD|PIB|PIBR|PK|RB|S370FF|S370FIB|S370FPD|ROMAN|SSN|WORDF|WORDS)", "numérique (affiché en binaire, hexadécimal ou texte)", "Float64", "valeur stockée inchangée (double IEEE)", "le format change la représentation affichée, jamais le type stocké"),
]
CHAR_RULES = [(r"\$(CHAR|F|HEX|VARYING|BINARY|OCTAL|QUOTE|REVERJ|REVERS|UPCASE|ASCII|EBCDIC1047|MSGCASE|N)?", "caractère", "Utf8", "—", "décoder avec l'encodage du fichier (voir section encodages)")]
USERDEF = ("format utilisateur (catalogue)", "Float64 ou Utf8 selon le type de la colonne ; Dictionary en option", "—", "le nom ne figure pas dans la liste native : chercher dans le catalogue `.sas7bcat`")


def classify(name):
    n = name.upper()
    if n.startswith("$"):
        for pat, cat, arrow, ep, amb in CHAR_RULES:
            if re.fullmatch(pat, n):
                return cat, arrow, ep, amb
        return USERDEF[0], USERDEF[1], USERDEF[2], USERDEF[3]
    for pat, cat, arrow, ep, amb in RULES:
        if re.fullmatch(pat, n):
            return cat, arrow, ep, amb
    return None


def presence():
    absent_f, absent_i = set(), set()
    for l in open(os.path.join(HERE, "..", "evidence", "fmt_existence.log"), encoding="utf-8", errors="replace"):
        m = re.match(r"ERROR \d+-\d+: The format (\S+) was not found", l)
        if m:
            absent_f.add(m.group(1))
        m = re.match(r"ERROR \d+-\d+: The informat (\S+) was not found", l)
        if m:
            absent_i.add(m.group(1))
    return absent_f, absent_i


def entries():
    af, ai = presence()
    out = []
    for kind, names, ab in (("format", C.NUM_FORMATS + C.CHAR_FORMATS, af), ("informat", C.NUM_INFORMATS + C.CHAR_INFORMATS, ai)):
        for n in names:
            key = n.upper()
            present = key not in ab and not (key == "$" and True and False)
            out.append((n, kind, present))
    return out


def main(argv):
    ent = entries()
    mode = argv[1] if len(argv) > 1 else "--check"
    if mode == "--check":
        missing = [n for n, k, p in ent if classify(n) is None]
        print(f"{len(ent)} noms inventories, {len(missing)} sans classification", missing[:20])
        return 1 if missing else 0
    if mode == "--table":
        print("| nom | format / informat | catégorie logique | type Arrow cible | époque et unité | présent dans l'oracle | ambiguïté et repli |")
        print("|---|---|---|---|---|---|---|")
        for n, k, p in ent:
            cat, arrow, ep, amb = classify(n)
            print(f"| `{n}` | {k} | {cat} | {arrow} | {ep} | {'oui' if p else 'non'} | {amb or '—'} |")
        return 0
    if mode == "--inventaire":
        for kind in ("format", "informat"):
            pres = [n for n, k, p in ent if k == kind and p]
            ab = [n for n, k, p in ent if k == kind and not p]
            print(f"- **{kind}s présents dans `sas_small`** ({len(pres)}) : " + " ".join(f"`{n}`" for n in pres))
            print(f"- **{kind}s documentés mais absents de `sas_small`** ({len(ab)}) : " + " ".join(f"`{n}`" for n in ab))
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
