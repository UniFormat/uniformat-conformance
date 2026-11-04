#!/usr/bin/env python3
"""Rejoue la matrice d'écriture (`write_cases.py`) avec le **driver** (`uniformat_io.sas.write_sas`) à la place de `ref_writer.py`
(jalon J6, critère 1) : chaque fichier est relu par le driver, pandas, pyreadstat (ReadStat), Parso et `ref_reader.py` ; il est
aussi comparé octet à octet à celui de `ref_writer.py` (mêmes entrées, même code de fichier, même date).

Usage : <venv>/bin/python rea_output/tools/validate_write_driver.py [cas ...]    (sans argument : tous les cas)
Environnement : VENV_PYTHON (pandas, pyreadstat), PARSO_CP (classpath Java de Parso + ParsoDump), UNIFORMAT_OUT (dossier de sortie).
SAS (oracle `sas_small`) n'est pas exécuté ici : suite optionnelle, colonne « non exécuté ».
"""
import os
import shutil
import sys
import tempfile
import warnings
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pyarrow as pa  # noqa: E402
import ref_reader  # noqa: E402
import ref_writer as W  # noqa: E402
import uniformat_io.sas as S  # noqa: E402
import validate_write as V  # noqa: E402
import write_cases  # noqa: E402

# Keep generated artifacts for inspection, in a private unpredictable directory by default.
# An explicit UNIFORMAT_OUT is a user-selected trusted output directory.
OUT = os.environ.get("UNIFORMAT_OUT") or tempfile.mkdtemp(prefix="uniformat-write-driver-")
CREATED = 1_762_000_000.0  # secondes Unix fixes : le fichier du driver et celui de ref_writer ont le même en-tête
READERS = ["driver", "pandas", "pyreadstat", "Parso", "ref_reader"]
ENCODINGS = {20: "utf-8", 29: "latin1", 62: "wlatin1"}
SPECIAL = {".": 1, "_": 2, **{chr(65 + i): 3 + i for i in range(26)}}


def to_table(cols, rows):
    arrays, names = [], []
    for j, c in enumerate(cols):
        vals = [r[j] for r in rows]
        if c.type == "n":
            nums = [None if isinstance(v, str) else float(v) for v in vals]
            codes = [SPECIAL.get(v, 0) if isinstance(v, str) else 0 for v in vals]
            arrays.append(pa.array(nums, type=pa.float64()))
            names.append(c.name)
            if any(codes):
                arrays.append(pa.array(codes, type=pa.uint8()))
                names.append(c.name + "__missing")
        else:
            arrays.append(pa.array([v if isinstance(v, str) else v.decode("latin-1") for v in vals], type=pa.string()))
            names.append(c.name)
    return pa.Table.from_arrays(arrays, names=names) if arrays else pa.table({})


def driver_write(path, cols, rows, compress=None, page_length=65536, enc_code=20, codec=None, seed=0):
    """Meme signature que `ref_writer.write` : ecrit avec le driver (`uniformat_io.sas.write_sas`)."""
    import random
    return S.write_sas(
        path, to_table(cols, rows), compression={"CHAR": "char", "BINARY": "binary"}.get(compress), encoding=ENCODINGS[enc_code],
        column_labels={c.name: c.label for c in cols if c.label}, formats={c.name: c.fmt for c in cols if c.fmt},
        informats={c.name: c.informat for c in cols if c.informat}, lengths={c.name: c.length for c in cols},
        page_length=page_length, file_code=random.Random(seed).getrandbits(32), created=CREATED,
    )


def build_driver(case, path):
    return driver_write(path, case["cols"], case["rows"], compress=case.get("compress"), page_length=case.get("page_length", 65536),
                        enc_code=case.get("enc_code", 20), seed=zlib.crc32(case["name"].encode()))


def build_reference(case, path):
    import random
    seed = zlib.crc32(case["name"].encode())
    W._sas_now = lambda: CREATED + 315619200.0
    W.write(path, case["cols"], case["rows"], seed=seed, **{k: v for k, v in case.items() if k in ("compress", "page_length", "enc_code", "codec")})


def driver_rows(path, case):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = S.read_sas_table(path, dates="float", missing="sidecar", encoding=None)
    d = t.to_pydict()
    out = []
    for i in range(t.num_rows):
        row = []
        for c in case["cols"]:
            v = d[c.name][i]
            if c.type == "n":
                code = d.get(c.name + "__missing", [0] * t.num_rows)[i]
                row.append(S.missing_label(code) if code else v)
            else:
                row.append(v)
        out.append(row)
    return out


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    names = argv[1:]
    table, ko = [], 0
    for case in write_cases.cases():
        stem = case["name"]
        if names and stem not in names:
            continue
        status = {}
        if case.get("not_feasible"):
            table.append((case, {r: ("NF", case["not_feasible"][:100]) for r in READERS}, ""))
            print(f"{stem:24} NON FAISABLE (ecrivain de reference)")
            continue
        path = os.path.join(OUT, stem + ".sas7bdat")
        ref_path = os.path.join(OUT, stem + ".ref.sas7bdat")
        if os.path.exists(path):
            os.remove(path)
        # limites de schema : l'ecrivain refuse avant le premier octet (assertion negative)
        refused = None
        try:
            build_driver(case, path)
        except S.SasError as e:
            refused = f"{type(e).__name__} : {e}"
        if refused:
            leaked = os.path.exists(path) or any(f.startswith("." + stem) for f in os.listdir(OUT))
            expected = stem in ("w14_name33", "w14_label257", "w14_char32768")
            ok = expected and not leaked
            status = {r: (("OKN" if ok else "KO"), refused[:110]) for r in READERS}
            table.append((case, status, ""))
            print(f"{stem:24} refuse avant ecriture : {refused[:80]} {'OK' if ok else 'KO'}")
            ko += 0 if ok else 1
            continue
        # page_length 1024 : le driver agrandit la page (ADR 0005 §3) la ou l'ecrivain de reference renonce
        try:
            build_reference(case, ref_path)
            identical = open(path, "rb").read() == open(ref_path, "rb").read()
            ref_note = "" if identical else "octets differents de ref_writer"
        except (ValueError, NotImplementedError) as e:
            identical, ref_note = None, f"ref_writer renonce : {str(e)[:60]}"
        bad = V.rows_match(case["cols"], case["rows"], driver_rows(path, case))
        status["driver"] = ("OK" if not bad else "KO", bad)
        third = V.run_third(case, path, stem)
        for k in ("pandas", "pyreadstat", "Parso"):
            status[k] = ("OK" if third[k] == "" else "NA" if third[k] == "SKIP" else "KO", (case.get("skip_why", "") if third[k] == "SKIP" else third[k]) or "")
        try:
            sf = ref_reader.SasFile(open(path, "rb").read(), raw=True)
            got = [[(x.decode(sf.codec or "latin-1") if isinstance(x, bytes) else x) for x in r] for r in sf.rows]
            b = V.rows_match(case["cols"], case["rows"], got)
        except Exception as e:  # noqa: BLE001
            b = f"{type(e).__name__}: {e}"
        status["ref_reader"] = ("OK" if not b else "KO", b)
        for r, why in case.get("known_ko", {}).items():
            if r in status and status[r][0] == "KO":
                status[r] = ("KOC", why + " — " + str(status[r][1]))
        table.append((case, status, ref_note if identical is not True else "identique"))
        line = " ".join(f"{k}={v[0]}" for k, v in status.items())
        print(f"{stem:24} {line}  octets={'identiques' if identical else ref_note}", flush=True)
        for k, v in status.items():
            if v[0] == "KO":
                ko += 1
                print(f"    {k}: {v[1]}")
    if not names:  # a run restricted to some cases must not overwrite the full matrix
        write_matrix(table)
    print(f"--- {len(table)} cas, {ko} cellule(s) KO")
    return 1 if ko else 0


def write_matrix(table):
    L = ["# Matrice d'écriture rejouée avec le driver (J6)", "",
         "Fichiers produits par `uniformat_io.sas.write_sas` (cœur Rust) à partir des cas de `write_cases.py`, relus par le driver, pandas, "
         "pyreadstat (ReadStat), Parso et `ref_reader.py`. La colonne « octets » compare le fichier à celui de `ref_writer.py` (mêmes "
         "entrées, même code de fichier et même date). **SAS (`sas_small`) n'a pas été exécuté** : suite optionnelle, oracle Docker indisponible ici.", "",
         "Cellules : `OK`, `KO`, `KO CONNU` (limite documentée : assertion négative), `REFUSÉ` (le driver refuse avant d'écrire : erreur typée, aucun fichier), `NON APPLICABLE`.", "",
         "| cas | description | " + " | ".join(READERS) + " | octets |", "|---|---|" + "---|" * len(READERS) + "---|"]
    for case, st, note in table:
        cells = []
        for r in READERS:
            s = st[r]
            cells.append({"OK": "OK", "OKN": "REFUSÉ : " + s[1], "NA": "NON APPLICABLE", "NF": "NON FAISABLE", "KOC": "KO CONNU : " + s[1][:90]}.get(s[0], f"KO : {s[1]}").replace("|", "/")[:150])
        L.append(f"| {case['name']} | {case['desc']} | " + " | ".join(cells) + f" | {note or '—'} |")
    open(os.path.join(HERE, "write_matrix_driver.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
