#!/usr/bin/env python3
"""Ecrivain de reference .sas7bdat (64 bits, little endian, imitant SAS 9.4M7 sous Linux), bibliotheque standard seulement.

Ecrit a partir de rea_output/10_format_sas7bdat.md, 15_compression.md et 30_formats_encodages.md ; la procedure est decrite dans
rea_output/20_ecriture.md. Chaque champ « recopie » (valeur observee faute de regle connue) est liste dans RECOPIES avec le fichier du
corpus et l'offset d'origine ; la classification (calcule / constante / libre) est dans 20_ecriture.md.

Usage (module) :
    cols = [Col("x", "n", 8), Col("s", "c", 5, label="texte")]
    write("sortie.sas7bdat", cols, [[1.5, "abc"], ["A", ""]])      # un manquant special s'ecrit "." "_" "A".."Z"
Limites : format 64 bits little endian seulement ; ni lignes supprimees, ni index, ni chiffrement ; metadonnees sur la page 0
(moins de 800 colonnes environ).
"""
import os
import random
import struct
import time

MAGIC = bytes(12) + bytes.fromhex("c2ea8160b31411cfbd92080009c7318c181f1011")
TAIL = 296  # 288 + t (t = 8)
MAX_TEXT_BLOCK = 32740
MIN_COMPRESSED_ROW = 16  # en dessous, la table est ecrite sans compression (section 5 de 20_ecriture.md)

# champs recopies : (nom, valeur, fichier d'origine, offset absolu d'origine). Valeurs observees identiques dans tous les fichiers 64 bits
# little endian de SAS 9.4M7 Linux du corpus ; classification (calcule / constante / libre) : 20_ecriture.md section 5.
_NU = "corpus/files/base/base_n100_mix_no.sas7bdat"  # RowSize en 130264, SubheaderCounts en 129640, ColumnText en 129572
_CP = "corpus/files/compression/compression_pat2_char.sas7bdat"  # table compressee (memes positions de RowSize et de Counts)
RECOPIES = [
    ("header.const_33_34", "22 00", _NU, 33), ("header.flag_36", "33", _NU, 36), ("header.const_38", "02", _NU, 38), ("header.const_39", "31", _NU, 39),
    ("header.platform_code", "01", _NU, 40), ("header.session_code_47_71", "14", _NU, 47), ("header.desc_50_51_74_75", "03 01", _NU, 50),
    ("header.desc_52_55", "18 1F 10 11", _NU, 52), ("header.byte_64", "01", _NU, 64), ("header.desc_65_68", "33 01 23 33", _NU, 65),
    ("header.byte_73", "20", _NU, 73), ("header.release_host_os", "9.0401M7 / Linux / 6.18.48-107.148. / x86_64", _NU, 0xE0),
    ("rowsize.marker", "0xF0 (0x131 si compresse)", _NU, 130264 + 8), ("rowsize.row_flags", "0x223011 (0x22303A si compresse)", _NU, 130264 + 32),
    ("rowsize.all_ones", "FF*16", _NU, 130264 + 128), ("rowsize.tail_refs", "references de texte constantes", _NU, 130264 + 0x2A0),
    ("rowsize.counters_2e8", "04 00 01 00 01 00 01 00", _NU, 130264 + 0x2E8), ("rowsize.tail_318", "00 00 00 01 00 00 00 00 / 00 01", _NU, 130264 + 0x318),
    ("rowsize.compressed_40_24a", "2 en +0x40 et 1 en +0x24A (compresse seulement)", _CP, 130264 + 0x40),
    ("subheader_counts.header_words", "m(3) = 7, 0x070C en +0x70", _NU, 129640 + 24), ("subheader_counts.signatures", "FC FD FF FE FB FA F9 (FFFFFFxx etendus a 64 bits)", _NU, 129640 + 120),
    ("column_text.prefix", "00 00 00 enc, 16 blancs, DATASTEP", _NU, 129572 + 16),
]


class Col:
    def __init__(self, name, type_, length, label="", fmt=None, informat=None):
        """fmt / informat : (nom, largeur, decimales), par exemple ("DATE", 9, 0)"""
        self.name, self.type, self.length, self.label, self.fmt, self.informat = name, type_, length, label, fmt, informat
        self.offset = 0


def _sas_now():
    return time.time() + 315619200.0  # secondes depuis 1960-01-01 (3653 jours)


def _tag_double(v):
    """valeur numerique -> 8 octets little endian ; manquants speciaux : ".", "_", "A".."Z"""
    if isinstance(v, str):
        code = 0xFE if v == "." else 0xFF if v == "_" else 0xFD - (ord(v) - ord("A"))
        return bytes([0, 0, 0, 0, 0, code, 0xFF, 0xFF])
    return struct.pack("<d", float(v))


def _pad4(n):
    return (n + 3) // 4 * 4


class _Texts:
    """blocs de texte (ColumnText) : chaque texte est range sur un multiple de 4 octets, reference (bloc, offset, longueur)"""

    def __init__(self, enc_code, codec, literal=None):
        self.codec = codec
        first = bytearray(36)
        first[8:12] = bytes([0, 0, 0, enc_code])
        first[12:28] = b" " * 16
        first[28:36] = b"DATASTEP"
        if literal:  # table compressee : le litteral (8 octets) s'insere en 12..19, le reste decale de 8 (15_compression.md section 2)
            first[12:12] = literal
        self.blocks = [first]

    def add(self, text):
        raw = text.encode(self.codec)
        if not raw:
            return (0, 0, 0)
        if len(self.blocks[-1]) + _pad4(len(raw)) > MAX_TEXT_BLOCK:
            self.blocks.append(bytearray(8))
        blk = self.blocks[-1]
        ref = (len(self.blocks) - 1, len(blk), len(raw))
        blk += raw + bytes(_pad4(len(raw)) - len(raw))
        return ref


def _subheader(sig8, body):
    return sig8 + body


SIG = {
    "row": bytes.fromhex("f7f7f7f700000000"), "col": bytes.fromhex("f6f6f6f600000000"), "counts": bytes.fromhex("00fcffffffffffff"),
    "text": bytes.fromhex("fdffffffffffffff"), "name": bytes.fromhex("ffffffffffffffff"), "attr": bytes.fromhex("fcffffffffffffff"),
    "fl": bytes.fromhex("fefbffffffffffff"),
}
SIG4 = {bytes.fromhex(h) for h in ("f7f7f7f7", "f6f6f6f6", "00fcffff", "fdffffff", "ffffffff", "fcffffff", "feffffff", "fefbffff", "fbffffff")}

# RowSize : zone de references constante observee (octets 0x2A0 a 0x2C7 et 0x2E8 a 0x2F7 dans base_n100_mix_no.sas7bdat)
ROWSIZE_TAIL_WORDS = {  # offset dans RowSize -> octets (recopies)
    0x2A0: bytes.fromhex("0000080004000000"), 0x2A8: bytes.fromhex("0000000000001400"), 0x2B0: bytes.fromhex("0800000000000000"),
    0x2B8: bytes.fromhex("00000c0008000000"), 0x2C0: bytes.fromhex("1c00080000000000"), 0x2E8: bytes.fromhex("0400010001000100"),
    0x318: bytes.fromhex("0000000100000000"), 0x31A: bytes.fromhex("0001"),
}
# RowSize d'une table compressee : zone de references (le litteral occupe le texte 12..19 : reference (0, 12, 8)) ; recopie de
# corpus/files/compression/compression_pat2_char.sas7bdat (page 0, RowSize)
COMPRESSED_TAIL_WORDS = {
    0x2A0: bytes.fromhex("0000080004000000"), 0x2A8: bytes.fromhex("0000000000001c00"), 0x2B0: bytes.fromhex("080000000c000800"),
    0x2B8: bytes.fromhex("0000140008000000"), 0x2C0: bytes.fromhex("2400080000000000"), 0x2E8: bytes.fromhex("0400010001000100"),
    0x318: bytes.fromhex("0000000100000000"), 0x31A: bytes.fromhex("0001"),
}


def _layout(cols):
    num = sorted([c for c in cols if c.type == "n"], key=lambda c: -c.length)
    chars = [c for c in cols if c.type == "c"]
    off = 0
    for c in num + chars:
        c.offset = off
        off += c.length
    return off + (-off) % 8 if num else off


def write(path, cols, rows, compress=None, page_length=65536, enc_code=20, codec="utf-8", seed=None):
    rnd = random.Random(seed)
    n = len(cols)
    if n > 4000:
        raise ValueError("plus de 4000 colonnes : ColumnName et ColumnAttributes tiendraient en plusieurs sous-en-tetes (longueur u16), non ecrits")
    row_len = _layout(cols)
    if compress and sum(c.length for c in cols) < MIN_COMPRESSED_ROW:
        compress = None  # ligne trop courte : ni brute (prise pour un sous-en-tete) ni compressee (plus longue que la ligne) ; SAS ecrit alors une table ordinaire
    if compress:
        row_len = sum(c.length for c in cols)
    enc_texts = _Texts(enc_code, codec, (b"SASYZCRL" if compress == "CHAR" else b"SASYZCR2") if compress else None)
    refs = []
    for c in cols:
        refs.append((enc_texts.add(c.name), enc_texts.add(c.fmt[0]) if c.fmt else (0, 0, 0),
                     enc_texts.add(c.informat[0]) if c.informat else (0, 0, 0), enc_texts.add(c.label) if c.label else (0, 0, 0)))
    # --- sous-en-tetes de metadonnees
    subs = []  # (type de pointeur, octets)
    ptr_type = 1 if compress else 0
    row_marker, row_flags = (0x131, 0x22303A) if compress else (0xF0, 0x223011)
    rowsize = bytearray(808)
    rowsize[0:8] = SIG["row"]
    for off, val in ((8, row_marker), (16, n + 9), (32, row_flags), (40, row_len), (48, len(rows)), (72, n), (96, n), (104, page_length),
                     (128, (1 << 64) - 1), (136, (1 << 64) - 1), (776, len(rows))):
        rowsize[off:off + 8] = struct.pack("<Q", val)
    rowsize[0x2EE:0x2F0] = struct.pack("<H", max(len(c.name.encode(codec)) for c in cols) if cols else 1)
    for off, val in (COMPRESSED_TAIL_WORDS if compress else ROWSIZE_TAIL_WORDS).items():
        rowsize[off:off + len(val)] = val
    if compress:
        rowsize[0x40:0x48] = struct.pack("<Q", 2)
        rowsize[0x24A] = 1
    subs.append((ptr_type, rowsize))
    colsize = bytearray(24)
    colsize[0:8] = SIG["col"]
    colsize[8:16] = struct.pack("<Q", n)
    subs.append((ptr_type, colsize))
    counts = bytearray(600)
    counts[0:8] = SIG["counts"]
    counts[8:16] = struct.pack("<Q", len(enc_texts.blocks[0]))
    counts[16:24] = struct.pack("<Q", 3)  # sous-en-tetes FC, FD, FF presents (ColumnList non ecrit) : 10 section 4.4
    counts[24:32] = struct.pack("<Q", 7)
    counts[112:120] = struct.pack("<Q", 0x070C)
    for k, sg in enumerate((0xFFFFFFFC, 0xFFFFFFFD, 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFB, 0xFFFFFFFA, 0xFFFFFFF9)):
        counts[120 + 40 * k:128 + 40 * k] = struct.pack("<q", -(1 << 32) + sg) if sg >= 0x80000000 else struct.pack("<Q", sg)
    subs.append((ptr_type, counts))
    text_idx = []
    for blk in enc_texts.blocks:
        body = bytearray(blk)
        body[0:2] = struct.pack("<H", len(blk))
        sh = bytearray(SIG["text"]) + body + bytes(12)
        subs.append((1, sh))
        text_idx.append(len(subs) - 1)
    # noms (entrees de 8 octets), un sous-en-tete
    entries = bytearray()
    for (nm, _, _, _) in refs:
        entries += struct.pack("<HHHH", nm[0], nm[1], nm[2], 0)
    sh = bytearray(SIG["name"]) + struct.pack("<H", 8 + len(entries)) + bytes(6) + entries + bytes(12)
    subs.append((1, sh))
    name_idx = len(subs) - 1
    ent = bytearray()
    for c in cols:
        flags = 0x0400 if len(c.name.encode(codec)) <= 8 else 0x0800
        ent += struct.pack("<QIHBB", c.offset, c.length, flags, 1 if c.type == "n" else 2, 0)
    sh = bytearray(SIG["attr"]) + struct.pack("<H", 8 + len(ent)) + bytes(6) + ent + bytes(12)
    subs.append((1, sh))
    attr_idx = len(subs) - 1
    first_fl = len(subs)
    for c, (_, fr, ir, lr) in zip(cols, refs):
        fl = bytearray(64)
        fl[0:8] = SIG["fl"]
        fw, fd = (c.fmt[1], c.fmt[2]) if c.fmt else (0, 0)
        iw, idd = (c.informat[1], c.informat[2]) if c.informat else (0, 0)
        fl[0x18:0x20] = struct.pack("<HHHH", fw, fd, iw, idd)
        fl[0x28:0x2E] = struct.pack("<HHH", *ir)
        fl[0x2E:0x34] = struct.pack("<HHH", *fr)
        fl[0x34:0x3A] = struct.pack("<HHH", *lr)
        subs.append((ptr_type, fl))
    last_fl = len(subs) - 1
    # compteurs : (page, position 1-based) de ColumnAttributes, ColumnText, ColumnName
    for k, idx in ((0, attr_idx), (1, text_idx[0]), (2, name_idx)):
        base = 120 + 40 * k + 8
        counts[base:base + 32] = struct.pack("<QQQQ", 1, idx + 1, 1, idx + 1) if True else b""
    po, ps = 32, 24
    sc = len(subs) + 1  # + pointeur terminal
    rows_b = [_encode_row(cols, r, row_len, codec) for r in rows]
    file_code = rnd.getrandbits(32)
    pages = []
    if compress:
        pages = _compressed_pages(subs, rows_b, compress, page_length, file_code, row_len, po, ps, first_fl, last_fl)
    else:
        total_sub = sum(len(s[1]) for s in subs)
        start = (po + 8 + sc * ps + 7) // 8 * 8
        minoff = page_length - total_sub
        avail = minoff - start
        if avail < 0:
            raise ValueError("metadonnees (%d octets de sous-en-tetes, %d pointeurs) trop grandes pour la page 0 de %d octets : plusieurs pages de metadonnees non ecrites" % (total_sub, sc, page_length))
        cap = max(c for c in range(0, avail // max(row_len, 1) + 2) if c * row_len + (c + 7) // 8 <= avail) if row_len else 0
        # lignes de la page 0 : min(lignes, capacite)
        n0 = min(len(rows_b), cap)
        # compteurs de RowSize qui dependent de la page
        rowsize[120:128] = struct.pack("<Q", cap)
        rowsize[0x2FE:0x300] = struct.pack("<H", min((cap + sc) if len(rows_b) <= cap else 0, 0xFFFF))
        rmax = max(r for r in range(0, (page_length - 40) // max(row_len, 1) + 2) if r * row_len + (r + 7) // 8 + 40 <= page_length)
        rest_rows = len(rows_b) - n0
        npages = 1 + (rest_rows + rmax - 1) // rmax if rest_rows else 1
        last_blocks = sc + n0 if npages == 1 else (rest_rows - (npages - 2) * rmax)
        locs = ((1, 2), (1, last_fl + 1), (1, sc + 1), (npages, last_blocks), (1, first_fl + 1))
        for k, (pgno, v) in enumerate(locs):
            rowsize[512 + 16 * k:520 + 16 * k] = struct.pack("<Q", pgno)
            rowsize[520 + 16 * k:528 + 16 * k] = struct.pack("<Q", v)
        if len(rows_b) > cap:
            rowsize[0x2FE:0x300] = struct.pack("<H", min(rmax, 0xFFFF))
        rowsize[0x1B8:0x1BC] = struct.pack("<I", file_code ^ 1)
        pg = bytearray(page_length)
        pg[0:4] = struct.pack("<I", file_code ^ 1)
        pg[24:32] = struct.pack("<Q", minoff - (start + n0 * row_len) - (cap + 7) // 8)
        pg[32:38] = struct.pack("<HHH", 0x0200, sc + n0, sc)
        off = page_length
        ptrs = bytearray()
        for ptype, data in subs:
            off -= len(data)
            pg[off:off + len(data)] = data
            ptrs += struct.pack("<QQBB", off, len(data), 0, ptype) + bytes(6)
        ptrs += struct.pack("<QQBB", off, 0, 1, 0) + bytes(6)
        pg[40:40 + len(ptrs)] = ptrs
        for i in range(n0):
            pg[start + i * row_len: start + (i + 1) * row_len] = rows_b[i]
        pages.append(pg)
        rest = rows_b[n0:]
        k = 1
        while rest:
            chunk, rest = rest[:rmax], rest[rmax:]
            pg = bytearray(page_length)
            pg[0:4] = struct.pack("<I", file_code ^ (k + 1))
            pg[24:32] = struct.pack("<Q", page_length - 40 - len(chunk) * row_len - (rmax + 7) // 8)
            pg[32:38] = struct.pack("<HHH", 0x0100, len(chunk), 0)
            for i, r in enumerate(chunk):
                pg[40 + i * row_len: 40 + (i + 1) * row_len] = r
            pages.append(pg)
            k += 1
        # RowSize a ete modifie apres sa copie dans la page : reecrire
        o = page_length - len(rowsize)
        pages[0][o:o + len(rowsize)] = rowsize
    # --- en-tete
    hdr = bytearray(page_length)
    hdr[0:32] = MAGIC
    hdr[32:40] = bytes([0x33, 0x22, 0x00, 0x33, 0x33, 0x01, 0x02, 0x31])
    hdr[40] = 0x01
    hdr[47] = 0x14
    hdr[50:56] = bytes([0x03, 0x01, 0x18, 0x1F, 0x10, 0x11])
    hdr[56:64] = bytes(hdr[32:40])
    hdr[64] = 0x01
    hdr[65:69] = bytes([0x33, 0x01, 0x23, 0x33])
    hdr[70] = enc_code
    hdr[71] = 0x14
    hdr[73] = 0x20
    hdr[74:76] = bytes([0x03, 0x01])
    hdr[84:92] = b"SAS FILE"
    hdr[92:124] = b" " * 32
    hdr[156:164] = b"DATA    "
    now = _sas_now()
    hdr[168:176] = struct.pack("<d", now)
    hdr[176:184] = struct.pack("<d", now)
    hdr[200:204] = struct.pack("<I", page_length)
    hdr[204:208] = struct.pack("<I", page_length)
    hdr[208:216] = struct.pack("<Q", len(pages))
    hdr[224:232] = b"9.0401M7"
    hdr[232:237] = b"Linux"
    hdr[248:264] = b"6.18.48-107.148."
    hdr[280:286] = b"x86_64"
    low = hdr[168:172]
    hdr[TAIL:TAIL + 4] = low
    xor = bytes(a ^ b for a, b in zip(low, b"LNoe"))
    for k in range(3):
        hdr[TAIL + 4 + 4 * k: TAIL + 8 + 4 * k] = xor
    hdr[328:332] = struct.pack("<I", file_code)
    hdr[336:344] = struct.pack("<d", now)
    with open(path, "wb") as f:
        f.write(hdr)
        for p in pages:
            f.write(p)


def _encode_row(cols, values, row_len, codec):
    out = bytearray(row_len)
    for c, v in zip(cols, values):
        if c.type == "n":
            raw = _tag_double(v)
            out[c.offset:c.offset + c.length] = raw[8 - c.length:]
        else:
            b = (v if isinstance(v, bytes) else str(v).encode(codec))[: c.length]
            out[c.offset:c.offset + c.length] = b + b" " * (c.length - len(b))
    return bytes(out)


def _row_stream(raw, algo):
    """(octet de compression, octets stockes) : flot compresse s'il est strictement plus court que la ligne, sinon ligne brute"""
    import ref_compress
    comp = ref_compress.rle_compress(raw) if algo == "CHAR" else ref_compress.rdc_compress(raw)
    # une ligne brute de moins de 16 octets, ou dont le debut ressemble a une signature de sous-en-tete, serait prise pour un sous-en-tete
    # par les lecteurs (ReadStat, ref_reader) : dans ces cas le flot compresse, meme plus long que la ligne, est la seule forme sure
    ambiguous = len(raw) < 16 or bytes(raw[:4]) in SIG4
    return (0, bytes(raw)) if len(comp) >= len(raw) and not ambiguous else (4, comp)


def _compressed_pages(subs, rows_b, algo, page_length, file_code, row_len, po, ps, first_fl, last_fl):
    """pages d'une table compressee (15_compression.md, sections 2 a 6) : page 0 = metadonnees puis autant de lignes qu'il en tient,
    pages suivantes = lignes seulement ; une page marqueur 0x9000 suit la premiere page contenant des lignes"""
    rowsize = subs[0][1]
    total = len(rows_b)
    meta_total = sum(len(d) for _, d in subs)
    if meta_total + po + 8 + (len(subs) + 1) * ps > page_length:
        raise ValueError("metadonnees trop grandes pour la page 0 de %d octets : plusieurs pages de metadonnees non ecrites" % page_length)
    streams = [_row_stream(r, algo) for r in rows_b]
    pages = [{"ptrs": [], "rows": 0, "data": [], "used": meta_total if k == 0 else 0, "meta": k == 0} for k in range(1)]

    def free_after(pg, add_len):
        nptr = (len(subs) if pg["meta"] else 0) + len(pg["ptrs"]) + 1 + 1  # + ligne ajoutee + pointeur terminal
        return page_length - pg["used"] - add_len - (po + 8 + nptr * ps)

    for comp, data in streams:
        if free_after(pages[-1], len(data)) < 0:
            if not pages[-1]["ptrs"] and not pages[-1]["meta"]:
                raise ValueError("ligne trop longue pour une page")
            pages.append({"ptrs": [], "rows": 0, "data": [], "used": 0, "meta": False})
            if free_after(pages[-1], len(data)) < 0:
                raise ValueError("ligne compressee de %d octets trop longue pour une page de %d octets" % (len(data), page_length))
        pg = pages[-1]
        pg["ptrs"].append((comp, len(data)))
        pg["data"].append(data)
        pg["used"] += len(data)
        pg["rows"] += 1
    first = next((i for i, pg in enumerate(pages) if pg["rows"]), 0)  # premiere page contenant des lignes (page 0 si aucune)
    order = list(range(len(pages)))
    order.insert(first + 1, "marker")
    last = max((i for i, k in enumerate(order) if k != "marker" and pages[k]["rows"]), default=0)
    # --- champs de RowSize qui dependent de la disposition
    n_sub = len(subs)
    rowsize[16:24] = struct.pack("<Q", total + n_sub + 2)
    rowsize[0x1B8:0x1BC] = struct.pack("<I", file_code ^ 1)
    sc_last = (n_sub if pages[order[last]]["meta"] else 0) + len(pages[order[last]]["ptrs"]) + 1
    locs = ((1, 2), (1, last_fl + 1), (1, n_sub + 1), (last + 1, sc_last - 1), (1, first_fl + 1))
    for k, (pgno, v) in enumerate(locs):
        rowsize[512 + 16 * k:520 + 16 * k] = struct.pack("<Q", pgno)
        rowsize[520 + 16 * k:528 + 16 * k] = struct.pack("<Q", v)
    start0 = (po + 8 + (n_sub + 1) * ps + 7) // 8 * 8
    avail = page_length - meta_total - start0
    cap = max(c for c in range(0, avail // max(row_len, 1) + 2) if c * row_len + (c + 7) // 8 <= avail) if row_len else 0
    rowsize[120:128] = struct.pack("<Q", cap)
    # --- octets des pages
    out = []
    for idx, k in enumerate(order):
        pg = bytearray(page_length)
        pg[0:4] = struct.pack("<I", file_code ^ (idx + 1))
        if k == "marker":
            # page marqueur (15_compression.md, page_comp_0x9000) : un enregistrement de 18 octets par page contenant des lignes, dans
            # l'ordre decroissant des pages : lignes cumulees jusqu'a cette page (u64 BIG endian), numero de page 1-base (u64),
            # dernier indice de sous-en-tete de la page (u16) ; la zone est [A - 18*n, A) avec A = min(longueur de page, 32767)
            data_pages = [(i, k2) for i, k2 in enumerate(order) if k2 != "marker" and pages[k2]["rows"]]
            n_tr = len(data_pages)
            A = min(page_length, 32767)
            pg[24:32] = struct.pack("<Q", 1)
            pg[32:40] = struct.pack("<HHHH", 0x9000, n_tr + 1, n_tr, A - 48 - 18 * n_tr)
            start = A - 18 * n_tr
            cum = 0
            tri = []
            for i, k2 in data_pages:
                cum += pages[k2]["rows"]
                nb = (n_sub if pages[k2]["meta"] else 0) + len(pages[k2]["ptrs"]) + 1
                tri.append((cum, i + 1, nb))
            for j, (cum_rows, pno, nb) in enumerate(reversed(tri)):
                o = start + 18 * j
                pg[o:o + 18] = struct.pack(">Q", cum_rows) + struct.pack("<QH", pno, nb - 1)
            out.append(pg)
            continue
        page = pages[k]
        ptrs = []
        off_end = page_length
        if page["meta"]:
            for ptype, data in subs:
                off_end -= len(data)
                pg[off_end:off_end + len(data)] = data
                ptrs.append((off_end, len(data), 0, ptype))
        for (comp, ln), data in zip(page["ptrs"], page["data"]):
            off_end -= ln
            pg[off_end:off_end + ln] = data
            ptrs.append((off_end, ln, comp, 1))
        end = po + len(ptrs) * ps + ps
        ptrs.append((end, off_end - end, 1, 1))
        for i, (o, ln, comp, ty) in enumerate(ptrs):
            pg[po + 8 + i * ps: po + 8 + (i + 1) * ps] = struct.pack("<QQBB", o, ln, comp, ty) + bytes(6)
        pg[24:32] = struct.pack("<Q", off_end - end)
        pg[32:38] = struct.pack("<HHH", 0x0000, len(ptrs), len(ptrs))
        out.append(pg)
    return out
