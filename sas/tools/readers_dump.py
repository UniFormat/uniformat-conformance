#!/usr/bin/env python3
"""Lit un .sas7bdat avec pandas ET pyreadstat (a lancer avec l'interpreteur du venv) et ecrit un JSON sur la sortie standard.

Usage : <venv>/bin/python readers_dump.py fichier.sas7bdat [encodage]
Sortie : {"pandas": {"ok": bool, "err": str, "cols": [...], "rows": [[...]]}, "pyreadstat": {... + "labels": {...}, "formats": {...}}}
Les NaN sont ecrits "NaN" (JSON ne les admet pas) ; les chaines restent des chaines.
"""
import json
import math
import sys
import warnings

warnings.filterwarnings("ignore")


def norm(v):
    if isinstance(v, float) and math.isnan(v):
        return "NaN"
    if isinstance(v, bytes):
        return v.decode("latin-1")
    if hasattr(v, "item"):
        v = v.item()
    import datetime
    if isinstance(v, (datetime.datetime, datetime.date)) or type(v).__name__ == "Timestamp":
        d0 = datetime.datetime(1960, 1, 1)
        dt = v if isinstance(v, datetime.datetime) else datetime.datetime(v.year, v.month, v.day)
        dt = dt.replace(tzinfo=None) if hasattr(dt, "replace") else dt
        return (dt - d0).total_seconds() / 86400 if True else None
    return v


def main(path, enc=None):
    out = {}
    try:
        import pandas as pd
        df = pd.read_sas(path, format="sas7bdat", encoding=enc or "utf-8")
        out["pandas"] = {"ok": True, "err": "", "cols": list(df.columns), "rows": [[norm(v) for v in r] for r in df.itertuples(index=False)]}
    except Exception as e:  # noqa: BLE001
        out["pandas"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}
    try:
        import pyreadstat
        df, meta = pyreadstat.read_sas7bdat(path, encoding=enc)
        out["pyreadstat"] = {"ok": True, "err": "", "cols": list(df.columns), "rows": [[norm(v) for v in r] for r in df.itertuples(index=False)],
                             "labels": dict(zip(meta.column_names, meta.column_labels)), "formats": dict(meta.original_variable_types),
                             "table_name": meta.table_name, "encoding": meta.file_encoding}
    except Exception as e:  # noqa: BLE001
        out["pyreadstat"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}
    print(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
