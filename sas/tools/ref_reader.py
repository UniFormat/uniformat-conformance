#!/usr/bin/env python3
"""Lecteur de reference .sas7bdat (non compresse), bibliotheque standard seulement.

Ecrit a partir de rea_output/10_format_sas7bdat.md ; sans ReadStat, pandas ni Parso.
Usage : python3 -I rea_output/tools/ref_reader.py fichier.sas7bdat [--meta]
Sortie : CSV (nom des colonnes, puis une ligne par ligne non supprimee).
Les valeurs numeriques sont ecrites avec repr(float) ; les manquants avec leur code (. _ A-Z).
"""
import csv
import struct
import sys

MAGIC = bytes(12) + bytes.fromhex("c2ea8160b31411cf" "bd92080009c7318c" "181f1011")
SIG_ROW_SIZE, SIG_COL_SIZE, SIG_COL_TEXT = 0xF7F7F7F7, 0xF6F6F6F6, 0xFFFFFFFD
SIG_COL_NAME, SIG_COL_ATTR, SIG_FORMAT = 0xFFFFFFFF, 0xFFFFFFFC, 0xFFFFFBFE
KNOWN_SIGS = {0xF7F7F7F7, 0xF6F6F6F6, 0xFFFFFC00, 0xFFFFFFFD, 0xFFFFFFFF, 0xFFFFFFFC, 0xFFFFFBFE, 0xFFFFFFFE, 0xFFFFFFFA}
ENCODINGS = {20: "utf-8", 28: "ascii", 29: "latin-1", 30: "iso8859-2", 33: "iso8859-5", 34: "iso8859-6", 35: "iso8859-7",
             36: "iso8859-8", 37: "iso8859-9", 60: "cp1250", 61: "cp1251", 62: "cp1252", 63: "cp1253", 64: "cp1254",
             65: "cp1255", 66: "cp1256", 67: "cp1257", 68: "cp1258", 138: "shift_jis"}


# ---------------------------------------------------------------------------- decompresseurs
# Ecrits par un agent n'ayant lu que rea_output/15_compression.md (sections 3 et 4), recopies tels quels.
def rle_decompress(data: bytes, out_len: int) -> bytes:
    data = bytes(data)
    n_in = len(data)
    out = bytearray()
    i = 0

    def need(k):
        if i + k > n_in:
            raise ValueError("RLE: donnees manquantes")

    while i < n_in:
        c = data[i]
        i += 1
        hi, lo = c & 0xF0, c & 0x0F
        if c < 0x40:
            need(1)
            n = data[i] + 64 + 256 * (c & 0x3F)
            i += 1
            need(n)
            out += data[i:i + n]
            i += n
        elif hi == 0x40:
            need(2)
            n = 256 * lo + data[i] + 18
            b = data[i + 1]
            i += 2
            out += bytes([b]) * n
        elif hi == 0x50:
            need(1)
            n = 256 * lo + data[i] + 17
            i += 1
            out += b"@" * n
        elif hi == 0x60:
            need(1)
            n = 256 * lo + data[i] + 17
            i += 1
            out += b" " * n
        elif hi == 0x70:
            need(1)
            n = 256 * lo + data[i] + 17
            i += 1
            out += b"\x00" * n
        elif 0x80 <= hi <= 0xB0:
            n = lo + 1 + 16 * ((hi - 0x80) >> 4)
            need(n)
            out += data[i:i + n]
            i += n
        elif hi == 0xC0:
            need(1)
            n = lo + 3
            out += bytes([data[i]]) * n
            i += 1
        elif hi == 0xD0:
            out += b"@" * (lo + 2)
        elif hi == 0xE0:
            out += b" " * (lo + 2)
        else:  # 0xF0
            out += b"\x00" * (lo + 2)
        if len(out) > out_len:
            raise ValueError("RLE: sortie depasse out_len")
    if len(out) != out_len:
        raise ValueError("RLE: longueur de sortie %d != %d" % (len(out), out_len))
    return bytes(out)



def rdc_decompress(data: bytes, out_len: int) -> bytes:
    data = bytes(data)
    n_in = len(data)
    out = bytearray()
    i = 0
    while i < n_in:
        if i + 2 > n_in:
            raise ValueError("RDC: mot de controle tronque")
        ctrl = (data[i] << 8) | data[i + 1]
        i += 2
        for j in range(16):
            if i >= n_in:
                break
            if not (ctrl >> (15 - j)) & 1:
                out.append(data[i])
                i += 1
            else:
                u = data[i]
                i += 1
                cmd, cnt = u >> 4, u & 0x0F
                if cmd == 0:
                    if i + 1 > n_in:
                        raise ValueError("RDC: donnees manquantes")
                    out += bytes([data[i]]) * (cnt + 3)
                    i += 1
                elif cmd == 1:
                    if i + 2 > n_in:
                        raise ValueError("RDC: donnees manquantes")
                    n = cnt + 19 + 16 * data[i]
                    out += bytes([data[i + 1]]) * n
                    i += 2
                else:
                    if cmd == 2:
                        if i + 2 > n_in:
                            raise ValueError("RDC: donnees manquantes")
                        ofs = cnt + 3 + 16 * data[i]
                        length = data[i + 1] + 16
                        i += 2
                    else:
                        if i + 1 > n_in:
                            raise ValueError("RDC: donnees manquantes")
                        ofs = cnt + 3 + 16 * data[i]
                        length = cmd
                        i += 1
                    if ofs > len(out):
                        raise ValueError("RDC: decalage > octets produits")
                    for _ in range(length):
                        out.append(out[-ofs])
            if len(out) > out_len:
                raise ValueError("RDC: sortie depasse out_len")
    if len(out) != out_len:
        raise ValueError("RDC: longueur de sortie %d != %d" % (len(out), out_len))
    return bytes(out)


_MAXOFS = 4098
_MAXCAND = 128



class SasFormatError(Exception):
    pass


class Column:
    def __init__(self):
        self.name = self.label = self.format = self.informat = ""
        self.type = "n"
        self.offset = self.length = 0
        self.fmt_width = self.fmt_dec = self.inf_width = self.inf_dec = 0


class SasFile:
    def __init__(self, data, raw=False):
        self.b = data
        self.raw = raw  # True : les colonnes caracteres sont rendues en octets (sans blancs ni NUL de fin)
        self._header()
        self.columns = []
        self.rows = []
        self.deleted_count_header = 0
        self._walk_pages()

    # ------------------------------------------------------------------ en-tete
    def _header(self):
        b = self.b
        if len(b) < 0x200 or b[:32] != MAGIC:
            raise SasFormatError("magic number invalide")
        self.u64 = b[32] == 0x33
        self.a1 = 4 if b[35] == 0x33 else 0
        self.a2 = 4 if self.u64 else 0
        self.int_len = 8 if self.u64 else 4
        self.e = "<" if b[37] == 1 else ">"
        self.encoding_code = b[70]
        self.codec = ENCODINGS.get(self.encoding_code)
        a1 = self.a1
        self.header_length = self._u32(196 + a1)
        self.page_length = self._u32(200 + a1)
        self.page_count = struct.unpack_from(self.e + ("Q" if self.u64 else "I"), b, 204 + a1)[0]
        t = a1 + self.a2
        self.release = bytes(b[216 + t:224 + t]).rstrip(b"\0 ").decode("latin-1")
        if len(b) < self.header_length + self.page_length * self.page_count:
            raise SasFormatError("fichier tronque")

    def _u16(self, o):
        return struct.unpack_from(self.e + "H", self.b, o)[0]

    def _u32(self, o):
        return struct.unpack_from(self.e + "I", self.b, o)[0]

    def _int(self, o):
        return struct.unpack_from(self.e + ("Q" if self.u64 else "I"), self.b, o)[0]

    # ------------------------------------------------------------------ pages
    def _walk_pages(self):
        self._stored = []
        self.texts = []
        self.names = []
        self.attrs = []
        self.fmts = []
        self.row_length = self.row_count = self.row_marker = 0
        self.col_count = 0
        data_pages = []
        po = 32 if self.u64 else 16
        for k in range(self.page_count):
            base = self.header_length + k * self.page_length
            ptype, bcount, scount = struct.unpack_from(self.e + "HHH", self.b, base + po)
            data_pages.append((base, ptype, bcount, scount))
            if ptype & 0xFF00 in (0x000, 0x200, 0x400) or ptype == 0x4000:
                self._subheaders(base, scount)
        self._build_columns()
        blob = b"".join(self.texts)
        self.compression = "RLE" if b"SASYZCRL" in blob else "RDC" if b"SASYZCR2" in blob else None
        if self.compression:  # lignes stockees comme sous-en-tetes (15_compression.md)
            dec = rle_decompress if self.compression == "RLE" else rdc_decompress
            for comp, data in self._stored:
                raw = data if comp == 0 else dec(data, self.row_length)
                self.rows.append(self._decode(raw[: self.row_length]))
            return
        for base, ptype, bcount, scount in data_pages:
            self._rows(base, ptype, bcount, scount)

    def _subheaders(self, base, scount):
        po = 32 if self.u64 else 16
        ps = 24 if self.u64 else 12
        for i in range(scount):
            q = base + po + 8 + i * ps
            o, l = struct.unpack_from(self.e + ("QQ" if self.u64 else "II"), self.b, q)
            comp = self.b[q + 2 * self.int_len]
            if l == 0 or comp == 1:  # pointeur terminal ou description de la zone libre
                continue
            if comp & 4:  # bit 2 : ligne compressee (RLE ou RDC) ; valeurs vues : 4, 6, 13
                self._stored.append((4, bytes(self.b[base + o: base + o + l])))
                continue
            if comp != 0 and l != self.row_length:  # autre valeur (2, 3, 9) : ligne brute si elle fait row_length, sinon ignoree
                continue
            sh = bytes(self.b[base + o: base + o + l])
            if l < 2 * self.int_len:
                continue
            sig = self._signature(sh)
            if self.row_length and l == self.row_length and sig not in KNOWN_SIGS:
                self._stored.append((0, sh))  # ligne brute rangee comme sous-en-tete dans une table compressee
                continue
            if sig == SIG_ROW_SIZE:
                w = self.int_len
                self.row_length = self._word(sh, 5 * w)
                self.row_count = self._word(sh, 6 * w)
                self.deleted_count_header = self._word(sh, 7 * w)
                self.row_marker = self._word(sh, w)
            elif sig == SIG_COL_SIZE:
                self.col_count = self._word(sh, self.int_len)
            elif sig == SIG_COL_TEXT:
                size = struct.unpack_from(self.e + "H", sh, self.int_len)[0]
                self.texts.append(sh[self.int_len:self.int_len + size])
            elif sig == SIG_COL_NAME:
                n = (l - 2 * self.int_len - 12) // 8
                for j in range(n):
                    x = self.int_len + 8 + 8 * j
                    self.names.append(struct.unpack_from(self.e + "HHH", sh, x))
            elif sig == SIG_COL_ATTR:
                es = self.int_len + 8
                n = (l - 2 * self.int_len - 12) // es
                for j in range(n):
                    x = self.int_len + 8 + es * j
                    off = self._word(sh, x)
                    width, flag, typ = struct.unpack_from(self.e + "IHB", sh, x + self.int_len)
                    self.attrs.append((off, width, typ))
            elif sig == SIG_FORMAT:
                self.fmts.append(sh)

    def _signature(self, sh):
        if self.u64:
            hi = sh[:8]
            v = struct.unpack(self.e + "Q", hi)[0]
            if self.e == "<":
                return struct.unpack("<I", hi[:4])[0] if hi[4:] in (bytes(4), b"\xff\xff\xff\xff") else v
            # big endian 64 bits : 4 octets significatifs en tete (F7F7F7F7, F6F6F6F6 suivis de FFFFFBFE) ou valeur etendue
            if hi[:4] in (b"\xf7\xf7\xf7\xf7", b"\xf6\xf6\xf6\xf6"):
                return struct.unpack(">I", hi[:4])[0]
            return v & 0xFFFFFFFF
        return struct.unpack(self.e + "I", sh[:4])[0]

    def _word(self, sh, o):
        return struct.unpack_from(self.e + ("Q" if self.u64 else "I"), sh, o)[0]

    def _text(self, ref):
        idx, off, ln = ref
        if idx >= len(self.texts) or ln == 0:
            return ""
        raw = self.texts[idx][off:off + ln]
        return raw.decode(self.codec or "latin-1", "replace").rstrip(" \0")

    def _build_columns(self):
        for j, (off, width, typ) in enumerate(self.attrs):
            c = Column()
            c.offset, c.length, c.type = off, width, "n" if typ == 1 else "c"
            if j < len(self.names):
                c.name = self._text(self.names[j])
            if j < len(self.fmts):
                f = self.fmts[j]
                if self.u64:
                    c.fmt_width, c.fmt_dec = struct.unpack_from(self.e + "HH", f, 0x18)
                    c.inf_width, c.inf_dec = struct.unpack_from(self.e + "HH", f, 0x1C)
                    c.informat = self._text(struct.unpack_from(self.e + "HHH", f, 0x28))
                    c.format = self._text(struct.unpack_from(self.e + "HHH", f, 0x2E))
                    c.label = self._text(struct.unpack_from(self.e + "HHH", f, 0x34))
                else:
                    c.fmt_width, c.fmt_dec = struct.unpack_from(self.e + "HH", f, 0x0C)
                    c.inf_width, c.inf_dec = struct.unpack_from(self.e + "HH", f, 0x10)
                    c.informat = self._text(struct.unpack_from(self.e + "HHH", f, 0x1C))
                    c.format = self._text(struct.unpack_from(self.e + "HHH", f, 0x22))
                    c.label = self._text(struct.unpack_from(self.e + "HHH", f, 0x28))
            self.columns.append(c)

    # ------------------------------------------------------------------ lignes
    def _rows(self, base, ptype, bcount, scount):
        po = 32 if self.u64 else 16
        kind = ptype & 0x0F00
        if kind == 0x100:  # page de donnees : pas de pointeurs, lignes contigues
            start, n = base + po + 8, bcount
        elif kind == 0x200:  # page mixte : lignes apres la table des pointeurs
            ps = 24 if self.u64 else 12
            start = base + (po + 8 + scount * ps + 7) // 8 * 8  # debut des lignes arrondi au multiple de 8 suivant
            n = bcount - scount
        else:
            return
        n = max(0, min(n, self.row_count - self._seen))
        deleted = self._deleted(base, start, n) if ptype & 0x80 else set()
        for i in range(n):
            self._seen += 1
            if i in deleted:
                continue
            raw = self.b[start + i * self.row_length: start + (i + 1) * self.row_length]
            self.rows.append(self._decode(raw))

    _seen = 0

    def _deleted(self, base, start, n):
        """Lignes supprimees d'une page : bitmap place a (valeur de l'octet 24|12 de la page) apres la fin des lignes,
        un bit par ligne, bit de poids fort en premier, 1 = supprimee."""
        free = self._int_at(base + (24 if self.u64 else 12))
        bm = base + free + (start - base) + n * self.row_length
        out = set()
        for i in range(n):
            if self.b[bm + i // 8] & (0x80 >> (i % 8)):
                out.add(i)
        return out

    def _int_at(self, o):
        return struct.unpack_from(self.e + ("Q" if self.u64 else "I"), self.b, o)[0]

    def _decode(self, raw):
        out = []
        for c in self.columns:
            f = raw[c.offset:c.offset + c.length]
            if c.type == "c":
                f = b"" if not f.strip(b"\0") else f.rstrip(b" ")  # champ entierement nul = vide
                out.append(bytes(f) if self.raw else f.decode(self.codec or "latin-1", "replace"))
            else:
                out.append(self._number(f))
        return out

    def _number(self, f):
        if len(f) < 8:
            f = (bytes(8 - len(f)) + f) if self.e == "<" else (f + bytes(8 - len(f)))
        v = struct.unpack(self.e + "d", f)[0]
        if v != v:
            raw = f if self.e == "<" else f[::-1]
            tag = raw[5]
            if tag == 0xFE:
                return "."
            if tag == 0xFF:
                return "_"
            if 0xE4 <= tag <= 0xFD:
                return chr(ord("A") + 0xFD - tag)
            return "."
        return v


def main(argv):
    sf = SasFile(open(argv[1], "rb").read())
    if "--meta" in argv:
        for c in sf.columns:
            print(c.name, c.type, c.offset, c.length, repr(c.label), c.format, c.fmt_width, c.fmt_dec, c.informat)
        return 0
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow([c.name for c in sf.columns])
    for r in sf.rows:
        w.writerow([repr(x) if isinstance(x, float) else x for x in r])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
