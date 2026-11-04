#!/usr/bin/env python3
"""Mutations des champs « recopies » d'un fichier ecrit par ref_writer.py, relues par SAS (oracle sas_small).

Usage : python3 -I rea_output/tools/mutate_write.py [identifiants de champs...]    (par defaut : tous)
Pour chaque champ et chaque mutation (zero, aleatoire, 0xFF) : ecrit une copie mutee, la fait relire par SAS (PROC CONTENTS + etape DATA
qui ecrit un CSV) et classe la reaction :
  ignore    journal sans ERROR/WARNING, meme CSV, meme listing PROC CONTENTS (valeurs de metadonnees comprises)
  modifie   journal propre mais CSV ou metadonnees differents
  rejet     ERROR, WARNING, exception ou fichier introuvable
Resultat : rea_output/evidence/write/mutations.tsv (+ journaux dans rea_output/evidence/write/mut/).
"""
import concurrent.futures
import os
import random
import re
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_writer as W  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DIR = os.path.join(REPO, "corpus", "gen", "probe", "write", "files")
GEN = os.path.join(REPO, "corpus", "gen", "probe", "write")
EVID = os.path.join(REPO, "rea_output", "evidence", "write", "mut")
HL = 65536  # taille de l'en-tete de fichier ecrit par ref_writer


def base_files():
    cols = [W.Col("i", "n", 8), W.Col("x", "n", 8), W.Col("s", "c", 10, label="texte", fmt=("$CHAR", 10, 0)), W.Col("d", "n", 8, fmt=("DATE", 9, 0))]
    rows = [[k, k / 4, "v%d" % k, 21915 + k] for k in range(1, 21)]
    ccols = [W.Col("i", "n", 8), W.Col("x", "n", 8), W.Col("a", "c", 40), W.Col("b", "c", 12)]
    crows = [[k, k / 4, "ligne %d" % (k % 7), "ab" * (k % 5)] for k in range(1, 61)]
    return {"U": (cols, rows, {}), "C": (ccols, crows, {"compress": "CHAR"})}


def pointers(b, page):
    base = HL + page * 65536
    t, bc, sc = struct.unpack_from("<HHH", b, base + 32)
    return [struct.unpack_from("<QQBB", b, base + 40 + 24 * i) for i in range(sc)], base


def sub(b, idx, off=0, ln=None):
    ptrs, base = pointers(b, 0)
    o, l, c, t = ptrs[idx]
    return (base + o + off, l - off if ln is None else ln)


def marker_page(b):
    n = struct.unpack_from("<Q", b, 208)[0]
    for p in range(n):
        if struct.unpack_from("<H", b, HL + p * 65536 + 32)[0] == 0x9000:
            return HL + p * 65536
    return None


# (identifiant, description, base, resolveur -> [(offset, longueur)])
FIELDS = [
    ("h.32", "en-tete 32 (33 : adresses 64 bits)", "U", lambda b: [(32, 1)]),
    ("h.33_34", "en-tete 33-34 (22 00)", "U", lambda b: [(33, 2)]),
    ("h.35", "en-tete 35 (33 : alignement a1 = 4)", "U", lambda b: [(35, 1)]),
    ("h.37", "en-tete 37 (01 : little endian)", "U", lambda b: [(37, 1)]),
    ("h.39", "en-tete 39 (31)", "U", lambda b: [(39, 1)]),
    ("h.36", "en-tete 36 (indicateur 33)", "U", lambda b: [(36, 1)]),
    ("h.38", "en-tete 38 (02)", "U", lambda b: [(38, 1)]),
    ("h.platform", "en-tete 40 (code plateforme)", "U", lambda b: [(40, 1)]),
    ("h.47", "en-tete 47 (14)", "U", lambda b: [(47, 1)]),
    ("h.71", "en-tete 71 (14)", "U", lambda b: [(71, 1)]),
    ("h.50_51", "en-tete 50-51 (03 01)", "U", lambda b: [(50, 2)]),
    ("h.52_55", "en-tete 52-55 (18 1F 10 11)", "U", lambda b: [(52, 4)]),
    ("h.74_75", "en-tete 74-75 (03 01)", "U", lambda b: [(74, 2)]),
    ("h.65_68", "en-tete 65-68 (33 01 23 33)", "U", lambda b: [(65, 4)]),
    ("h.64", "en-tete 64 (01)", "U", lambda b: [(64, 1)]),
    ("h.56_63", "en-tete 56-63 (copie de 32-39)", "U", lambda b: [(56, 8)]),
    ("h.73", "en-tete 73 (20)", "U", lambda b: [(73, 1)]),
    ("h.release", "release 9.0401M7", "U", lambda b: [(224, 8)]),
    ("h.host", "hote Linux", "U", lambda b: [(232, 5)]),
    ("h.os_version", "version du systeme", "U", lambda b: [(248, 16)]),
    ("h.machine", "machine x86_64", "U", lambda b: [(280, 6)]),
    ("h.dates", "dates de creation et de modification (168-183)", "U", lambda b: [(168, 16)]),
    ("h.tail_296", "zone 296-327 (dates en entier et XOR)", "U", lambda b: [(296, 16)]),
    ("h.file_code", "code de fichier 328-331", "U", lambda b: [(328, 4)]),
    ("h.date_336", "date 336-343", "U", lambda b: [(336, 8)]),
    ("p.sig", "signature de la page 0 (octets 0-3)", "U", lambda b: [(HL, 4)]),
    ("rs.marker", "RowSize +0x08 (0xF0)", "U", lambda b: [sub(b, 0, 8, 8)]),
    ("rs.field2", "RowSize +0x10 (n+9)", "U", lambda b: [sub(b, 0, 16, 8)]),
    ("rs.flags", "RowSize +0x20 (0x223011)", "U", lambda b: [sub(b, 0, 32, 8)]),
    ("rs.cap", "RowSize +0x78 (capacite page mixte)", "U", lambda b: [sub(b, 0, 120, 8)]),
    ("rs.loc0_1", "RowSize localisateurs 0 et 1 (+0x200..+0x21F)", "U", lambda b: [sub(b, 0, 512, 32)]),
    ("rs.loc2", "RowSize localisateur 2 (+0x220)", "U", lambda b: [sub(b, 0, 544, 16)]),
    ("rs.loc3", "RowSize localisateur 3 (+0x230, derniere page)", "U", lambda b: [sub(b, 0, 560, 16)]),
    ("rs.loc4", "RowSize localisateur 4 (+0x240)", "U", lambda b: [sub(b, 0, 576, 16)]),
    ("rs.page_sig", "RowSize +0x1B8 (signature de la page 0)", "U", lambda b: [sub(b, 0, 0x1B8, 4)]),
    ("rs.tail_refs", "RowSize references de texte +0x2A0..+0x2C7", "U", lambda b: [sub(b, 0, 0x2A0, 40)]),
    ("rs.name_len", "RowSize +0x2EE (longueur max des noms)", "U", lambda b: [sub(b, 0, 0x2EE, 2)]),
    ("rs.tail_2e8", "RowSize +0x2E8 (compteurs 04 00 01 00 01 00 01 00)", "U", lambda b: [sub(b, 0, 0x2E8, 6)]),
    ("rs.fe", "RowSize +0x2FE (capacite + pointeurs)", "U", lambda b: [sub(b, 0, 0x2FE, 2)]),
    ("rs.tail_318", "RowSize +0x318", "U", lambda b: [sub(b, 0, 0x318, 12)]),
    ("rs.58", "RowSize +0x58 (zero dans ref_writer)", "U", lambda b: [sub(b, 0, 0x58, 8)]),
    ("rs.40_rowlen", "RowSize +0x28 (longueur de ligne)", "U", lambda b: [sub(b, 0, 40, 8)]),
    ("rs.nobs", "RowSize +0x30 (nombre de lignes)", "U", lambda b: [sub(b, 0, 48, 8)]),
    ("rs.72_n", "RowSize +0x48 (nombre de colonnes)", "U", lambda b: [sub(b, 0, 72, 8)]),
    ("rs.96_n", "RowSize +0x60 (nombre de colonnes)", "U", lambda b: [sub(b, 0, 96, 8)]),
    ("rs.104_page", "RowSize +0x68 (taille de page)", "U", lambda b: [sub(b, 0, 104, 8)]),
    ("rs.128_136", "RowSize +0x80..+0x8F (tous les bits a 1)", "U", lambda b: [sub(b, 0, 128, 16)]),
    ("rs.776_nobs", "RowSize +0x308 (nombre de lignes, copie)", "U", lambda b: [sub(b, 0, 776, 8)]),
    ("h.magic", "en-tete 0-31 (nombre magique)", "U", lambda b: [(0, 32)]),
    ("h.enc", "en-tete 70 (code d'encodage)", "U", lambda b: [(70, 1)]),
    ("h.sas_file", "en-tete 84-91 (SAS FILE)", "U", lambda b: [(84, 8)]),
    ("h.name", "en-tete 92-123 (nom de table)", "U", lambda b: [(92, 32)]),
    ("h.type", "en-tete 156-163 (DATA)", "U", lambda b: [(156, 8)]),
    ("h.hdrlen", "en-tete 200 (taille d'en-tete)", "U", lambda b: [(200, 4)]),
    ("h.pagelen", "en-tete 204 (taille de page)", "U", lambda b: [(204, 4)]),
    ("h.pagecount", "en-tete 208 (nombre de pages)", "U", lambda b: [(208, 8)]),
    ("pg.4_23", "page 0 : octets 4-23", "U", lambda b: [(HL + 4, 20)]),
    ("pg.type", "page 0 : type", "U", lambda b: [(HL + 32, 2)]),
    ("pg.bc", "page 0 : block_count", "U", lambda b: [(HL + 34, 2)]),
    ("pg.sc", "page 0 : subheader_count", "U", lambda b: [(HL + 36, 2)]),
    ("ptr.type_rowsize", "pointeur RowSize : type (octet 17)", "U", lambda b: [(HL + 40 + 17, 1)]),
    ("ptr.type_text", "pointeur ColumnText : type (octet 17)", "U", lambda b: [(HL + 40 + 24 * 3 + 17, 1)]),
    ("ptr.comp", "pointeur ColumnText : octet de compression (16)", "U", lambda b: [(HL + 40 + 24 * 3 + 16, 1)]),
    ("ptr.pad", "pointeur ColumnText : octets 18-23", "U", lambda b: [(HL + 40 + 24 * 3 + 18, 6)]),
    ("cs.pad", "ColumnSize octets 16-23", "U", lambda b: [sub(b, 1, 16, 8)]),
    ("nm.hdr", "ColumnName : longueur et zeros (8-15)", "U", lambda b: [sub(b, 4, 8, 8)]),
    ("nm.entry_pad", "ColumnName : 4e mot de la 1re entree", "U", lambda b: [sub(b, 4, 16 + 6, 2)]),
    ("at.hdr", "ColumnAttributes : longueur et zeros (8-15)", "U", lambda b: [sub(b, 5, 8, 8)]),
    ("at.pad", "ColumnAttributes : octet de remplissage de la 1re entree", "U", lambda b: [sub(b, 5, 16 + 15, 1)]),
    ("fl.widths", "FormatAndLabel : largeurs et decimales (0x18-0x1F)", "U", lambda b: [sub(b, 8, 0x18, 8)]),
    ("fl.refs", "FormatAndLabel : references de texte (0x28-0x39)", "U", lambda b: [sub(b, 8, 0x28, 18)]),
    ("cn.m1", "SubheaderCounts +0x08 (taille du texte)", "U", lambda b: [sub(b, 2, 8, 8)]),
    ("cs.m1", "ColumnSize : nombre de colonnes", "U", lambda b: [sub(b, 1, 8, 8)]),
    ("cn.hdr", "SubheaderCounts +0x10..+0x1F (compteurs d'en-tete)", "U", lambda b: [sub(b, 2, 16, 16)]),
    ("cn.const_112", "SubheaderCounts +0x70 (0x070C)", "U", lambda b: [sub(b, 2, 112, 8)]),
    ("cn.entry0", "SubheaderCounts entree 0 (signature et positions)", "U", lambda b: [sub(b, 2, 120, 40)]),
    ("cn.entry3_6", "SubheaderCounts entrees 3 a 6", "U", lambda b: [sub(b, 2, 240, 160)]),
    ("tx.enc", "ColumnText octets 8-11 (code d'encodage)", "U", lambda b: [sub(b, 3, 16, 4)]),
    ("tx.spaces", "ColumnText octets 12-27 (blancs)", "U", lambda b: [sub(b, 3, 20, 16)]),
    ("tx.datastep", "ColumnText octets 28-35 (DATASTEP)", "U", lambda b: [sub(b, 3, 36, 8)]),
    ("fl.head", "FormatAndLabel octets 8-23 (zeros)", "U", lambda b: [sub(b, 6, 8, 16)]),
    ("fl.tail", "FormatAndLabel octets 58-63", "U", lambda b: [sub(b, 6, 58, 6)]),
    ("at.flags", "ColumnAttributes drapeaux du nom (0x0400/0x0800)", "U", lambda b: [sub(b, 5, 8 + 8 + 12, 2)]),
    ("pg.free", "page 0 : free_bytes (octets 24-31)", "U", lambda b: [(HL + 24, 8)]),
    ("pg.38_39", "page 0 : octets 38-39", "U", lambda b: [(HL + 38, 2)]),
    # tables compressees
    ("zc.rs_40", "compresse : RowSize +0x40 (2)", "C", lambda b: [sub(b, 0, 0x40, 8)]),
    ("zc.rs_24a", "compresse : RowSize +0x24A (1)", "C", lambda b: [sub(b, 0, 0x24A, 1)]),
    ("zc.rs_tail", "compresse : RowSize references +0x2A0..+0x2C7", "C", lambda b: [sub(b, 0, 0x2A0, 40)]),
    ("zc.rs_field2", "compresse : RowSize +0x10", "C", lambda b: [sub(b, 0, 16, 8)]),
    ("zc.rs_loc2", "compresse : RowSize localisateur 2", "C", lambda b: [sub(b, 0, 544, 16)]),
    ("zc.rs_loc3", "compresse : RowSize localisateur 3", "C", lambda b: [sub(b, 0, 560, 16)]),
    ("zc.literal", "compresse : litteral SASYZCRL dans ColumnText", "C", lambda b: [sub(b, 3, 20, 8)]),
    ("zc.mk_hdr", "marqueur 0x9000 : en-tete (octets 24-39)", "C", lambda b: [(marker_page(b) + 24, 16)]),
    ("zc.mk_c0", "marqueur 0x9000 : lignes de la premiere page (32756)", "C", lambda b: [(marker_page(b) + 32756, 1)]),
    ("zc.mk_pageno", "marqueur 0x9000 : numero de page (32757)", "C", lambda b: [(marker_page(b) + 32757, 1)]),
    ("zc.mk_d", "marqueur 0x9000 : pointeurs de la premiere page (32765)", "C", lambda b: [(marker_page(b) + 32765, 2)]),
]


def mutate(b, regions, kind, rnd):
    out = bytearray(b)
    for off, ln in regions:
        old = bytes(out[off:off + ln])
        for _ in range(8):
            if kind == "zero":
                new = bytes(ln)
            elif kind == "ff":
                new = b"\xff" * ln
            else:
                new = bytes(rnd.randrange(256) for _ in range(ln))
            if new != old:
                break
        else:
            new = bytes((x + 1) & 0xFF for x in old)  # la mutation aurait redonne la valeur d'origine
        out[off:off + ln] = new
    return bytes(out)


def sas_program(stem, cols):
    puts = " ".join(f"{c.name} :best32." if c.type == "n" else f"{c.name} :$quote{c.length + 2}." for c in cols)
    return "\n".join(['options nodate nonumber linesize=200 pagesize=32000;', 'libname o "/work/gen/probe/write/files";',
                      f'proc contents data=o.{stem}; run;',
                      f'data _null_; set o.{stem}; file "/work/out/{stem}.csv" dlm="," lrecl=1000000;', f'  put {puts};', 'run;']) + "\n"


KEYS = (r"Observations\s+(\d+)", r"Variables\s+(\d+)", r"Compressed\s+(\S+)", r"Observation Length\s+(\d+)", r"Deleted Observations\s+(\d+)",
        r"Encoding\s+(\S+)", r"Release Created\s+(\S+)", r"Host Created\s+(\S+)", r"Data Set Page Size\s+(\d+)", r"Number of Data Set Pages\s+(\d+)",
        r"Data Representation\s+(\S+)", r"Indexes\s+(\d+)")


def norm_listing(text):
    keep = []
    for k in KEYS:
        m = re.search(k, text)
        keep.append(k.split("\\")[0].strip() + "=" + (m.group(1) if m else "?"))
    for l in text.splitlines():
        s = l.strip()
        if re.match(r"^\d+\s+\S+\s+(Num|Char)", s):
            keep.append(re.sub(r"\s+", " ", s))
    return "\n".join(keep)


def run_one(args):
    stem, cols, data = args
    path = os.path.join(DIR, stem + ".sas7bdat")
    open(path, "wb").write(data)
    prog = os.path.join(GEN, stem + ".sas")
    open(prog, "w").write(sas_program(stem, cols))
    hung = False
    try:
        subprocess.run([os.path.join(REPO, "oracle", "run_sas.sh"), f"gen/probe/write/{stem}.sas"], capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:  # SAS boucle sur certains fichiers mutes : arreter le conteneur de ce programme
        hung = True
        for cid in subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True).stdout.split():
            if f"{stem}.sas" in subprocess.run(["docker", "inspect", "--format", "{{.Args}}", cid], capture_output=True, text=True).stdout:
                subprocess.run(["docker", "kill", cid], capture_output=True)
    out = os.path.join(REPO, "corpus", "out")
    log = open(os.path.join(out, stem + ".log"), errors="replace").read()
    lst = open(os.path.join(out, stem + ".lst"), errors="replace").read() if os.path.exists(os.path.join(out, stem + ".lst")) else ""
    csvp = os.path.join(out, stem + ".csv")
    csv = open(csvp, errors="replace").read() if os.path.exists(csvp) else None
    bad = [l for l in log.splitlines() if l.startswith(("ERROR", "WARNING")) or "Segmentation" in l or "exception" in l.lower()]
    if hung:
        bad = ["BOUCLE : SAS ne termine pas (arret apres 90 s)"] + bad
    for ext in (".log", ".lst", ".csv"):
        f = os.path.join(out, stem + ext)
        if os.path.exists(f):
            shutil.move(f, os.path.join(EVID, stem + ext)) if ext != ".csv" else os.remove(f)
    for f in (path, prog):
        os.remove(f)
    return bad, norm_listing(lst), csv


def main(argv):
    os.makedirs(EVID, exist_ok=True)
    wanted = set(argv[1:])
    bases = {}
    for k, (cols, rows, kw) in base_files().items():
        p = os.path.join(DIR, f"mutbase_{k}.sas7bdat")
        W.write(p, cols, rows, seed=11, **kw)
        bases[k] = (cols, open(p, "rb").read())
        os.remove(p)
    ref = {}
    jobs = []
    for k, (cols, data) in bases.items():
        jobs.append((f"mb_{k.lower()}", cols, data))
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        for (stem, cols, data), res in zip(jobs, ex.map(run_one, jobs)):
            ref[stem[-1].upper()] = res
            print("reference", stem, "journal propre" if not res[0] else res[0][:2], flush=True)
    jobs, meta = [], []
    rnd = random.Random(2026)
    n = 0
    for fid, desc, kind, res in FIELDS:
        if wanted and fid not in wanted:
            continue
        cols, data = bases[kind]
        try:
            regions = res(data)
        except Exception as e:  # noqa: BLE001
            print("champ ignore", fid, e)
            continue
        for mk in ("zero", "rand", "ff"):
            n += 1
            stem = f"m{n:03d}"
            jobs.append((stem, cols, mutate(data, regions, mk, rnd)))
            meta.append((fid, desc, kind, mk, regions, stem))
    lines = ["identifiant\tmutation\tbase\treaction\tdetail\tjournal"]
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        for m, res in zip(meta, ex.map(run_one, jobs)):
            fid, desc, kind, mk, regions, stem = m
            bad, lst, csv = res
            rbad, rlst, rcsv = ref[kind]
            if bad:
                react, det = "rejet", bad[0][:90]
            elif csv != rcsv:
                react, det = "modifie", "donnees differentes"
            elif lst != rlst:
                a = set(lst.splitlines()) ^ set(rlst.splitlines())
                react, det = "modifie", "metadonnees : " + "; ".join(sorted(a))[:120]
            else:
                react, det = "ignore", ""
            lines.append(f"{fid}\t{mk}\t{kind}\t{react}\t{det}\tevidence/write/mut/{stem}.log")
            print(f"{fid:14s} {mk:5s} {react:8s} {det}", flush=True)
    tsv = os.path.join(REPO, "rea_output", "evidence", "write", "mutations.tsv")
    old = {}
    if os.path.exists(tsv):
        for l in open(tsv).read().splitlines()[1:]:
            f = l.split("\t")
            old[(f[0], f[1])] = l
    for l in lines[1:]:
        f = l.split("\t")
        old[(f[0], f[1])] = l
    order = {fid: i for i, (fid, *_r) in enumerate(FIELDS)}
    merged = sorted([kv for kv in old.items() if kv[0][0] in order], key=lambda kv: (order.get(kv[0][0], 999), ("zero", "rand", "ff").index(kv[0][1])))
    open(tsv, "w").write("\n".join([lines[0]] + [v for _, v in merged]) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
