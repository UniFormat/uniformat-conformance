#!/usr/bin/env python3
"""Controle de la relecture SAS (tache 3.1) : un fichier du corpus doit sortir OK, une copie volontairement tronquee doit sortir KO.

Usage : python3 -I rea_output/tools/control_sas.py <fichier du corpus .sas7bdat>
Journaux : rea_output/evidence/write/control_ok_sas.log et control_ko_sas.log
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_reader  # noqa: E402
import ref_writer as W  # noqa: E402
import validate_write as V  # noqa: E402


def main(argv):
    src = open(argv[1], "rb").read()
    sf = ref_reader.SasFile(src, raw=True)
    cols = [W.Col(c.name, c.type, c.length, label=c.label or "") for c in sf.columns]
    rows = [[(x.decode(sf.codec or "latin-1") if isinstance(x, bytes) else x) for x in r] for r in sf.rows]
    ok = True
    for stem, data, want in (("control_ok", src, "OK"), ("control_ko", src[:len(src) // 2], "KO")):
        open(os.path.join(V.FILES, stem + ".sas7bdat"), "wb").write(data)
        bad, log = V.run_sas({"cols": cols, "rows": rows}, stem)
        got = "OK" if not bad or bad == "OK*" else "KO"
        print(f"{stem}: attendu {want}, obtenu {got} {'' if got == 'OK' else '(' + str(bad)[:100] + ')'}")
        ok &= got == want
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
