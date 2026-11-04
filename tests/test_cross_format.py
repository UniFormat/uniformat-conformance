"""Cross-format round trips through the common (Arrow) data model.

Only one real format (sas7bdat) exists today, so the *other* side of each conversion is a **stand-in format** built in this
file on top of pyarrow (Parquet and CSV adapters registered with `uniformat_io.core`). The point of the test is the
path itself: format A -> Arrow table (core) -> format B -> Arrow table -> format A -> compare. When real `uniformat-parquet`
and `uniformat-csv` packages exist, they replace the stand-ins here.

Needs `UNIFORMAT_CORPUS` (a corpus root with `files/` and/or `external/`; the repository ships `data/` with the public files).
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest

import uniformat_io.core as uf
import uniformat_io.sas  # noqa: F401  (registers through the entry point; imported for its types)

HERE = Path(__file__).resolve().parent


def corpus_root() -> Path:
    env = os.environ.get("UNIFORMAT_CORPUS") or os.environ.get("SAS7BDAT_CORPUS")
    root = Path(env) if env else HERE.parent / "data"
    if not root.is_dir():
        pytest.skip("no corpus available")
    return root


@pytest.fixture(autouse=True)
def stand_in_formats():
    uf.register(uf.Format(
        name="parquet-standin", extensions=("parquet",),
        read_table=lambda p, columns=None, **kw: pq.read_table(p, columns=columns),
        write_table=lambda p, t, **kw: pq.write_table(t, p),
        schema=lambda p, **kw: pq.read_schema(p),
    ))
    uf.register(uf.Format(
        name="csv-standin", extensions=("csv",),
        read_table=lambda p, column_types=None, **kw: pacsv.read_csv(p, convert_options=pacsv.ConvertOptions(column_types=column_types)),
        write_table=lambda p, t, **kw: pacsv.write_csv(t, p),
    ))
    yield
    uf.unregister("parquet-standin")
    uf.unregister("csv-standin")


def files():
    root = corpus_root()
    wanted = [
        "files/base/base_n100_mix_no.sas7bdat",
        "files/valeurs/valeurs_manquants_no.sas7bdat",
        "files/metadonnees/metadonnees_fmt_date9_no.sas7bdat",
        "files/types/types_char200_no.sas7bdat",
        "files/compression/compression_pat2_binary.sas7bdat",
        "external/pandas/cars.sas7bdat",
        "external/pyreadstat/missing_test.sas7bdat",
        "external/datareader/test1.sas7bdat",
    ]
    found = [root / w for w in wanted if (root / w).is_file()]
    if not found:
        pytest.skip("none of the reference files is available")
    return found


def same_values(a: pa.Table, b: pa.Table) -> None:
    assert a.num_rows == b.num_rows
    assert a.column_names == b.column_names
    for name in a.column_names:
        for x, y in zip(a.column(name).to_pylist(), b.column(name).to_pylist()):
            if isinstance(x, float) and isinstance(y, float) and not (math.isnan(x) or math.isnan(y)):
                assert x == pytest.approx(y, rel=1e-13), name
            else:
                assert x == y, name


def test_sas_to_parquet_to_sas_is_lossless(tmp_path):
    for src in files():
        opts = {"missing": "sidecar"}
        enc = {"encoding": "utf-8"} if "datareader" in str(src) and src.stem in {f"test{n}" for n in range(16, 22)} else {}
        original = uf.read(src, **opts, **enc)
        mid = tmp_path / "mid.parquet"
        uf.convert(src, mid, read_options={**opts, **enc})
        assert uf.read(mid).num_rows == original.num_rows
        back = tmp_path / "back.sas7bdat"
        uf.convert(mid, back, write_options={"compression": "char"})
        again = uf.read(back, **opts)
        same_values(original, again)


def test_sas_to_csv_to_sas_keeps_numbers_and_text(tmp_path):
    src = [f for f in files() if f.name == "base_n100_mix_no.sas7bdat"]
    if not src:
        pytest.skip("base_n100_mix_no not available")
    original = uf.read(src[0])
    csv = tmp_path / "t.csv"
    uf.write(csv, original)
    back = tmp_path / "t.sas7bdat"
    # CSV carries no types: a text column such as "00001" would be inferred as an integer, so the types are given
    types = {f.name: f.type for f in original.schema}
    uf.write(back, uf.read(csv, column_types=types))
    again = uf.read(back)
    assert again.num_rows == original.num_rows
    assert set(again.column_names) == set(original.column_names)
    for name in original.column_names:
        for x, y in zip(original.column(name).to_pylist(), again.column(name).to_pylist()):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                assert float(x) == pytest.approx(float(y), rel=1e-13), name
            else:
                assert str(x or "") == str(y or ""), name


def test_conversion_errors_leave_no_file(tmp_path):
    src = files()[0]
    dst = tmp_path / "never.sas7bdat"
    with pytest.raises(Exception):
        uf.convert(src, dst, write_options={"compression": "zip"})
    assert not dst.exists()
    assert [p.name for p in tmp_path.iterdir()] == []
