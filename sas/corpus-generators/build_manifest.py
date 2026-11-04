#!/usr/bin/env python3
"""Genere (ou verifie) corpus/MANIFEST.md.

    python3 -I corpus/gen/build_manifest.py            # ecrit corpus/MANIFEST.md
    python3 -I corpus/gen/build_manifest.py --verify   # recalcule les SHA-256 et controle la couverture

Entrees : corpus/gen/tables.tsv (metadonnees des tables generees), corpus/gen/dropped_long_names.tsv,
corpus/external/EXTERNAL.tsv (provenance des fichiers publics), corpus/out_full/compression_check.tsv
et le contenu reel de corpus/files/ (SAS complet), corpus/files_sas_small/ (sas_small) et corpus/external/.
Aucun fichier n'est interprete : seuls nom, taille et SHA-256 sont calcules.
"""
import csv
import hashlib
import os
import sys

CORPUS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(CORPUS, "MANIFEST.md")
KINDS = {".sas7bdat": "table SAS", ".sas7bcat": "catalogue SAS", ".sas7bndx": "index SAS", ".contents.txt": "sortie PROC CONTENTS",
         ".print.txt": "sortie PROC PRINT", ".csv": "CSV de reference"}
EXTS = (".contents.txt", ".print.txt", ".sas7bdat", ".sas7bcat", ".sas7bndx", ".csv")
# fichiers produits en plus des tables de tables.tsv : nom -> (table de reference, description)
AUX = {
    "formats": ("catalogue_fmtuser_no", "catalogue de formats utilisateur ecrit par PROC FORMAT"),
    "catalogue_cntlout": ("catalogue_fmtuser_no", "export CNTLOUT du catalogue de formats (table)"),
    "catalogue_fmtlib": ("catalogue_fmtuser_no", "PROC FORMAT FMTLIB du catalogue"),
}
SAS_FULL = "SAS 9.4 TS1M7 complet (Linux x86-64) via corpus/gen/run_all.sh full"
SAS_SMALL = "SAS 9.4 TS1M7 (sas_small, Docker amd64) via oracle/run_sas.sh"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def stem_and_kind(fname):
    for ext in EXTS:
        if fname.endswith(ext):
            return fname[: -len(ext)], ext
    return fname, ""


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def programme(t):
    if t["famille"] in ("suppression", "index", "catalogue") or t["variante"] == "sjis":
        return f"full_{t['famille']}.sas"
    return f"{t['famille']}{'_comp' if t['compression'] != 'no' else ''}.sas"


tables = {r["fichier"]: r for r in tsv(os.path.join(CORPUS, "gen", "tables.tsv"))}
dropped = tsv(os.path.join(CORPUS, "gen", "dropped_long_names.tsv"))
external = {r["fichier"]: r for r in tsv(os.path.join(CORPUS, "external", "EXTERNAL.tsv"))}
check = {r["fichier"]: r for r in tsv(os.path.join(CORPUS, "out_full", "compression_check.tsv"))}

files = []
for top in ("files", "files_sas_small", "external"):
    for dp, _, fs in os.walk(os.path.join(CORPUS, top)):
        for fn in fs:
            if fn.startswith(".") or fn == "EXTERNAL.tsv":
                continue
            files.append(os.path.relpath(os.path.join(dp, fn), CORPUS))
files.sort()

rows, problems = [], []
for rel in files:
    path = os.path.join(CORPUS, rel)
    size, digest = os.path.getsize(path), sha256(path)
    if rel.startswith(("files/", "files_sas_small/")):
        small = rel.startswith("files_sas_small/")
        stem, ext = stem_and_kind(os.path.basename(rel))
        aux = AUX.get(stem)
        t = tables.get(aux[0] if aux else stem)
        if not t or (small and t["oracle"] != "small"):
            problems.append(f"fichier genere sans metadonnees : {rel}")
            continue
        if small:
            outil = f"{SAS_SMALL} ; programme corpus/gen/{t['famille']}.sas"
            fam = t["famille"] + " (sas_small)"
        else:
            outil = f"{SAS_FULL} ; programme corpus/gen_full/{programme(t)}"
            fam = t["famille"]
        if ext in (".contents.txt", ".print.txt"):
            outil += " ; decoupe par split_listing.py (chemins et nom d'utilisateur remplaces : /work, sas)"
        param = t["parametre_varie"] + (f" ; reference : {t['reference']}" if t["reference"] else "")
        if aux:
            param = f"{aux[1]} ; produit avec {aux[0]}"
        c = check.get(stem)
        if not small and c:
            if c["compressed_effectif"] == c["compression_demandee"]:
                param += f" ; compression effective ({c['compressed_effectif']})"
            else:
                param += f" ; ATTENTION compression NON appliquee par SAS (Compressed={c['compressed_effectif']}) : a exclure de l'analyse de compression"
        rows.append((rel, fam, param, "generee (" + KINDS[ext] + ")", outil, size, digest))
    else:
        e = external.get(rel)
        if rel.startswith("external/") and os.path.basename(rel).startswith("LICENSE_"):
            rows.append((rel, "licence", "texte de licence du depot source", "externe",
                         "copie du fichier de licence du depot", size, digest))
        elif e:
            rows.append((rel, "externe", e["cas_couvert"] + (f" ; {e['note']}" if e["note"] else ""),
                         f"externe : {e['url']} @ {e['commit']} ({e['chemin_source']}) ; licence {e['licence']}",
                         "copie telle quelle", size, digest))
        else:
            problems.append(f"fichier externe sans provenance : {rel}")

if "--verify" in sys.argv:
    text = open(MANIFEST, encoding="utf-8").read()
    ok = True
    for rel, *_rest, size, digest in rows:
        if f"| {rel} |" not in text:
            print("SANS LIGNE :", rel); ok = False
        elif digest not in text.split(f"| {rel} |", 1)[1].split("\n", 1)[0]:
            print("SHA-256 DIFFERENT :", rel); ok = False
    print(("OK : " if ok and not problems else "ECHEC : ") + f"{len(rows)} fichiers verifies, {len(problems)} problemes")
    for p in problems:
        print(" ", p)
    sys.exit(0 if ok and not problems else 1)

if problems:
    print("\n".join(problems), file=sys.stderr)
    sys.exit(1)

produced = {stem_and_kind(os.path.basename(r[0]))[0] for r in rows if r[0].startswith("files/") and r[0].endswith(".sas7bdat")}
drop_names = {r["fichier"] for r in dropped}
missing = [n for n in tables if n not in produced and n not in drop_names]
if missing:
    print("tables attendues mais absentes de corpus/files :", ", ".join(missing), file=sys.stderr)
    sys.exit(1)

eff = [r for r in check.values() if r["compressed_effectif"] == r["compression_demandee"]]
off = [r for r in check.values() if r["compressed_effectif"] != r["compression_demandee"]]

out = ["# Manifeste du corpus de reference `.sas7bdat`", "",
       "Genere par `corpus/gen/build_manifest.py` (verification : `--verify`). Une ligne par fichier de `corpus/files/` (SAS complet), "
       "`corpus/files_sas_small/` (sas_small) et `corpus/external/` (les metadonnees `external/EXTERNAL.tsv` ne sont pas listees). "
       "Taille en octets, empreinte SHA-256.", "",
       "## Notes importantes", "",
       "- **Deux oracles, deux dossiers.** `files/` est l'ensemble complet produit par le SAS complet (variantes `NO`, `CHAR`, `BINARY`, "
       "lignes supprimees, index, catalogue, Shift-JIS). `files_sas_small/` contient les 65 variantes `NO` produites par sas_small : "
       "meme programme, autre build, donc utile pour distinguer les champs d'en-tete lies a l'environnement. "
       "**Pour comparer deux variantes (par exemple `_no` et `_char`), prendre les deux dans `files/`** : l'hypothese \"un seul parametre "
       "varie\" n'est garantie qu'au sein d'un meme oracle.",
       "- **Non-reproductibilite octet pour octet.** Un fichier regenere avec le meme programme differe du fichier du corpus par "
       "au moins ses horodatages (creation, modification) et peut differer par d'autres champs d'en-tete. L'empreinte SHA-256 "
       "identifie le fichier du corpus, pas le resultat d'une regeneration. Les CSV et les sorties PROC CONTENTS/PRINT sont "
       "stables (les dates sont masquees par `options nodate nonumber`), a l'exception des champs `Created`/`Last Modified`/`Inode Number` "
       "de PROC CONTENTS.",
       "- **Anonymisation des fichiers texte.** Dans les sorties PROC CONTENTS/PRINT et les journaux du SAS complet, le chemin de travail "
       "a ete remplace par `/work`, le nom d'utilisateur par `sas` et la ligne de licence (nom et numero de site) par `[site masque]`. "
       "Les `.sas7bdat`, `.sas7bcat`, `.sas7bndx` et `.csv` sont inchanges (aucune de ces chaines n'y figure).",
       "- **Un seul parametre varie.** Pour chaque ligne, la colonne \"parametre varie\" nomme l'unique parametre qui distingue le fichier "
       "de sa reference (nom de la reference apres \"reference :\"). Les variantes de compression sont comparables a la table `_no` de "
       "meme nom dans `files/`.",
       f"- **Compression reellement appliquee : {len(eff)} tables sur {len(check)}.** SAS desactive la compression quand elle augmente la taille "
       "(note du journal) : les autres tables `_char`/`_binary` ont `Compressed=NO` et sont, pour l'analyse de compression, des tables non compressees. "
       "Detail dans la section \"Compression effective\" ; la colonne \"parametre varie\" le rappelle ligne par ligne.",
       "- **Plateformes.** Les fichiers `plateforme_*` et ceux de `datareader` utilisent `OUTREP=` : fichiers ecrits par SAS dans la "
       "representation de donnees demandee, pas produits sur l'OS d'origine.",
       "- **Infinis et NaN.** SAS ne sait pas en produire (aucune syntaxe) : non generes.",
       "- **Table a 0 ligne.** `PROC PRINT` n'imprime rien pour une table vide : `base_n0_mix_no.print.txt` n'existe pas.",
       "- **Listings tronques.** Dans la famille `compression`, `PROC PRINT` avertit \"Data too long for column c; truncated to 196 characters\" "
       "(`linesize=200`) : seul le listing `.print.txt` est tronque, pas la table ni le CSV.",
       "- **Caracteres.** Le CSV ecrit les manquants tels qu'affiches (`.`, `_`, `A`-`Z`) ; les blancs de fin ne sont pas des donnees en SAS, "
       "les blancs de tete sont conserves entre guillemets.", "",
       "## Fichiers", "",
       "| fichier | famille | parametre varie | source | outil de generation | taille | SHA-256 |", "|---|---|---|---|---|---|---|"]
for rel, fam, param, src, outil, size, digest in rows:
    out.append(f"| {cell(rel)} | {cell(fam)} | {cell(param)} | {cell(src)} | {cell(outil)} | {size} | {digest} |")

out += ["", "## Compression effective", "",
        "Source : `out_full/compression_check.tsv` (ligne `Compressed` de PROC CONTENTS et note du journal).", "",
        "| table | demandee | effective | taille (octets) | taille de la variante NO |", "|---|---|---|---|---|"]
for r in eff:
    out.append(f"| {r['fichier']} | {r['compression_demandee']} | {r['compressed_effectif']} | {r['taille_octets']} | {r['taille_octets_de_la_variante_no']} |")
out += ["", f"Les {len(off)} autres tables `_char`/`_binary` ont `Compressed=NO` (note du journal : \"Compression was disabled ... because compression "
        "overhead would increase the size of the data set\") : leur taille est celle de la variante `_no`. Liste dans `out_full/compression_check.tsv`.",
        "", "Constat a verifier au changement 03 : seules `types_char32767` et `compression_runs` (CHAR et BINARY) sont plus petites que leur variante `NO` ; "
        "les autres tables marquees compressees sont plus grandes (par exemple `compression_blank200_char`) : le critere de SAS est une estimation, "
        "pas la taille finale.", ""]

out += ["## Variantes manquantes (justification)", "",
        "Aucune variante n'est fabriquee. Seules manquent les variantes dont le nom de table depasse 32 octets (limite des noms de membre SAS), "
        "constate lors de l'execution avec le SAS complet (`gen/dropped_long_names.tsv`). Pour chacune, la variante `_no` et l'autre mode "
        "de compression existent.", "",
        "| table | raison |", "|---|---|"]
for r in dropped:
    out.append(f"| {r['fichier']} | {cell(r['raison'])} |")

out += ["", "## Cas hors oracle", "",
        "Cas impossibles a produire avec l'oracle, jamais fabriques. Couverts par `external/` quand un fichier public existe.", "",
        "| cas | couvert ? | detail |", "|---|---|---|",
        "| big endian 32 bits | oui, via `OUTREP=` | `files/plateforme/plateforme_hp_ux_32_no` (SAS, `OUTREP=HP_UX_32`) ; `external/datareader/test10..12` (RS_6000_AIX_32) ; `external/pandas/test10` |",
        "| big endian 64 bits | oui, via `OUTREP=` | `files/plateforme/plateforme_solaris_64_no`, `plateforme_aix_64_no` ; `external/datareader/test13..15` ; `external/pandas/test13` |",
        "| 32 bits little endian | oui, via `OUTREP=` | `files/plateforme/plateforme_linux_32_no`, `plateforme_windows_32_no` ; `external/datareader/test1..3` |",
        "| fichier produit sur un autre OS (AIX, Solaris, HP-UX, Windows reels) | **non** | aucun fichier public repere hors `OUTREP=` ; a demander a l'utilisateur (voir `prompts/01b_extraction_sas_complet.md`, etape D) |",
        "| fichier chiffre (`ENCRYPT=YES/AES`) | **non** | aucun fichier public repere (voir `rea_output/00_etat_de_l_art.md`, 4.5) ; SAS/SECURE requis cote oracle ; la disponibilite du produit n'est pas connue (rapport d'extraction non recu) |",
        "| compression `CHAR`/`BINARY` | oui, partiellement | `files/` : voir \"Compression effective\" ; les tables ou SAS refuse de compresser ne comptent pas |",
        "| lignes supprimees | oui | `files/suppression/` (`MODIFY ... REMOVE`, 10 lignes sur 100) |",
        "| index `.sas7bndx` | oui | `files/index/index_n100_ix_no` |",
        "| catalogue de formats `.sas7bcat` | oui | `files/catalogue/formats.sas7bcat` ; autres : `external/pyreadstat/test_formats_linux.sas7bcat`, `missing_formats.sas7bcat`, `external/readstat/format_with_default_*.sas7bcat` |",
        "| encodage Shift-JIS | oui | `files/encodage/encodage_sjis_no` |",
        "| encodages (Parso : ~70 codes) | **non copie** | le corpus Parso (`src/test/resources/sas7bdat`, 134 fichiers, Apache-2.0) n'est pas copie ici ; a copier au changement `specify-sas-formats-encodings` (04) |", ""]
with open(MANIFEST, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print(f"{len(rows)} fichiers, {len(dropped)} tables ignorees (nom > 32 octets) ; ecrit {MANIFEST}")
