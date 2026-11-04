#!/usr/bin/env python3
"""Genere les programmes SAS du corpus COMPLEMENTAIRE (prompt 01c) pour le SAS complet.

Usage : python3 build_complement.py <dossier de travail>
Ecrit <dossier>/gen_complement/*.sas, <dossier>/gen_complement/run_complement.sh et <dossier>/files_complement/ (vide).
Bibliotheque standard seulement. Donnees synthetiques uniquement, deterministes (aucune fonction aleatoire).

Objectifs (rea_output/60_inconnues.md) :
  W01, W02, C07 : tables compressees de 255 a 10 000 lignes, plusieurs pages de lignes, pages de 4 096 a 16 384 octets ;
  C02, C05, C08 : lignes limites (ligne vide, ligne uniforme, motifs RDC a decalage 3, 4, 4098, 4099, suites de 15 a 20 octets) ;
  F07 a F09     : catalogues de formats ne differant que d'un element ;
  F02 a F06     : formats ISO 8601 et NLS, dates hors plage, heures tres grandes.
"""
import os
import sys

ALPHA = "abcdefghijklmnopqrstuvwxyz0123456789"


def header(libpath):
    return f'options nodate nonumber linesize=200 pagesize=32000;\nlibname o "{libpath}";\n'


def csv_step(table, csvpath, cols):
    puts = " ".join(f"{c} :best32." if t == "n" else f"{c} :$quote{w + 2}." for c, t, w in cols)
    return (f'data _null_; set {table}; file "{csvpath}" dlm="," lrecl=1000000;\n  put {puts};\nrun;\n'
            f'proc contents data={table}; run;\n')


def series_rows(libpath, csvdir):
    """A : meme schema, 3 variantes de compression, nombre de lignes variable."""
    out = {}
    for n in (255, 256, 257, 300, 1000, 10000, 65535, 65536, 70000):
        body = []
        for comp, tag in (("no", "no"), ("char", "char"), ("binary", "binary")):
            opt = f"(compress={comp})"
            body.append(
                f"data o.comp_n{n}_{tag}{opt};\n  length i 8 x 8 a $40 b $12;\n  do k=1 to {n};\n    i=k; x=k/4;\n"
                f"    a='ligne '||put(mod(k,7),1.);\n    b=substr('ababababab',1,2*mod(k,5)+2);\n    output;\n  end;\n  drop k;\nrun;\n")
        body.append(csv_step("o.comp_n%d_no" % n, f"{csvdir}/comp_n{n}.csv", [("i", "n", 0), ("x", "n", 0), ("a", "c", 40), ("b", "c", 12)]))
        out[f"comp_n{n}"] = header(libpath) + "".join(body)
    return out


def series_rl(libpath, csvdir):
    """G : longueur de ligne et decision de compresser (C02) : une colonne caractere de n octets, 200 lignes, contenu compressible."""
    out = {}
    body = []
    for n in (16, 17, 18, 19, 20, 21, 22, 24, 28, 32, 40, 48, 56, 64):
        for comp in ("no", "char", "binary"):
            body.append(f"data o.rl{n}_{comp}(compress={comp});\n  length a ${n};\n  do k=1 to 200;\n    a=put(k,z8.);\n    output;\n  end;\n  drop k;\nrun;\n")
        body.append(f"proc contents data=o.rl{n}_char; run;\nproc contents data=o.rl{n}_binary; run;\n")
    out["rl"] = header(libpath) + "".join(body)
    return out


def series_big(libpath, csvdir):
    """B : lignes volumineuses de texte pseudo-aleatoire (formule arithmetique deterministe) -> plusieurs pages de lignes."""
    out = {}
    for n in (200, 300, 1000):
        body = []
        for comp, tag in (("no", "no"), ("char", "char"), ("binary", "binary")):
            opt = f"(compress={comp})"
            body.append(
                f"data o.big_n{n}_{tag}{opt};\n  length i 8 a $440;\n  retain s 12345;\n  alpha='{ALPHA}';\n  do k=1 to {n};\n    i=k;\n"
                f"    do j=1 to 440;\n      s=mod(s*1103+12345,65521);\n      substr(a,j,1)=substr(alpha,1+mod(s,36),1);\n    end;\n    output;\n  end;\n  drop k j s alpha;\nrun;\n")
        body.append(csv_step("o.big_n%d_no" % n, f"{csvdir}/big_n{n}.csv", [("i", "n", 0), ("a", "c", 440)]))
        out[f"big_n{n}"] = header(libpath) + "".join(body)
    return out


def series_pages(libpath, csvdir):
    """C : taille de page imposee par BUFSIZE, 300 lignes compressibles."""
    out = {}
    for bs in (4096, 8192, 16384):
        body = []
        for comp in ("char", "binary"):
            body.append(
                f"data o.pg{bs}_{comp}(compress={comp} bufsize={bs});\n  length i 8 x 8 a $40 b $12;\n  do k=1 to 300;\n    i=k; x=k/4;\n"
                f"    a='ligne '||put(mod(k,7),1.);\n    b=substr('ababababab',1,2*mod(k,5)+2);\n    output;\n  end;\n  drop k;\nrun;\n"
                f"proc contents data=o.pg{bs}_{comp}; run;\n")
        out[f"pg{bs}"] = header(libpath) + "".join(body)
    return out


def series_edges(libpath, csvdir):
    """D : lignes limites."""
    out = {}
    base = []
    # ligne vide (toutes les colonnes caracteres a blanc) et ligne uniforme
    for comp in ("no", "char", "binary"):
        opt = f"(compress={comp})"
        base.append(f"data o.edge_blank_{comp}{opt};\n  length a $100;\n  do k=1 to 50;\n    a=' ';\n    output;\n  end;\n  drop k;\nrun;\n")
        base.append(f"data o.edge_uniform_{comp}{opt};\n  length a $200;\n  do k=1 to 50;\n    a=repeat('x',199);\n    output;\n  end;\n  drop k;\nrun;\n")
        base.append(f"data o.edge_numzero_{comp}{opt};\n  length x1-x30 8;\n  array v x1-x30;\n  do k=1 to 50;\n    do j=1 to 30;\n      v[j]=0;\n    end;\n    output;\n  end;\n  drop k j;\nrun;\n")
    base.append(csv_step("o.edge_blank_no", f"{csvdir}/edge_blank.csv", [("a", "c", 100)]))
    base.append(csv_step("o.edge_uniform_no", f"{csvdir}/edge_uniform.csv", [("a", "c", 200)]))
    out["edge_rows"] = header(libpath) + "".join(base)
    # motifs RDC : bloc de p caracteres repete (decalage p) sur une colonne de 5000 octets
    rdc = []
    for p in (3, 4, 5, 16, 17, 18, 19, 20, 100, 4097, 4098, 4099):
        for comp in ("no", "binary"):
            opt = f"(compress={comp})"
            rdc.append(
                f"data o.edge_per{p}_{comp}{opt};\n  length a $5000;\n  retain s 777;\n  alpha='{ALPHA}';\n  do k=1 to 20;\n    do j=1 to {p};\n"
                f"      s=mod(s*1103+12345,65521);\n      substr(a,j,1)=substr(alpha,1+mod(s,36),1);\n    end;\n"
                f"    do j={p}+1 to 5000;\n      substr(a,j,1)=substr(a,j-{p},1);\n    end;\n    output;\n  end;\n  drop k j s alpha;\nrun;\n")
        rdc.append(csv_step(f"o.edge_per{p}_no", f"{csvdir}/edge_per{p}.csv", [("a", "c", 5000)]))
    out["edge_rdc_period"] = header(libpath) + "".join(rdc)
    # suites d'un meme octet de longueur 14 a 21, apres un prefixe pseudo-aleatoire
    runs = []
    for comp in ("no", "char", "binary"):
        opt = f"(compress={comp})"
        runs.append(
            f"data o.edge_runlen_{comp}{opt};\n  length n 8 a $120;\n  retain s 4242;\n  alpha='{ALPHA}';\n  do n=14 to 21;\n    do j=1 to 120;\n"
            f"      s=mod(s*1103+12345,65521);\n      substr(a,j,1)=substr(alpha,1+mod(s,36),1);\n    end;\n    do j=41 to 40+n;\n      substr(a,j,1)='z';\n    end;\n    output;\n  end;\n  drop j s alpha;\nrun;\n")
    runs.append(csv_step("o.edge_runlen_no", f"{csvdir}/edge_runlen.csv", [("n", "n", 0), ("a", "c", 120)]))
    out["edge_runlen"] = header(libpath) + "".join(runs)
    return out


def _catalog_programs(libpath, variants):
    out = ["options nodate nonumber linesize=200 pagesize=32000;\n", f'libname o "{libpath}";\n']
    for name, stmt in variants.items():
        lib = "c" + name[1:3]
        out.append(f'libname {lib} "{libpath}/cat_{name}";\nproc format library={lib};\n  {stmt}\nrun;\n')
        out.append(f'proc format library={lib} cntlout=o.ctl_{name};\nrun;\n')
        out.append(f'proc catalog cat={lib}.formats; contents; run; quit;\n')
    return "".join(out)


def series_formats(libpath, csvdir):
    """F : formats ISO 8601 / NLS, dates hors plage, heures tres grandes -> fichier texte `put`."""
    vals_dt = ["0", "86400", "1893456000", "-86400", "1e10", "3e11", "-3e10", "2.5"]
    prog = [f'options nodate nonumber linesize=200 pagesize=32000;\nfilename out "{csvdir}/formats_iso_nls.txt";\ndata _null_;\n  file out;\n']
    fmts = ["E8601DA10.", "E8601DT19.", "E8601DT25.", "E8601TM8.", "E8601LZ.", "E8601DN.", "B8601DA8.", "B8601DT15.", "NLDATE.", "NLDATEL.", "NLDATEW.",
            "NLDATM.", "NLTIME.", "NLMNY15.2", "NLNUM15.2", "NLPCT.", "EURDFDE9.", "EURDFDT20.", "EURDFMY7.", "DATE9.", "DATETIME20.", "TIME8.", "HHMM.",
            "MMSS.", "WEEKDATE.", "WORDDATE.", "YYMMDD10.", "MMDDYY10.", "DDMMYY10.", "JULIAN7.", "DTMONYY7."]
    for f in fmts:
        for v in vals_dt:
            prog.append(f"  x={v}; put \"{f}|{v}|\" x {f};\n")
    prog.append("run;\n")
    # heures tres grandes et decimales
    prog.append(f'data _null_;\n  file out mod;\n  do x=0, 3599.999, 86399.5, 86400, 360000, 3600000, 1e8, -1, -3600;\n    put "HHMM|" x best32. "|" x hhmm. "|" x mmss. "|" x time8. "|" x time12.2;\n  end;\nrun;\n')
    return {"formats_iso_nls": "".join(prog)}


def run_script():
    return '''#!/bin/sh
# Execute les programmes du corpus complementaire avec le SAS complet. Usage : SAS_FULL_CMD=<lanceur> sh run_complement.sh (depuis le dossier de travail)
set -u
: "${SAS_FULL_CMD:?definir SAS_FULL_CMD}"
mkdir -p files_complement/csv out_complement
for f in gen_complement/*.sas; do
  n=$(basename "$f" .sas)
  $SAS_FULL_CMD -sysin "$f" -log "out_complement/$n.log" -print "out_complement/$n.lst" -nodate > /dev/null 2>&1
  rc=$?
  e=$(grep -c "^ERROR" "out_complement/$n.log")
  w=$(grep -c "^WARNING" "out_complement/$n.log")
  printf '%s\\t%s\\t%s\\t%s\\n' "$n" "$rc" "$e" "$w" >> out_complement/run_summary.tsv
done
find files_complement -type f | sort | xargs shasum -a 256 > out_complement/sha256.txt 2>/dev/null || find files_complement -type f | sort | xargs sha256sum > out_complement/sha256.txt
'''


def main(argv):
    root = argv[1]
    gdir = os.path.join(root, "gen_complement")
    fdir = os.path.join(root, "files_complement")
    cdir = os.path.join(fdir, "csv")
    os.makedirs(gdir, exist_ok=True)
    os.makedirs(cdir, exist_ok=True)
    progs = {}
    for fn in (series_rows, series_rl, series_big, series_pages, series_edges, series_formats):
        progs.update(fn(os.path.abspath(fdir), os.path.abspath(cdir)))
    # noms de format non natifs : SAS refuse d'ecrire un format utilisateur homonyme d'un format fourni (F, $F)
    progs["catalogs"] = _catalog_programs(os.path.abspath(fdir), {
        "v00_base": "value myf 1='a' 2='b';", "v01_label": "value myf 1='a' 2='c';", "v02_ajout": "value myf 1='a' 2='b' 3='c';",
        "v03_plage": "value myf 1-2='a';", "v04_other": "value myf 1='a' 2='b' other='z';", "v05_lowhigh": "value myf low-1='a' 2-high='b';",
        "v06_char": "value $myf 'x'='a' 'y'='b';", "v07_invalue": "invalue myf 'a'=1 'b'=2;", "v08_picture": "picture myf low-high='000,009.99';",
        "v09_notsorted": "value myf (notsorted) 2='b' 1='a';", "v10_defaut": "value myf (default=12) 1='a' 2='b';", "v11_deux": "value myf 1='a' 2='b';\n  value myg 1='x';"})
    for name, text in progs.items():
        with open(os.path.join(gdir, name + ".sas"), "w") as f:
            f.write(text)
    # les dossiers de bibliotheque de catalogues doivent exister
    for v in ("v00_base", "v01_label", "v02_ajout", "v03_plage", "v04_other", "v05_lowhigh", "v06_char", "v07_invalue", "v08_picture", "v09_notsorted", "v10_defaut", "v11_deux"):
        os.makedirs(os.path.join(fdir, "cat_" + v), exist_ok=True)
    with open(os.path.join(gdir, "run_complement.sh"), "w") as f:
        f.write(run_script())
    print(f"{len(progs)} programmes ecrits dans {gdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
