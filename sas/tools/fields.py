#!/usr/bin/env python3
"""Tables de champs de l'en-tete et des sous-en-tetes .sas7bdat, et controle de couverture octet par octet.

Les offsets sont ceux de rea_output/10_format_sas7bdat.md. Ce module sert a :
  * annoter un hexdump par champ                (annotate_header)
  * verifier qu'aucun octet non nul n'echappe aux tables  (python3 -I fields.py coverage <fichiers...>)

Notation : t = a1 + a2 (a1 = 4 si l'octet 35 vaut 0x33, a2 = 4 si l'octet 32 vaut 0x33) ; w = 8 (fichier u64) ou 4.
Un champ est (nom, offset, taille) ; l'offset peut dependre de a1, t, w via une lambda.
"""
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inspect_sas7bdat as I  # noqa: E402


def header_fields(a1, a2):
    t = a1 + a2
    return [
        ("magic", 0, 32), ("u64_flag", 32, 1), ("const_33_34", 33, 2), ("a1_flag", 35, 1), ("flag_36", 36, 1),
        ("endian", 37, 1), ("const_38", 38, 1), ("platform_char", 39, 1), ("platform_code", 40, 1),
        ("session_code_47", 47, 1), ("desc_50_51", 50, 2), ("magic_tail_copy", 52, 4),
        ("descriptor_copy_56_64", 56, 9), ("desc_65_68", 65, 4), ("encoding", 70, 1), ("session_code_71", 71, 1),
        ("byte_73", 73, 1), ("desc_74_75", 74, 2), ("file_label_sas_file", 84, 8), ("table_name", 92, 64),
        ("file_type", 156, 8), ("created", 164 + a1, 8), ("modified", 172 + a1, 8),
        ("tz_offset_created", 180 + a1, 8), ("tz_offset_modified", 188 + a1, 8),
        ("header_length", 196 + a1, 4), ("page_length", 200 + a1, 4), ("page_count", 204 + a1, 4 + a2),
        ("after_page_count", 208 + a1 + a2, 4),
        ("sas_release", 216 + t, 8), ("host", 224 + t, 16), ("os_version", 240 + t, 16), ("os_name", 256 + t, 16),
        ("os_machine", 272 + t, 16), ("created_low_copy", 288 + t, 4), ("created_low_xor_1", 292 + t, 4),
        ("created_low_xor_2", 296 + t, 4), ("created_low_xor_3", 300 + t, 4), ("file_code", 320 + t, 4),
        ("created_copy", 328 + t, 8),
    ]


PAGE_HEADER = lambda w: [  # (nom, offset, taille) ; w = 8 (u64) ou 4
    ("page_signature", 0, 4), ("reserved_4_7", 4, 4), ("free_bytes", 24 if w == 8 else 12, w),
    ("page_type", 32 if w == 8 else 16, 2), ("block_count", 34 if w == 8 else 18, 2),
    ("subheader_count", 36 if w == 8 else 20, 2), ("reserved_after_count", 38 if w == 8 else 22, 2),
]


def subheader_fields(kind, w, length):
    """Champs decodes de chaque sous-en-tete (offsets en octets, w = 8 ou 4). Tout octet hors de ces champs est inconnu."""
    sig = ("signature", 0, w)
    if kind == "RowSize":
        loc0 = 512 if w == 8 else 264
        return [sig, ("marker", w, w), ("field_2", 2 * w, w), ("flags", 4 * w, w), ("row_length", 5 * w, w),
                ("row_count", 6 * w, w), ("deleted_count", 7 * w, w), ("col_count_p1", 9 * w, w), ("col_count_p2", 10 * w, w),
                ("field_11", 11 * w, w), ("field_12", 12 * w, w), ("page_length_copy", 13 * w, w),
                ("mix_capacity", 15 * w, w), ("ff_fill", 16 * w, 2 * w), ("page_signature_copy", 55 * w, 4),
                ("locators", loc0, 10 * w)]
    if kind == "ColumnSize":
        return [sig, ("column_count", w, w)]
    if kind == "SubheaderCounts":
        out = [sig, ("text_size_plus_8", w, w), ("field_2", 2 * w, w), ("entry_count", 3 * w, w), ("const_1804", 14 * w, w)]
        for k in range(7):
            out.append((f"entry_{k}", (15 + 5 * k) * w, 5 * w))
        return out
    if kind == "ColumnText":
        return [sig, ("text_size", w, 2), ("text", w + 2, max(0, length - w - 2))]
    if kind == "ColumnName":
        return [sig, ("size", w, 2), ("pointers", w + 2 + 2 + 8 if False else w + 8, max(0, length - w - 8))]
    if kind == "ColumnAttributes":
        return [sig, ("size", w, 2), ("entries", w + 8, max(0, length - w - 8))]
    if kind == "ColumnList":
        return [sig]
    if kind == "FormatAndLabel":
        if w == 8:
            return [sig, ("format_width", 0x18, 2), ("format_decimals", 0x1A, 2), ("informat_width", 0x1C, 2),
                    ("informat_decimals", 0x1E, 2), ("informat_ref", 0x28, 6), ("format_ref", 0x2E, 6), ("label_ref", 0x34, 6)]
        return [sig, ("format_width", 0x0C, 2), ("format_decimals", 0x0E, 2), ("informat_width", 0x10, 2),
                ("informat_decimals", 0x12, 2), ("informat_ref", 0x1C, 6), ("format_ref", 0x22, 6), ("label_ref", 0x28, 6)]
    return [sig]


def header_params(b):
    a1 = 4 if b[35] == 0x33 else 0
    a2 = 4 if b[32] == 0x33 else 0
    return a1, a2


def uncovered(b):
    """Octets non nuls de l'en-tete qui n'appartiennent a aucun champ de header_fields."""
    a1, a2 = header_params(b)
    hl = struct.unpack_from("<I" if b[37] == 1 else ">I", b, 196 + a1)[0]
    cov = bytearray(hl)
    for _, o, n in header_fields(a1, a2):
        for i in range(o, min(o + n, hl)):
            cov[i] = 1
    return [i for i in range(hl) if b[i] and not cov[i]]


def uncovered_pages(b):
    """Octets non nuls des en-tetes de page et des pointeurs qui n'appartiennent a aucun champ decrit
    (en-tete de page : PAGE_HEADER ; pointeur : offset, longueur, compression, type)."""
    h = I.parse_header(b)
    w = 8 if h.u64 else 4
    po = 32 if h.u64 else 16
    ps = 24 if h.u64 else 12
    out = []
    for k, (off, pt, bc, sc) in enumerate(I.parse_pages(b, h)):
        cov = bytearray(po + 8 + sc * ps)
        for _, o, n in PAGE_HEADER(w):
            for i in range(o, o + n):
                cov[i] = 1
        for i in range(sc):
            q = po + 8 + i * ps
            for j in range(2 * w + 2):
                cov[q + j] = 1
        for i in range(len(cov)):
            if b[off + i] and not cov[i]:
                out.append((k, hex(i)))
    return out


def annotate_header(b):
    a1, a2 = header_params(b)
    lines = []
    for name, o, n in header_fields(a1, a2):
        v = b[o:o + n]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in v)
        lines.append(f"{o:#06x} +{n:<3} {name:<22} {v.hex() if n <= 16 else v[:16].hex() + '...'}  {txt[:32]!r}")
    return "\n".join(lines)


def unknowns(patterns):
    """Pour chaque type de sous-en-tete, liste les zones d'octets hors champs decodes, avec valeurs observees (markdown)."""
    import collections
    acc = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    nfiles = collections.Counter()
    for pat in patterns:
        for p in sorted(glob.glob(pat, recursive=True)):
            if not p.endswith(".sas7bdat"):
                continue
            b = open(p, "rb").read()
            if b"SASYZCRL" in b or b"SASYZCR2" in b:
                continue  # fichier compresse : hors perimetre (lignes stockees comme sous-en-tetes)
            try:
                h = I.parse_header(b)
            except Exception:
                continue
            w = 8 if h.u64 else 4
            variant = f"{'u64' if h.u64 else 'u32'}-{'LE' if h.le else 'BE'}"
            for k, (off, pt, bc, sc) in enumerate(I.parse_pages(b, h)):
                if pt & 0xFF00 not in (0x000, 0x200, 0x400) and pt != 0x4000:
                    continue
                for o, l, c, t in I.pointers(b, h, off, sc):
                    if l == 0 or c != 0 or l < 2 * w:
                        continue
                    sg, raw = I.signature(b, h, off, o)
                    kind = I.SIGS.get(sg)
                    if kind is None:
                        kind = f"inconnu_{raw.hex()}"
                    d = b[off + o: off + o + l]
                    cov = bytearray(l)
                    for _, fo, fn in subheader_fields(kind, w, l):
                        for i in range(fo, min(fo + fn, l)):
                            cov[i] = 1
                    nfiles[(kind, variant)] += 1
                    i = 0
                    while i < l:
                        if cov[i]:
                            i += 1
                            continue
                        j = i
                        while j < l and not cov[j]:
                            j += 1
                        seg = d[i:j]
                        acc[(kind, variant)][(i, j - i)][seg.hex() if any(seg) else "00*"] += 1
                        i = j
    lines = ["| structure | variante | zone (offset, taille) | valeurs observees (nombre de sous-en-tetes) |", "|---|---|---|---|"]
    for key in sorted(acc):
        for (o, n), cn in sorted(acc[key].items()):
            vals = ", ".join(f"`{v[:48]}{'...' if len(v) > 48 else ''}` x{c}" for v, c in cn.most_common(3))
            lines.append(f"| {key[0]} | {key[1]} | {o:#x}, {n} | {vals} ({len(cn)} valeur(s) distincte(s)) |")
    print("\n".join(lines))
    return 0


def main(argv):
    if len(argv) >= 3 and argv[1] == "annotate":
        print(annotate_header(open(argv[2], "rb").read()))
        return 0
    if len(argv) >= 3 and argv[1] == "coverage":
        bad = 0
        n = 0
        for pat in argv[2:]:
            for p in sorted(glob.glob(pat, recursive=True)):
                if not p.endswith(".sas7bdat"):
                    continue
                n += 1
                data = open(p, "rb").read()
                u = uncovered(data)
                if u:
                    bad += 1
                    print(f"{os.path.basename(p)}: {len(u)} octet(s) non nuls hors champ (en-tete) : {[hex(x) for x in u[:12]]}")
                if b"SASYZCRL" in data or b"SASYZCR2" in data:
                    continue  # pages de fichiers compresses : hors perimetre
                up = uncovered_pages(data)
                if up:
                    bad += 1
                    print(f"{os.path.basename(p)}: octets non nuls hors champ (pages) : {up[:6]}")
        print(f"--- {n} fichiers, {bad} avec octets non couverts")
        return 1 if bad else 0
    if len(argv) >= 3 and argv[1] == "unknowns":
        return unknowns(argv[2:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
