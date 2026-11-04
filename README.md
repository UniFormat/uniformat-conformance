# uniformat-conformance

Reference data, validation tools and cross-format tests for the UniFormat family. Not published.

| Path | Content |
|---|---|
| `crates/uniformat-testkit` | Rust test harness: corpus discovery (`UNIFORMAT_CORPUS`), reference CSV read by column name, value comparison at `1e-13` |
| `data/external/` | public reference files with redistributable licenses (see `NOTICE` and `data/external/EXTERNAL.tsv`) |
| `sas/tools/` | Python reference implementations (reader, writer, RLE/RDC compressors) and validators for `.sas7bdat` |
| `sas/corpus-generators/` | SAS programs and scripts that regenerate the full reference corpus (they need a licensed SAS) |
| `tests/` | cross-format round trips (`format A → Arrow → format B → Arrow → format A`) |

## Data policy

The full reference corpus is produced with a licensed SAS installation and is **not** stored in any repository. Point
`UNIFORMAT_CORPUS` to a local copy; tests that need it are skipped otherwise. This repository ships only files whose
license allows redistribution, with attribution in `NOTICE`.

## Cross-format tests

Only one real format exists today (`sas7bdat`). `tests/test_cross_format.py` therefore uses **stand-in** Parquet and CSV
adapters built on pyarrow for the other side of each conversion; they are replaced by `uniformat-parquet` and
`uniformat-csv` when those exist.

```bash
pip install -e ../uniformat-core/python pytest
(cd ../uniformat-sas/bindings/python && maturin develop --release)
UNIFORMAT_CORPUS=<corpus or data/> pytest tests
```

## Write-matrix replay (SAS tools)

`sas/tools/validate_write_driver.py [case ...]` writes the 57 reference cases with the driver, reads them back with the
driver, pandas, pyreadstat, Parso and the reference reader, and compares bytes with the reference writer. Without
arguments it also rewrites `sas/tools/write_matrix_driver.md`; with case names it does not. Environment: `VENV_PYTHON`
(pandas and pyreadstat; pandas 3.1 rejects 0-row compressed tables, use 2.3.x), `PARSO_CP`, `UNIFORMAT_OUT`. The optional
SAS oracle suite (`validate_write.py`) needs Docker and a licensed SAS.

## Mandatory security tests and optional corpus

The driver repositories generate their security fixtures in private temporary directories supplied by `uniformat-testkit`. These tests run without SAS and without an external corpus. Keep them in the default test suite.

Tests that require the independent SAS corpus are explicitly `#[ignore]`. Run them with `UNIFORMAT_CORPUS=/trusted/corpus cargo test --locked -- --ignored`; `Corpus::require_from_env()` fails if the corpus is missing or empty. A missing corpus must never be counted as successful conformance coverage. Existing fixtures and their independently obtained reference values are still needed to check real SAS compatibility.

The validation driver creates a private unpredictable output directory by default. `UNIFORMAT_OUT` is an explicit override for a trusted output directory. Rust dependency locks are tracked, and `cargo deny --locked --all-features check advisories` includes test dependencies.
