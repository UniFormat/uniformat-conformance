#!/usr/bin/env python3
"""Compare sasfmt.py aux sorties PUT de l'oracle (evidence/fmt_display_*.txt) : une ligne "format|valeur|resultat" par cas.

Usage : python3 -I rea_output/tools/check_display.py [dossier evidence] [--verbose] [--only motif]
Sortie : par format, nombre de cas identiques / total et 3 premiers ecarts ; total. Code retour 1 s'il reste des ecarts.
"""
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sasfmt  # noqa: E402


def parse_value(tok):
    return tok if tok.startswith(".") and tok != "." or tok == "." else float(tok)


def main(argv):
    ev = next((a for a in argv[1:] if not a.startswith("--") and os.path.isdir(a)), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence"))
    only = argv[argv.index("--only") + 1] if "--only" in argv else ""
    stats = collections.OrderedDict()
    for path in sorted(glob.glob(os.path.join(ev, "fmt_display_*.txt"))):
        chars = path.endswith("_chr.txt")
        for line in open(path, encoding="utf-8", errors="replace"):
            if line.count("|") < 2:
                continue
            f, v, r = line.rstrip("\n").split("|", 2)
            if only and only not in f:
                continue
            r = r.rstrip(" ")
            try:
                got = sasfmt.fmt_char(v, f) if chars else sasfmt.fmt(parse_value(v), f)
            except (KeyError, ArithmeticError, ValueError, TypeError, AttributeError, OverflowError):
                got = None
            ok = got is not None and got.rstrip(" ") == r
            st = stats.setdefault(f, [0, 0, [], got is None])
            st[0 if ok else 1] += 1
            if not ok and len(st[2]) < 3:
                st[2].append((v, r, got))
    ok = sum(s[0] for s in stats.values())
    tot = ok + sum(s[1] for s in stats.values())
    unsup = [f for f, s in stats.items() if s[3]]
    for f, s in stats.items():
        if s[1] and ("--verbose" in argv or True):
            print(f"{f:14} {s[0]:4}/{s[0]+s[1]:<4} ex. " + " ; ".join(f"{v}->[{r}] obtenu [{g}]" for v, r, g in s[2]) if not s[3] else f"{f:14} non implemente")
    print(f"--- {ok}/{tot} cas identiques ; {len(stats)} formats ; {len(unsup)} non implementes")
    return 0 if ok == tot else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
