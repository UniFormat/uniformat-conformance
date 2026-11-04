#!/usr/bin/env python3
"""Boucle de validation de l'ecrivain de reference : ecrit les cas de write_cases.py, les fait relire par SAS (sas_small via
oracle/run_sas.sh), pandas, pyreadstat, Parso et ref_reader.py, compare aux valeurs attendues et ecrit write_matrix.md.

Usage : python3 -I rea_output/tools/validate_write.py [cas ...]     (sans argument : tous les cas)
Environnement : VENV_PYTHON = interpreteur ou pandas et pyreadstat sont installes ; PARSO_CP = classpath Java de Parso + ParsoDump.
"""
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import check_contents  # noqa: E402
import ref_reader  # noqa: E402
import write_cases  # noqa: E402

FILES = os.path.join(REPO, "corpus", "gen", "probe", "write", "files")
OUT = os.path.join(REPO, "corpus", "out")
EVID = os.path.join(REPO, "rea_output", "evidence", "write")
VENV = os.environ.get("VENV_PYTHON", "")
PARSO = os.environ.get("PARSO_CP", "")
READERS = ["SAS", "pandas", "pyreadstat", "Parso", "ref_reader"]
MISS = {".", "_"} | {chr(c) for c in range(65, 91)}


def is_miss(v):
    return isinstance(v, str) and v in MISS


def num_eq(exp, got):
    if is_miss(exp):
        return got is None or got in ("NaN", "", ".", "_") or (isinstance(got, str) and got in MISS) or (isinstance(got, float) and math.isnan(got))
    try:
        return float(got) == float(exp) or math.isclose(float(got), float(exp), rel_tol=1e-13)
    except (TypeError, ValueError):
        return False


def rows_match(cols, exp_rows, got_rows):
    if len(exp_rows) != len(got_rows):
        return f"{len(got_rows)} lignes au lieu de {len(exp_rows)}"
    for i, (er, gr) in enumerate(zip(exp_rows, got_rows)):
        if len(gr) != len(er):
            return f"ligne {i + 1} : {len(gr)} colonnes au lieu de {len(er)}"
        for c, e, g in zip(cols, er, gr):
            if c.type == "n":
                ok = num_eq(e, g)
            else:
                exp_s = (e.decode("latin-1") if isinstance(e, bytes) else str(e)).rstrip(" ")
                got_s = str(g if g is not None else "").rstrip(" ")
                ok = got_s == exp_s or (exp_s == "" and got_s == "NaN")  # pandas rend NaN pour une chaine vide (comportement documente, hors format)
            if not ok:
                return f"ligne {i + 1} colonne {c.name} : attendu {e!r}, lu {g!r}"
    return ""


def sas_program(case, stem):
    cols = case["cols"]
    L = ["options nodate nonumber linesize=200 pagesize=32000;", 'libname o "/work/gen/probe/write/files";',
         f'title1 "@@@ {stem} contents"; proc contents data=o.{stem}; run;', *([] if case.get("no_print") else [f'title1 "@@@ {stem} print"; proc print data=o.{stem}; run;']), "title1;"]
    names = [c.name for c in cols]
    if names:
        L.append(f'data _null_; set o.{stem}; file "/work/out/write_{stem}.csv" dlm="," lrecl=1000000;')
        items = [f"{c.name} :best32." if c.type == "n" else (f"{c.name} $char{c.length}." if case.get("csv_plain") else f"{c.name} :$quote{min(c.length + 2, 32767)}.") for c in cols]
        for k in range(0, len(items), 200):
            L.append("  put " + " ".join(items[k:k + 200]) + (" @;" if k + 200 < len(items) else ";"))
        L.append("run;")
    return "\n".join(L) + "\n"


def run_sas(case, stem):
    prog = os.path.join(REPO, "corpus", "gen", "probe", "write", f"w_{stem}.sas")
    open(prog, "w").write(sas_program(case, stem))
    csvp = os.path.join(OUT, f"write_{stem}.csv")
    if os.path.exists(csvp):
        os.remove(csvp)
    r = subprocess.run([os.path.join(REPO, "oracle", "run_sas.sh"), f"gen/probe/write/w_{stem}.sas"], capture_output=True, text=True)
    log = os.path.join(OUT, f"w_{stem}.log")
    text = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
    problems = [l for l in text.splitlines() if l.startswith(("ERROR", "WARNING"))]
    benign = [l for l in problems if re.match(r"WARNING: The informat @\S+ could not be loaded", l)] if any(c.informat for c in case["cols"]) else []
    problems = [l for l in problems if l not in benign]
    os.makedirs(EVID, exist_ok=True)
    for ext in ("log", "lst"):
        src = os.path.join(OUT, f"w_{stem}.{ext}")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(EVID, f"{stem}_sas.{ext}"))
    if problems:
        return f"{len(problems)} ERROR/WARNING : {problems[0][:90]}", f"{stem}_sas.log"
    note = "OK*" if benign else ""
    lst = os.path.join(OUT, f"w_{stem}.lst")
    if os.path.exists(lst) and case["cols"]:
        refmeta = check_contents.parse_contents(lst)
        for j, c in enumerate(case["cols"], 1):
            m = (refmeta or {}).get(c.name)
            want_f = check_contents.fmt_str(c.fmt[0], c.fmt[1], c.fmt[2]) if c.fmt else ""
            want_i = check_contents.fmt_str(c.informat[0], c.informat[1], c.informat[2]) if c.informat else ""
            lab_ok = m is not None and (m["label"] == c.label or (len(m["label"]) >= 60 and c.label.startswith(m["label"])))  # le listing tronque les labels tres longs (linesize=200)
            if m is None or not lab_ok or (m["num"], m["type"], m["length"], m["format"], m["informat"]) != (j, c.type, c.length, want_f, want_i):
                return f"PROC CONTENTS : variable {c.name} lue {m} au lieu de {(j, c.type, c.length, c.label, want_f, want_i)}", f"{stem}_sas.log"
    if not case["cols"]:
        return note, f"{stem}_sas.log"
    if not os.path.exists(csvp):
        return "pas de CSV produit", f"{stem}_sas.log"
    raw = open(csvp, "rb").read().decode("utf-8", "replace").replace("\x00", "")
    got = list(csv.reader(raw.splitlines()))
    return rows_match(case["cols"], case["rows"], got) or note, f"{stem}_sas.log"


def run_third(case, path, stem):
    res = {}
    enc = case.get("codec")
    if VENV:
        r = subprocess.run([VENV, os.path.join(HERE, "readers_dump.py"), path] + ([enc] if enc and enc != "utf-8" else []), capture_output=True, text=True)
        try:
            data = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            data = {k: {"ok": False, "err": r.stderr[-200:]} for k in ("pandas", "pyreadstat")}
        for k in ("pandas", "pyreadstat"):
            d = data.get(k, {"ok": False, "err": "?"})
            if not d["ok"]:
                res[k] = d["err"][:120]
            else:
                bad = rows_match(case["cols"], case["rows"], d["rows"]) or ("" if d["cols"] == [c.name for c in case["cols"]] else f"colonnes {d['cols']}")
                if not bad and k == "pyreadstat":
                    for c in case["cols"]:
                        if (d["labels"].get(c.name) or "") != c.label:
                            bad = f"label de {c.name} : {d['labels'].get(c.name)!r} au lieu de {c.label!r}"
                res[k] = bad
    else:
        res["pandas"] = res["pyreadstat"] = "non disponible"
    if case.get("skip") and "Parso" in case["skip"]:
        res["Parso"] = "SKIP"
    elif PARSO:
        r = subprocess.run(["java", "-cp", PARSO, "ParsoDump", path], capture_output=True, text=True)
        lines = [l for l in r.stdout.splitlines() if not l.startswith("SLF4J")]
        if r.returncode != 0 or not any(l.startswith("#ROWS") for l in lines):
            res["Parso"] = (r.stderr or r.stdout)[-120:] or "echec"
        else:
            rows = [l.split("\t") for l in lines if not l.startswith("#")]
            res["Parso"] = rows_match(case["cols"], case["rows"], rows)
    else:
        res["Parso"] = "non disponible"
    return res


def main(argv):
    names = argv[1:]
    cases = [c for c in write_cases.cases() if not names or c["name"] in names]
    os.makedirs(FILES, exist_ok=True)
    table = []
    for case in cases:
        stem = case["name"]
        path = os.path.join(FILES, stem + ".sas7bdat")
        if case.get("not_feasible"):
            table.append((case, {r: ("NON FAISABLE", case["not_feasible"]) for r in READERS}, ""))
            continue
        try:
            write_cases.build(case, path)
        except (NotImplementedError, ValueError) as e:
            table.append((case, {r: ("NON FAISABLE", str(e)) for r in READERS}, ""))
            continue
        status = {}
        bad, log = run_sas(case, stem)
        status["SAS"] = (("OK" if not bad or bad == "OK*" else "KO"), ("avertissement de l'oracle sur l'informat : voir note 1" if bad == "OK*" else bad or log))
        third = run_third(case, path, stem)
        for k in ("pandas", "pyreadstat", "Parso"):
            status[k] = (("OK" if third[k] == "" else "NA" if third[k] == "SKIP" else "KO"), (case.get("skip_why", "") if third[k] == "SKIP" else third[k]) or "")
        try:
            sf = ref_reader.SasFile(open(path, "rb").read(), raw=True)
            got = [[(x.decode(sf.codec or "latin-1") if isinstance(x, bytes) else x) for x in r] for r in sf.rows]
            b = rows_match(case["cols"], case["rows"], got)
        except Exception as e:  # noqa: BLE001
            b = f"{type(e).__name__}: {e}"
        status["ref_reader"] = ("OK" if not b else "KO", b)
        for r, why in case.get("known_ko", {}).items():
            if status[r][0] == "KO":
                status[r] = ("KOC", why + " — " + str(status[r][1]))
        table.append((case, status, log))
        print(f"{stem:28} " + " ".join(f"{k}={v[0]}" for k, v in status.items()), flush=True)
        for k, v in status.items():
            if v[0] == "KO":
                print(f"    {k}: {v[1]}")
    if not names:  # a run restricted to some cases must not overwrite the full matrix
        write_matrix(table)
    ko = sum(1 for _, st, _ in table for v in st.values() if v[0] == "KO")
    print(f"--- {len(table)} cas, {ko} cellule(s) KO")
    return 1 if ko else 0


HEAD = """# Matrice de validation de l'écrivain de référence

Fichiers produits par `rea_output/tools/ref_writer.py` (cas dans `write_cases.py`, boucle dans `validate_write.py`), relus par les lecteurs disponibles :

| lecteur | version | usage |
|---|---|---|
| SAS | 9.4 TS1M7, oracle `sas_small` (Docker linux/amd64, `oracle/run_sas.sh`) | `PROC CONTENTS`, `PROC PRINT`, `data _null_; set lib.t`, journal sans `ERROR` ni `WARNING` |
| pandas | 2.3.3 (Python 3.9, venv hors dépôt) | `read_sas`, données |
| pyreadstat | 1.2.9 (ReadStat) | données et métadonnées |
| Parso | 2.0.14 (Java 26) | données (`ParsoDump.java`) |
| `ref_reader.py` | écrit depuis `10_format_sas7bdat.md` | données et métadonnées |

Lecteurs non disponibles : SAS complet (les tables compressées de plus de 255 lignes ne peuvent pas être comparées à un fichier de SAS 9.4M7, inconnue W01).
"""


def write_matrix(table):
    p = os.path.join(HERE, "write_matrix.md")
    old = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    head = HEAD
    L = [head.rstrip() + "\n", "## Matrice", "", "Chaque cellule : `OK`, `KO` (cause), `KO CONNU` (limite documentée dans `20_ecriture.md`, hors critère de fin), `NON APPLICABLE` ou `NON FAISABLE` (raison) ; le journal SAS de chaque cas est `rea_output/evidence/write/<cas>_sas.log`. **Note 1 (`OK*`)** : `sas_small` ne sait pas charger les informats (`WARNING: The informat @DATE could not be loaded, probably due to insufficient memory`) ; le même avertissement apparait pour un fichier écrit par le SAS complet (`corpus/files/metadonnees/metadonnees_infmt_date9_no`, journal `rea_output/evidence/write_informat_oracle_ref.log`) : ce n'est pas un défaut du fichier produit.", "",
         "| cas | description | " + " | ".join(READERS) + " | journal SAS |", "|---|---|" + "---|" * len(READERS) + "---|"]
    for case, st, log in table:
        cells = []
        for r in READERS:
            s = st[r]
            cells.append(("OK*" if "note 1" in s[1] else "OK") if s[0] == "OK" else f"{ {'NA': 'NON APPLICABLE', 'KOC': 'KO CONNU'}.get(s[0], s[0]) } : {s[1]}".replace("|", "/")[:150])
        L.append(f"| {case['name']} | {case['desc']} | " + " | ".join(cells) + f" | {('`' + log + '`') if log else '—'} |")
    open(p, "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
