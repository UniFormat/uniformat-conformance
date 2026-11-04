"""Tests des compresseurs et decompresseurs de reference sur les vecteurs de compression_vectors/ et sur des cas synthetiques.

Usage : python3 -I rea_output/tools/test_compression.py   (code retour 1 si un test echoue)
"""
import csv, os, random, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref_compress import *

VD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compression_vectors") + os.sep
ALG = {"char.tsv": (rle_decompress, rle_compress, "RLE"),
       "binary.tsv": (rdc_decompress, rdc_compress, "RDC")}
res = {}
def rec(k, ok, msg=""):
    r = res.setdefault(k, [0, 0, []])
    r[0 if ok else 1] += 1
    if not ok and len(r[2]) < 5:
        r[2].append(msg)

def cmd_stats(name, comp):
    pass

for f, (dec, comp, nm) in ALG.items():
    rows = list(csv.DictReader(open(VD + f), delimiter="\t"))
    brutes = []
    for r in rows:
        L = int(r["longueur_ligne"])
        st = bytes.fromhex(r["stocke_hex"]); br = bytes.fromhex(r["brut_hex"])
        if r["stockage"] == "compressed":
            try:
                o = dec(st, L)
                if r["brut_hex"]:
                    rec(f"1 {nm} decompress == brut", o == br, r["id"])
                else:
                    rec(f"2 {nm} sans brut: pas d'exception, longueur", len(o) == L, r["id"])
            except Exception as e:
                rec(f"1 {nm} decompress == brut" if r["brut_hex"] else f"2 {nm} sans brut: pas d'exception, longueur", False, r["id"] + " " + repr(e))
        if r["brut_hex"]:
            brutes.append((r["id"], br))
    for i, b in brutes:
        try:
            rec(f"3 {nm} aller-retour lignes connues", dec(comp(b), len(b)) == b, i)
        except Exception as e:
            rec(f"3 {nm} aller-retour lignes connues", False, i + " " + repr(e))

# 4 synthetiques
rnd = random.Random(1)
syn = [("vide", b""), ("1 octet", b"x"), ("5000 identiques", b"\x41" * 5000), ("aleatoire 1000", bytes(rnd.randrange(256) for _ in range(1000)))]
for rng in (range(2, 21), range(60, 71), range(255, 261), range(4100, 4121)):
    for n in rng:
        for b in (0x78, 0x40, 0x20, 0x00, 0xFF):
            syn.append((f"{n}x{b:02x}", bytes([b]) * n))
for p in (3, 4, 7):
    pat = bytes(rnd.randrange(256) for _ in range(p))
    syn.append((f"periode {p} x300", pat * 300))
    syn.append((f"periode {p} x300 ascii", bytes(range(65, 65 + p)) * 300))
# melanges
mix = bytearray()
for _ in range(300):
    mix += bytes([rnd.choice([0, 0x20, 0x40, 7])]) * rnd.randrange(1, 40) + bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 30)))
syn.append(("melange", bytes(mix)))
syn.append(("longs 4113/4112/4114/8300", b"a"*4113+b" "*4112+b"\x00"*4114+b"@"*8300+b"z"*9000))
syn.append(("run 4114+1 / 4113+1", b" "*4113+b"y"+b" "*4114+b"y"+b"\x00"*4113+b"y"))
for nm_, b in syn:
    for f, (dec, comp, nm) in ALG.items():
        try:
            rec(f"4 {nm} synthetiques aller-retour", dec(comp(b), len(b)) == b, nm_)
        except Exception as e:
            rec(f"4 {nm} synthetiques aller-retour", False, nm_ + " " + repr(e))

# couverture des commandes RDC par le compresseur
def rdc_cmds(data):
    seen = set(); i = 0
    while i < len(data):
        c = (data[i] << 8) | data[i+1]; i += 2
        for j in range(16):
            if i >= len(data): break
            if not (c >> (15-j)) & 1: i += 1
            else:
                u = data[i]; cmd = u >> 4; seen.add(cmd)
                i += 2 if cmd in (0, 3,4,5,6,7,8,9,10,11,12,13,14,15) else 3
                if cmd == 0: i -= 0
    return seen
allc = set()
for nm_, b in syn:
    allc |= rdc_cmds(rdc_compress(b))
for k in sorted(res):
    ok, ko, ex = res[k]
    print(f"{k}: {ok} ok, {ko} echecs", ex if ko else "")
print("commandes RDC emises par rdc_compress sur les cas 4:", sorted(allc))
sys.exit(1 if any(v[1] for v in res.values()) else 0)
