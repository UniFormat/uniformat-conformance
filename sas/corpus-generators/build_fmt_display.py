#!/usr/bin/env python3
"""Genere corpus/gen/probe/fmt/display_N.sas : valeurs limites x formats courants, affichees par PUT dans sas_small.
Sortie de chaque programme : corpus/out/fmt_display_N.txt, lignes "format|valeur|resultat" (resultat sur 80 caracteres, blancs de fin ignores).
Les valeurs sont ecrites comme litteraux SAS exacts (repr Python) ; les manquants comme . ._ .A .Z."""
import os

NUM = [0.0, 1.0, -1.0, 0.5, -0.5, 1.5, 2.5, 0.05, 0.005, 0.0005, 0.25, 0.125, 12345.6789, 1234567.891, 99999.99, 99999.999,
       9999.995, 999.5, 99.95, 9.995, 0.99995, 1e-5, 1e10, 123456789012.0, 0.30000000000000004, 1 / 3, 2 / 3, 1e15, 1e-10, -12.345,
       -0.001, 1e300, 123456.0, 12345678.0, 100.0, 1e5, 1e6, 1e7, 1e8, 3.14159265358979, 1234.5678, -1234.5678, 0.1, 0.01, 7.0, 42.0]
MISS = [".", "._", ".A", ".B", ".Z"]
DATE = [-141714, -141429, -141428, -141427, -141426, -138061, 2936546, 2936548, 2936549, 2936550, 3000000, 5000000, 7305000, 7305400, 8000000, 0, 1, -1, 59, 60, 365, 366, 14609, 14610, 21914, 21915, 22000, 60000, -21914, -21915, -25202, 2000000, -700000, 2936547, 1000000, 100, 31, 3653]
DTIME = [0, 1, 86399, 86400, 1e9, 1.5, -1, 1.7e9, -1e9, 3e9, 0.999, 59.5, 1234567890.123, 315619200, 1e10]
TIME = [0, 1, 59.5, 60, 3600, 3661, 86399, 86400, 90000, -1, -3661, 1e5, 12345.678, 0.5, 43200, 45296.789]
CHR = ["", " ab", "ab ", "abcdef", "a b", "abcdefghij", "x", "  ab  ", "ABC def"]

NUMFMT = ["8.", "8.2", "10.3", "5.", "12.4", "3.", "6.1", "2.", "1.", "15.", "20.10", "32.", "7.4", "4.1",
          "best1.", "best4.", "best6.", "best8.", "best12.", "best32.", "e8.", "e10.", "e12.3", "e7.", "e15.6",
          "comma8.", "comma10.2", "comma12.", "comma6.", "comma4.", "commax10.2", "dollar8.", "dollar12.2", "dollar6.", "dollar4.", "dollarx12.2",
          "percent8.", "percent8.1", "percent5.", "percent3.", "z5.", "z8.2", "z3.", "z12.", "negparen8.", "negparen10.2",
          "binary8.", "hex4.", "hex8.", "octal6.", "roman8.", "worddate10.", "words40.", "wordf40.", "fract8.", "ssn11."]
DATEFMT = ["date9.", "date7.", "date5.", "date11.", "date3.", "yymmdd10.", "yymmdd8.", "yymmdd6.", "yymmddn8.", "yymmddc10.", "yymmdds10.", "yymmddd10.", "yymmddb10.",
           "ddmmyy10.", "ddmmyy8.", "ddmmyy6.", "ddmmyyc10.", "ddmmyyn8.", "mmddyy10.", "mmddyy8.", "mmddyy6.", "mmddyyc10.", "mmddyyn8.",
           "monyy7.", "monyy5.", "yymon7.", "yymm7.", "yymmc7.", "yymmn6.", "mmyy7.", "yyq6.", "yyq4.", "yyqr8.", "worddate18.", "worddate9.", "worddatx18.",
           "weekdate17.", "weekdate29.", "weekdatx17.", "downame.", "downame3.", "monname.", "monname3.", "month.", "year4.", "year2.", "day.", "qtr.", "qtrr.", "weekday.", "julian7.", "julian5.", "julday3.", "nengo10.", "nldatemn.", "d8.", "bestd8."]
DTFMT = ["datetime19.", "datetime16.", "datetime22.3", "datetime13.", "datetime9.", "dateampm22.", "dateampm11.", "tod8.", "tod11.2", "date9.", "time8.", "hhmm5.", "hour4."]
TIMEFMT = ["time8.", "time5.", "time11.2", "time12.", "time3.", "hhmm5.", "hhmm5.2", "hour4.", "hour4.1", "mmss5.", "mmss8.1", "timeampm11.", "timeampm8.", "timeampm5."]
CHRFMT = ["$char4.", "$char8.", "$char12.", "$4.", "$8.", "$hex6.", "$hex12.", "$quote8.", "$quote12.", "$binary16.", "$octal12.", "$f6.", "$varying8. 4"]

def lit(v):
    if isinstance(v, str):
        return v
    r = repr(float(v))
    if r.endswith(".0"):
        r = r[:-2]
    return r.replace("e+", "E").replace("e-", "E-").replace("e", "E")

def block(fmts, values, chars=False):
    """une etape DATA par format : un format ou une largeur invalide n'en perd qu'une"""
    rows = []
    for f in fmts:
        rows.append('data _null_; file "OUTFILE" mod; length s $80' + (' x $20;' if chars else ';'))
        for v in values:
            if chars:
                rows.append(f'  x="{v}"; s=put(x,{f}); put "{f}|{v}|" s $char80.;')
            else:
                rows.append(f"  x={lit(v)}; s=put(x,{f}); put \"{f}|{lit(v)}|\" s $char80.;")
        rows.append("run;")
    return rows

jobs = {
 "num": block(NUMFMT, NUM + MISS),
 "date": block(DATEFMT, DATE + MISS),
 "dt": block(DTFMT, DTIME + MISS),
 "time": block(TIMEFMT, TIME + MISS),
 "chr": block(CHRFMT, CHR, chars=True),
}
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe", "fmt")
os.makedirs(d, exist_ok=True)
for name, rows in jobs.items():
    # un bloc de 250 instructions par etape DATA : une erreur de compilation n'en perd que 250
    body = ["options nodate nonumber linesize=200;", f'data _null_; file "/work/out/fmt_display_{name}.txt"; put "debut"; run;'] + [r.replace("OUTFILE", f"/work/out/fmt_display_{name}.txt") for r in rows]
    open(os.path.join(d, f"display_{name}.sas"), "w").write("\n".join(body) + "\n")
    print(name, len(rows), "instructions")
