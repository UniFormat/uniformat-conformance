#!/usr/bin/env python3
"""Genere les programmes SAS du corpus (un par famille) et la table de metadonnees.

Pourquoi un script hote : dans sas_small, ni les macros SAS, ni la plupart des fonctions DATA,
ni ARRAY, ni PROC SORT/FORMAT/SQL/EXPORT ne fonctionnent (voir rea_output/STATE.md). Les
programmes sont donc du SAS "plat", ecrit litteralement par ce script.

Usage (depuis la racine du depot) :
    python3 -I corpus/gen/build_programs.py                      # oracle sas_small, chemins /work
    python3 -I corpus/gen/build_programs.py --root /chemin/corpus --outdir /tmp/gen_full

Sorties dans --outdir (defaut corpus/gen) :
    <famille>.sas        variantes COMPRESS=NO         (tourne sur sas_small)
    <famille>_comp.sas   variantes COMPRESS=CHAR/BINARY (SAS complet : sas_small ne sait pas)
    full_*.sas           lignes supprimees, index, catalogue de formats (SAS complet)
    tables.tsv           une ligne par table : famille, variante, parametre varie, reference...
"""
import argparse
import os

ap = argparse.ArgumentParser()
ap.add_argument("--root", default="/work", help="racine du corpus vue par SAS (defaut /work)")
ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__))))
ap.add_argument("--files-dir", default="files", help="sous-dossier de la racine recevant les fichiers (defaut files ; "
                "files_sas_small pour l'oracle sas_small, afin de ne pas ecraser les fichiers du SAS complet)")
args = ap.parse_args()
ROOT = args.root.rstrip("/")
FILES_DIR = args.files_dir.strip("/")


class T:
    def __init__(self, fam, var, param, ref, body, opts="", cols=None, oracle="small", note="", comp="no", fmt=""):
        self.fam, self.var, self.param, self.ref = fam, var, param, ref
        self.body, self.opts, self.oracle, self.note, self.comp = body, opts, oracle, note, comp
        self.cols = cols or []  # [(nom, 'n'|'c')]
        self.fmt = fmt  # instructions format/informat/label placees avant output (dans body deja)

    @property
    def name(self):
        return f"{self.fam}_{self.var}_{self.comp}"

    def with_comp(self, comp):
        t = T(self.fam, self.var, "compression = " + comp.upper() + " (reference : meme table en NO)",
              f"{self.fam}_{self.var}_no", self.body, self.opts, self.cols, "full", self.note, comp)
        return t


def mix(n):
    return f"length c $5; do i=1 to {n}; x=i*1.5; c=put(i,z5.); output; end;"


MIXCOLS = [("i", "n"), ("x", "n"), ("c", "c", 5)]
tables = []

# ---------------------------------------------------------------- base
for n in (0, 1, 2, 100, 3000):
    tables.append(T("base", f"n{n}_mix", f"nombre de lignes = {n}", "base_n100_mix_no" if n != 100 else "(reference)",
                    mix(n), cols=MIXCOLS))
tables.append(T("base", "n100_num", "colonnes = 1 numerique", "base_n100_mix_no",
                "do i=1 to 100; output; end;", cols=[("i", "n")]))
tables.append(T("base", "n100_chr", "colonnes = 1 caractere", "base_n100_mix_no",
                "length c $5; do i=1 to 100; c=put(i,z5.); output; end;", "keep=c", cols=[("c", "c", 5)]))

# ---------------------------------------------------------------- types
for L in (3, 4, 5, 6, 7, 8):
    tables.append(T("types", f"num{L}", f"longueur numerique = {L}", "types_num8_no" if L != 8 else "(reference)",
                    f"length x {L}; do i=1 to 20; x=i*1.25; output; end;", cols=[("i", "n"), ("x", "n")]))
for L in (1, 8, 200, 32767):
    tables.append(T("types", f"char{L}", f"longueur caractere = {L}", "types_char8_no" if L != 8 else "(reference)",
                    f'length c $ {L}; do i=1 to 20; c="a"; output; end;', cols=[("i", "n"), ("c", "c", L)]))

# ---------------------------------------------------------------- valeurs
letters = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
stmts = ["x=.; output;", "x=._; output;"] + [f"x=.{l}; output;" for l in letters]
tables.append(T("valeurs", "manquants", "valeurs manquantes (. ._ .A-.Z)", "(sans reference : une valeur par ligne)",
                " ".join(stmts), cols=[("x", "n")],
                note="infinis et NaN : SAS ne sait pas en produire (aucune syntaxe), non generes"))
ext = ["0", "1", "-1", "1e-300", "-1e-300", "1e300", "-1e300", "2.2250738585072014e-308",
       "1.7976931348623157e308", "123456789012345", "0.1", "9007199254740992"]
tables.append(T("valeurs", "extremes", "valeurs extremes", "(sans reference : une valeur par ligne)",
                " ".join(f"x={v}; output;" for v in ext), cols=[("x", "n")]))
tables.append(T("valeurs", "chaines", "contenus de chaine (vide, blancs, tabulation)", "(sans reference : une valeur par ligne)",
                'length c $10; c=""; output; c=" "; output; c="  a"; output; c="a  "; output; c="09"x; output; c="6109"x; output;',
                cols=[("c", "c", 10)]))

# ---------------------------------------------------------------- metadonnees
lab256 = "L" * 256
tables.append(T("metadonnees", "ref", "(reference)", "(reference)", "x=1234.5; output;", cols=[("x", "n")]))
tables.append(T("metadonnees", "nom1", "nom de variable = 1 caractere", "metadonnees_ref_no", "a=1234.5; output;", cols=[("a", "n")]))
n32 = "abcdefghijklmnopqrstuvwxyz123456"
tables.append(T("metadonnees", "nom32", "nom de variable = 32 caracteres", "metadonnees_ref_no", f"{n32}=1234.5; output;", cols=[(n32, "n")]))
tables.append(T("metadonnees", "lab_ascii", "label de variable ASCII court", "metadonnees_ref_no",
                'x=1234.5; label x="Un label ASCII"; output;', cols=[("x", "n")]))
tables.append(T("metadonnees", "lab256", "label de variable = 256 caracteres", "metadonnees_ref_no",
                f'x=1234.5; label x="{lab256}"; output;', cols=[("x", "n")]))
tables.append(T("metadonnees", "lab_utf8", "label de variable non ASCII", "metadonnees_ref_no",
                'x=1234.5; label x="Libellé accentué é ü ñ — 日本"; output;', cols=[("x", "n")]))
tables.append(T("metadonnees", "tablabel", "label de table", "metadonnees_ref_no", "x=1234.5; output;", 'label="Etiquette de table"', cols=[("x", "n")]))
fmts = [("date9", "d", "date9."), ("datetime19", "d", "datetime19."), ("time8", "d", "time8."),
        ("dollar12_2", "d", "dollar12.2"), ("best12", "d", "best12."), ("comma10_2", "d", "comma10.2"),
        ("percent8_1", "d", "percent8.1"), ("e10", "d", "e10.")]
for tag, v, f in fmts:
    tables.append(T("metadonnees", f"fmt_{tag}", f"format de variable = {f}", "metadonnees_ref_no",
                    f"d=21000.5; format d {f}; output;", cols=[("d", "n")]))
    if tag in ("date9", "datetime19", "time8", "comma10_2"):
        tables.append(T("metadonnees", f"infmt_{tag}", f"informat de variable = {f}", "metadonnees_ref_no",
                        f"d=21000.5; informat d {f}; output;", cols=[("d", "n")]))
tables.append(T("metadonnees", "fmt_char20", "format de variable = $char20.", "metadonnees_ref_no",
                'length c $20; c="abc"; format c $char20.; output;', cols=[("c", "c", 20)]))
tables.append(T("metadonnees", "infmt_char20", "informat de variable = $char20.", "metadonnees_ref_no",
                'length c $20; c="abc"; informat c $char20.; output;', cols=[("c", "c", 20)]))

# ---------------------------------------------------------------- taille
tables.append(T("taille", "n50000", "nombre de lignes = 50000 (plusieurs pages)", "base_n3000_mix_no", mix(50000), cols=MIXCOLS))
for b in (4096, 8192, 65536, 131072):
    tables.append(T("taille", f"buf{b}", f"taille de page (BUFSIZE) = {b}", "taille_buf65536_no" if b != 65536 else "(reference)",
                    mix(3000), f"bufsize={b}", MIXCOLS))
for w in (300, 5000):
    names = [f"x{j:04d}" for j in range(1, w + 1)]
    body = "do r=1 to 3;\n  " + "\n  ".join(f"{nm}=r;" for nm in names) + "\n  output; end;"
    tables.append(T("taille", f"wide{w}", f"nombre de colonnes numeriques = {w}", "(reference : wide300)" if w == 5000 else "(reference)",
                    body, cols=[("r", "n")] + [(nm, "n") for nm in names],
                    note="5000 colonnes : doit depasser la capacite d'un sous-en-tete de noms"
                    if w == 5000 else ""))

# ---------------------------------------------------------------- encodage
for enc, tag in (("utf-8", "utf8"), ("latin1", "latin1"), ("wlatin1", "wlatin1")):
    tables.append(T("encodage", tag, f"encodage = {enc}", "encodage_utf8_no" if tag != "utf8" else "(reference)",
                    'length c $20; c="Café été ñ"; output;', f"encoding='{enc}'", [("c", "c", 20)]))

# ---------------------------------------------------------------- plateforme (OUTREP=)
for rep, tag in (("LINUX_X86_64", "linux_x86_64"), ("LINUX_32", "linux_32"), ("WINDOWS_32", "windows_32"),
                 ("WINDOWS_64", "windows_64"), ("SOLARIS_64", "solaris_64"), ("HP_UX_32", "hp_ux_32"),
                 ("RS_6000_AIX_64", "aix_64")):
    tables.append(T("plateforme", tag, f"representation des donnees (OUTREP) = {rep}",
                    "plateforme_linux_x86_64_no" if tag != "linux_x86_64" else "(reference)",
                    mix(100), f"outrep={rep}", MIXCOLS,
                    note="fichier ecrit par SAS avec OUTREP= (representation emulee, pas produit sur l'OS d'origine)"))

# ---------------------------------------------------------------- compression (donnees faites pour etre compressibles)
# SAS desactive la compression quand le surcout par ligne depasse le gain : les autres familles ont des lignes
# trop courtes pour compresser. Cette famille a des lignes longues et compressibles ; chaque table existe en
# NO / CHAR / BINARY (seul le mode de compression change).
import random
rnd = random.Random(20261030)
alnum = "abcdefghijklmnopqrstuvwxyz0123456789"
CP = "compression"
tables.append(T(CP, "blank200", "(reference NO) ligne = 3 caracteres + 197 blancs", "(reference)",
                'length c $200; do i=1 to 200; c="abc"; output; end;', cols=[("i", "n"), ("c", "c", 200)]))
tables.append(T(CP, "pat2", "(reference NO) motif de 2 octets repete", "(reference)",
                f'length c $200; do i=1 to 200; c="{"ab" * 100}"; output; end;', cols=[("i", "n"), ("c", "c", 200)]))
tables.append(T(CP, "pat4", "(reference NO) motif de 4 octets repete", "(reference)",
                f'length c $500; do i=1 to 200; c="{"abcd" * 125}"; output; end;', cols=[("i", "n"), ("c", "c", 500)]))
tables.append(T(CP, "pat7", "(reference NO) motif de 7 octets repete", "(reference)",
                f'length c $500; do i=1 to 200; c="{"abcdefg" * 71}"; output; end;', cols=[("i", "n"), ("c", "c", 500)]))
zn = [f"z{j:02d}" for j in range(1, 21)]
tables.append(T(CP, "zeros", "(reference NO) 20 colonnes numeriques a zero", "(reference)",
                "do i=1 to 100;\n  " + "\n  ".join(f"{n}=0;" for n in zn) + "\n  output; end;",
                cols=[("i", "n")] + [(n, "n") for n in zn]))
noise = "\n  ".join(f'i={k}; c="{"".join(rnd.choice(alnum) for _ in range(200))}"; output;' for k in range(1, 21))
tables.append(T(CP, "noise", "(reference NO) 20 lignes de 200 caracteres pseudo-aleatoires (peu compressibles)", "(reference)",
                "length c $200;\n  " + noise, cols=[("i", "n"), ("c", "c", 200)]))
runs = [2, 3, 4, 5, 15, 16, 17, 18, 19, 20, 30, 63, 64, 65, 127, 128, 129, 255, 256, 257, 300, 500]
rows = []
k_row = 0
for byte in (0x78, 0x40, 0x00, 0xFF, 0x20):
    for n in runs:
        k_row += 1
        hexs = f"{byte:02x}" * n + "454e44"  # n fois l'octet, puis "END"
        rows.append(f'i={k_row}; k={byte}; n={n}; c="{hexs}"x; output;')
tables.append(T(CP, "runs", "(reference NO) suites d'un meme octet de longueur 2 a 500 (octets 78 40 00 FF 20) suivies de END",
                "(reference)", "length c $1100;\n  " + "\n  ".join(rows),
                cols=[("i", "n"), ("k", "n"), ("n", "n"), ("c", "c", 1100)],
                note="les octets non imprimables sont ecrits dans le CSV tels que stockes (voir fichier .csv)"))

small_tables = list(tables)
comp_tables = []
dropped_long = []  # un nom de membre SAS fait 32 octets au plus : ces variantes n'existent pas (constate avec le SAS complet)
for t in small_tables:
    for c in ("char", "binary"):
        tc = t.with_comp(c)
        if len(tc.name.encode("utf-8")) > 32:
            dropped_long.append(tc.name)
        else:
            comp_tables.append(tc)
with open(os.path.join(args.outdir, "dropped_long_names.tsv"), "w", encoding="utf-8") as f:
    f.write("fichier\traison\n")
    for n in dropped_long:
        f.write(f"{n}\tnom de table > 32 octets (limite SAS)\n")

# ---------------------------------------------------------------- full seulement
full_tables = []
base = "base_n100_mix"
for c in ("no", "char", "binary"):
    full_tables.append(T("suppression", f"n100_del10", "lignes supprimees (10 sur 100)", f"{base}_no",
                         "", cols=MIXCOLS, oracle="full", comp=c,
                         note="MODIFY ... REMOVE ; absent de sas_small (BRIDGE FAILURE sasyoix/sase7yd)"))
full_tables.append(T("index", "n100_ix", "index simple sur i", f"{base}_no", "", cols=MIXCOLS, oracle="full",
                     note="PROC DATASETS INDEX CREATE ; produit aussi un .sas7bndx"))
full_tables.append(T("catalogue", "fmtuser", "format utilisateur (PROC FORMAT) lie a une colonne", f"{base}_no", "",
                     cols=MIXCOLS, oracle="full", note="produit aussi formats.sas7bcat et un CNTLOUT"))
full_tables.append(T("encodage", "sjis", "encodage = shift-jis", "encodage_utf8_no",
                     'length c $20; c="日本語"; output;', "encoding='shift-jis'", [("c", "c", 20)], oracle="full"))


# ================================================================ rendu
def libpath(fam):
    return f"{ROOT}/{FILES_DIR}/{fam}"


def csv_step(t, lib):
    """CSV de reference : sans DSD (DSD ecrit '.' comme une cellule vide) ; numeriques avec :best32. (le code
    de missing est ecrit tel qu'affiche : . _ A-Z), caracteres avec :$quoteN. (espaces de tete conserves)."""
    names = [c[0] for c in t.cols]
    items = []
    for c in t.cols:
        if c[1] == "n":
            items.append(f"{c[0]} :best32.")
        else:
            items.append(f"{c[0]} :$quote{min(c[2] + 2, 32767)}.")
    path = f"{libpath(t.fam)}/{t.name}.csv"
    out = [f'data _null_; file "{path}" lrecl=1000000;']
    for k in range(0, len(names), 150):
        last = k + 150 >= len(names)
        out.append(f'  put "{",".join(names[k:k+150])}{"" if last else ","}"' + (";" if last else " @;"))
    out.append("run;")
    out.append(f'data _null_; set {lib}.{t.name}; file "{path}" mod dlm="," lrecl=1000000;')
    for k in range(0, len(items), 300):
        out.append("  put " + " ".join(items[k:k + 300]) + (" @;" if k + 300 < len(items) else ";"))
    out.append("run;")
    return "\n".join(out)


def listing(name, dsname, lib="o"):
    """CONTENTS et PRINT dans le listing du programme, separes par des titres-marqueurs (decoupes ensuite par split_listing.py)."""
    return [f'title1 "@@@ {name} contents";', f"proc contents data={lib}.{dsname}; run;",
            f'title1 "@@@ {name} print";', f"proc print data={lib}.{dsname}; run;", "title1;"]


def table_block(t, lib="o"):
    opts = []
    if t.comp != "no":
        opts.append(f"compress={t.comp}")
    else:
        opts.append("compress=no")
    if t.opts:
        opts.append(t.opts)
    s = [f"data {lib}.{t.name}({' '.join(opts)});", f"  {t.body}", "run;"]
    s += listing(t.name, t.name, lib)
    s.append(csv_step(t, lib))
    return "\n".join(s)


def write_program(fname, header, blocks_by_fam):
    lines = [f"/* {header} */", "/* Genere par corpus/gen/build_programs.py : ne pas modifier a la main. */",
             "options nodate nonumber linesize=200 pagesize=32000;"]
    for fam, blocks in blocks_by_fam.items():
        lines.append(f'libname o "{libpath(fam)}";')
        lines += blocks
    with open(os.path.join(args.outdir, fname), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


fams = []
for t in small_tables:
    if t.fam not in fams:
        fams.append(t.fam)
programs = []
for fam in fams:
    write_program(f"{fam}.sas", f"famille {fam} : variantes COMPRESS=NO",
                  {fam: [table_block(t) for t in small_tables if t.fam == fam]})
    programs.append((f"{fam}.sas", "small"))
    write_program(f"{fam}_comp.sas", f"famille {fam} : variantes COMPRESS=CHAR et BINARY (SAS complet)",
                  {fam: [table_block(t) for t in comp_tables if t.fam == fam]})
    programs.append((f"{fam}_comp.sas", "full"))

# suppression : lignes supprimees via MODIFY ... REMOVE
sup = []
for c in ("no", "char", "binary"):
    nm = f"suppression_n100_del10_{c}"
    sup += [f'libname b "{libpath("base")}";',
            f"data o.{nm}(compress={c}); set b.base_n100_mix_no; run;",
            f"data o.{nm}; modify o.{nm}; if i in (3,13,23,33,43,53,63,73,83,93) then remove; run;",
            ] + listing(nm, nm)
    t = [x for x in full_tables if x.fam == "suppression" and x.comp == c][0]
    sup.append(csv_step(t, "o"))
write_program("full_suppression.sas", "lignes supprimees (SAS complet seulement)", {"suppression": sup})
programs.append(("full_suppression.sas", "full"))

ix = [f'libname b "{libpath("base")}";', "data o.index_n100_ix_no(compress=no); set b.base_n100_mix_no; run;",
      "proc datasets lib=o nolist; modify index_n100_ix_no; index create ix=(i); quit;",
      ] + listing("index_n100_ix_no", "index_n100_ix_no")
ixt = [x for x in full_tables if x.fam == "index"][0]
ixt.comp = "no"
ix.append(csv_step(ixt, "o"))
write_program("full_index.sas", "index simple (SAS complet seulement)", {"index": ix})
programs.append(("full_index.sas", "full"))

cat = [f'libname b "{libpath("base")}";', f'libname fmtlib "{libpath("catalogue")}";',
       "proc format library=fmtlib; value ff 1='un' 2='deux' 3-high='plus' other='autre'; invalue inf 'a'=1 'b'=2; picture pp low-high='000.00'; run;",
       f'proc format library=fmtlib cntlout=o.catalogue_cntlout; run;',
       "data o.catalogue_fmtuser_no(compress=no); set b.base_n100_mix_no; format i ff.; run;",
       ] + listing("catalogue_fmtuser_no", "catalogue_fmtuser_no") + ['title1 "@@@ catalogue_fmtlib print";', "proc format library=fmtlib fmtlib; run;", "title1;"]
ctab = [x for x in full_tables if x.fam == "catalogue"][0]
cat.append(csv_step(ctab, "o"))
write_program("full_catalogue.sas", "catalogue de formats (SAS complet seulement)", {"catalogue": cat})
programs.append(("full_catalogue.sas", "full"))

write_program("full_encodage.sas", "encodages exotiques (SAS complet seulement)",
              {"encodage": [table_block([x for x in full_tables if x.var == "sjis"][0])]})
programs.append(("full_encodage.sas", "full"))

# ---------------------------------------------------------------- tables.tsv et programmes.tsv
with open(os.path.join(args.outdir, "tables.tsv"), "w", encoding="utf-8") as f:
    f.write("fichier\tfamille\tvariante\tparametre_varie\treference\tcompression\toracle\tnote\n")
    for t in small_tables + comp_tables + full_tables:
        f.write("\t".join([t.name, t.fam, t.var, t.param, t.ref, t.comp, t.oracle, t.note]) + "\n")
with open(os.path.join(args.outdir, "programmes.tsv"), "w", encoding="utf-8") as f:
    f.write("programme\toracle\n")
    for p, o in programs:
        f.write(f"{p}\t{o}\n")
print(f"{len(small_tables)} tables NO, {len(comp_tables)} tables CHAR/BINARY, {len(full_tables)} tables SAS complet seul ;"
      f" {len(programs)} programmes ; fichiers ecrits dans {args.outdir}")
