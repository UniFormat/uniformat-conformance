#!/usr/bin/env python3
"""Inspecteur de structure d'un .sas7bdat (outil d'analyse, pas le lecteur de reference).

Usage : python3 -I rea_output/tools/inspect_sas7bdat.py fichier.sas7bdat [--pages] [--subheaders] [--hex N]

Affiche l'en-tete decode, la liste des pages (type, nombre de blocs, de sous-en-tetes) et, avec
--subheaders, chaque pointeur de sous-en-tete (offset, longueur, compression, type, signature).
Les offsets suivent les hypotheses de rea_output/00_etat_de_l_art.md puis les corrections de
rea_output/10_format_sas7bdat.md : ils sont verifies par comparaison de fichiers du corpus.
"""
import struct
import sys

MAGIC = bytes(12) + bytes.fromhex("c2ea8160b31411cfbd92080009c7318c" "181f1011")

SIGS = {  # signature (valeur entiere, vue en endianness du fichier, sur 4 octets) -> nom
    0xF7F7F7F7: "RowSize", 0xF6F6F6F6: "ColumnSize", 0xFFFFFC00: "SubheaderCounts",
    0xFFFFFFFD: "ColumnText", 0xFFFFFFFF: "ColumnName", 0xFFFFFFFC: "ColumnAttributes",
    0xFFFFFBFE: "FormatAndLabel", 0xFFFFFFFE: "ColumnList",
}


class Hdr:
    pass


def parse_header(b):
    h = Hdr()
    h.magic_ok = b[:32] == MAGIC
    h.u64 = b[32] == 0x33
    h.a1 = 4 if b[35] == 0x33 else 0
    h.a2 = 4 if h.u64 else 0
    h.le = b[37] == 1
    h.e = "<" if h.le else ">"
    h.platform = chr(b[39])
    h.encoding = b[70]
    h.file_type = bytes(b[84:92]).decode("latin1")
    h.name = bytes(b[92:156])
    h.type2 = bytes(b[156:164])
    a1 = h.a1
    h.created = struct.unpack_from(h.e + "d", b, 164 + a1)[0]
    h.modified = struct.unpack_from(h.e + "d", b, 172 + a1)[0]
    h.header_length = struct.unpack_from(h.e + "I", b, 196 + a1)[0]
    h.page_length = struct.unpack_from(h.e + "I", b, 200 + a1)[0]
    h.page_count = struct.unpack_from(h.e + ("Q" if h.u64 else "I"), b, 204 + a1)[0]
    t = a1 + h.a2
    h.release = bytes(b[216 + t:224 + t])
    h.host = bytes(b[224 + t:240 + t])
    h.os_ver = bytes(b[240 + t:256 + t])
    h.os_name = bytes(b[256 + t:272 + t])
    return h


def parse_pages(b, h):
    pages = []
    for k in range(h.page_count):
        off = h.header_length + k * h.page_length
        p = b[off:off + h.page_length]
        po = 32 if h.u64 else 16
        ptype, bcount, scount = struct.unpack_from(h.e + "HHH", p, po)
        pages.append((off, ptype, bcount, scount))
    return pages


def pointers(b, h, off, scount):
    """Pointeurs de sous-en-tetes d'une page : (offset, longueur, compression, type)."""
    po = 32 if h.u64 else 16
    start = off + po + 8
    n = 24 if h.u64 else 12
    res = []
    for i in range(scount):
        q = start + i * n
        if h.u64:
            o, l = struct.unpack_from(h.e + "QQ", b, q)
            c, t = b[q + 16], b[q + 17]
        else:
            o, l = struct.unpack_from(h.e + "II", b, q)
            c, t = b[q + 8], b[q + 9]
        res.append((o, l, c, t))
    return res


def signature(b, h, base, o):
    w = 8 if h.u64 else 4
    raw = b[base + o: base + o + w]
    if len(raw) < w:
        return None, raw
    v = struct.unpack(h.e + ("Q" if h.u64 else "I"), raw)[0]
    # en 64 bits, la signature utile est dans les 4 octets de poids faible si les autres sont 0 ou 0xFFFFFFFF
    low = v & 0xFFFFFFFF
    if h.u64 and not h.le and raw[:4] in (b"\xf7\xf7\xf7\xf7", b"\xf6\xf6\xf6\xf6"):
        return struct.unpack(">I", raw[:4])[0], raw  # big endian 64 bits : RowSize/ColumnSize = 4 octets puis FFFFFBFE
    if h.u64:
        if v >> 32 in (0, 0xFFFFFFFF):
            return low, raw
        return v, raw
    return low, raw


def main(argv):
    path = argv[1]
    b = open(path, "rb").read()
    h = parse_header(b)
    print(f"{path}: {len(b)} octets")
    print(f"  magic_ok={h.magic_ok} u64={h.u64} a1={h.a1} a2={h.a2} {'LE' if h.le else 'BE'} plateforme={h.platform!r} encodage={h.encoding}")
    strip = bytes([0, 32])
    print(f"  type={h.file_type!r}/{h.type2!r} nom={h.name.rstrip(strip)!r} release={h.release!r} "
          f"hote={h.host.rstrip(strip)!r} os={h.os_ver.rstrip(strip)!r}/{h.os_name.rstrip(strip)!r}")
    print(f"  taille_entete={h.header_length} taille_page={h.page_length} pages={h.page_count} (fichier = {h.header_length + h.page_length * h.page_count})")
    pages = parse_pages(b, h)
    for k, (off, pt, bc, sc) in enumerate(pages):
        print(f"  page {k}: offset={off} type={pt:#06x} blocs={bc} sous-en-tetes={sc}")
        if "--subheaders" in argv:
            for i, (o, l, c, t) in enumerate(pointers(b, h, off, sc)):
                sig, raw = signature(b, h, off, o) if l else (None, b"")
                name = SIGS.get(sig, "?") if sig is not None else "-"
                print(f"     [{i:2}] off={o:#06x} len={l:#06x} comp={c} type={t} sig={raw.hex()} {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
