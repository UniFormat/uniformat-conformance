#!/usr/bin/env python3
"""Lecture PARTIELLE d'un catalogue .sas7bcat de formats (outil d'analyse, pas un lecteur complet).

Usage : python3 -I rea_output/tools/catalog_dump.py fichier.sas7bcat
Affiche : en-tete (type de fichier, tailles, pages), repertoire de la page 0 (type, nom de chaque entree), puis les libelles
(chaines precedees de leur longueur) trouves dans les pages d'entrees. La structure des plages et des options n'est PAS decodee
(voir 30_formats_encodages.md, section 5, et 60_inconnues.md).
"""
import re
import struct
import sys


def main(path):
    b = open(path, "rb").read()
    u64 = b[32] == 0x33
    a1 = 4 if b[35] == 0x33 else 0
    e = "<" if b[37] == 1 else ">"
    hl, pl = struct.unpack_from(e + "II", b, 196 + a1)
    pc = struct.unpack_from(e + ("Q" if u64 else "I"), b, 204 + a1)[0]
    print(f"{path}: magic octet 15 = {b[15]:#04x} type = {bytes(b[156:164])!r} u64={u64} {'LE' if e == '<' else 'BE'} header={hl} page={pl} pages={pc}")
    po = 32 if u64 else 16
    for k in range(pc):
        pg = b[hl + k * pl: hl + (k + 1) * pl]
        t, bc, sc = struct.unpack_from(e + "HHH", pg, po)
        print(f"  page {k}: signature={pg[:4].hex()} +{po}: {t:#06x} {bc} {sc} ; octets non nuls = {sum(1 for x in pg if x)}")
    pg0 = b[hl: hl + pl]
    print("  repertoire (page 0) :")
    for m in re.finditer(rb"([A-Z ]{8})([A-Z ]{3,8})", pg0[pl - 0x100:]):
        print("    type/nom :", m.group(1).decode().strip(), "/", m.group(2).decode().strip())
    print("  libelles (long. u16 + texte) :")
    for k in range(pc):
        pg = b[hl + k * pl: hl + (k + 1) * pl]
        for m in re.finditer(rb"\x06\x00([\x01-\x40])\x00([ -~]{1,64})", pg):
            n = m.group(1)[0]
            if len(m.group(2)) >= n:
                print(f"    page {k} +{m.start():#06x} : {m.group(2)[:n].decode()!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
