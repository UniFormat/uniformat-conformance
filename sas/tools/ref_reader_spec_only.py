"""Lecteur sas7bdat non compresse, ecrit a partir de la seule specification
10_format_sas7bdat.md (bibliotheque standard uniquement)."""
import struct
import math

MAGIC = bytes.fromhex("000000000000000000000000C2EA8160B31411CFBD92080009C7318C181F1011")

# Seules correspondances donnees par la specification (sec. 2.1, octet 70)
ENC_CODES = {20: 'utf-8', 29: 'latin-1', 62: 'cp1252', 138: 'shift_jis'}

SIG_ROWSIZE = 0xF7F7F7F7
SIG_COLSIZE = 0xF6F6F6F6
SIG_COUNTS = 0xFFFFFC00
SIG_COLTEXT = 0xFFFFFFFD
SIG_COLNAME = 0xFFFFFFFF
SIG_COLATTR = 0xFFFFFFFC
SIG_FMTLAB = 0xFFFFFBFE
SIG_COLLIST = 0xFFFFFFFE


class Column:
    def __init__(self):
        self.name = ''
        self.type = 'n'
        self.offset = 0
        self.length = 0
        self.label = ''
        self.format = ''
        self.fmt_width = 0
        self.fmt_dec = 0
        self.informat = ''
        self.inf_width = 0
        self.inf_dec = 0


def _missing_label(code):
    if code == 0xFE:
        return '.'
    if code == 0xFF:
        return '_'
    if 0xE4 <= code <= 0xFD:
        return chr(ord('A') + (0xFD - code))
    return None


class SasFile:
    def __init__(self, data: bytes, raw: bool = False):
        self.raw = raw
        self.columns = []
        self.rows = []
        self.compression = None
        self.codec = None
        self.encoding_code = 0
        self.data = data
        self._parse()

    # ------------------------------------------------------------------
    def _parse(self):
        d = self.data
        if len(d) < 352 or d[:32] != MAGIC:
            raise ValueError("pas un fichier sas7bdat (magic)")
        self.w = w = 8 if d[32] == 0x33 else 4
        a2 = 4 if d[32] == 0x33 else 0
        a1 = 4 if d[35] == 0x33 else 0
        self.le = d[37] == 1
        self.e = '<' if self.le else '>'
        self.encoding_code = d[70]
        self.codec = ENC_CODES.get(self.encoding_code)
        e = self.e
        self.header_length = struct.unpack_from(e + 'I', d, 196 + a1)[0]
        self.page_length = struct.unpack_from(e + 'I', d, 200 + a1)[0]
        if w == 8:
            self.page_count = struct.unpack_from(e + 'Q', d, 204 + a1)[0]
        else:
            self.page_count = struct.unpack_from(e + 'I', d, 204 + a1)[0]
        if len(d) < self.header_length + self.page_length * self.page_count:
            raise ValueError("fichier tronque")
        self.po = po = 32 if w == 8 else 16
        self.ps = 24 if w == 8 else 12

        self.row_length = 0
        self.row_count = 0
        self.deleted_count = 0
        self.col_count = 0
        self.row_marker = 0
        texts = []      # blocs de texte
        names = []      # (idx, off, len)
        attrs = []      # (offset, width, flags, type)
        fmts = []       # tuples
        self._page_info = []
        comp_flag = None

        # ---------------- premiere passe : metadonnees
        for k in range(self.page_count):
            base = self.header_length + k * self.page_length
            ptype, bcount, scount = struct.unpack_from(e + 'HHH', d, base + po)
            self._page_info.append((base, ptype, bcount, scount))
            if ptype & 0xFF00 in (0x0000, 0x0200, 0x0400, 0x4000):
                for i in range(scount):
                    p = base + po + 8 + i * self.ps
                    off = self._uw(d, p)
                    ln = self._uw(d, p + w)
                    comp = d[p + 2 * w]
                    if ln == 0:
                        continue
                    if comp != 0:
                        if comp == 4 and comp_flag is None:
                            comp_flag = '?'
                        continue
                    sub = d[base + off: base + off + ln]
                    self._subheader(sub, texts, names, attrs, fmts)
            elif ptype & 0xFF00 == 0x9000 or ptype & 0xF000 == 0x9000:
                comp_flag = comp_flag or '?'
        self.texts = texts

        # compression ?
        for t in texts:
            if b'SASYZCRL' in t[:40]:
                self.compression = 'RLE'
            elif b'SASYZCR2' in t[:40]:
                self.compression = 'RDC'
        if self.compression is None and comp_flag:
            self.compression = comp_flag
        if self.compression is None and self.row_marker == 0x131:
            # indication faible (voir rapport)
            pass

        # codec par defaut si inconnu
        # colonnes
        ncol = max(len(names), len(attrs))
        self.columns = []
        for j in range(ncol):
            c = Column()
            if j < len(names):
                idx, off, ln = names[j]
                c.name = self._text(idx, off, ln)
            if j < len(attrs):
                o, wd, fl, ty = attrs[j]
                c.offset = o
                c.length = wd
                c.type = 'n' if ty == 1 else 'c'
            if j < len(fmts):
                (fw, fd, iw, idc, iref, fref, lref) = fmts[j]
                c.fmt_width, c.fmt_dec = fw, fd
                c.inf_width, c.inf_dec = iw, idc
                c.informat = self._text(*iref)
                c.format = self._text(*fref)
                c.label = self._text(*lref)
            self.columns.append(c)

        if self.compression:
            self.rows = []
            return
        self._read_rows()

    # ------------------------------------------------------------------
    def _uw(self, d, p):
        if self.w == 8:
            return struct.unpack_from(self.e + 'Q', d, p)[0]
        return struct.unpack_from(self.e + 'I', d, p)[0]

    def _text(self, idx, off, ln):
        if ln == 0 or idx >= len(self.texts):
            return ''
        b = self.texts[idx][off:off + ln]
        return self._dec(b).rstrip(' ')

    def _dec(self, b):
        codec = self.codec or 'latin-1'
        try:
            return b.decode(codec)
        except Exception:
            return b.decode(codec, errors='replace')

    def _subheader(self, sub, texts, names, attrs, fmts):
        w, e = self.w, self.e
        if len(sub) < w:
            return
        sig = struct.unpack_from(e + 'I', sub, 0)[0]
        if sig not in (SIG_ROWSIZE, SIG_COLSIZE) and w == 8 and not self.le:
            sig = struct.unpack_from(e + 'I', sub, 4)[0]
        L = len(sub)
        if sig == SIG_ROWSIZE:
            m = lambda k: self._uw(sub, k * w)
            self.row_marker = m(1)
            self.row_length = m(5)
            self.row_count = m(6)
            self.deleted_count = m(7)
        elif sig == SIG_COLSIZE:
            self.col_count = self._uw(sub, w)
        elif sig == SIG_COLTEXT:
            ts = struct.unpack_from(e + 'H', sub, w)[0]
            texts.append(bytes(sub[w:w + ts]))
        elif sig == SIG_COLNAME:
            n = (L - 2 * w - 12) // 8
            for j in range(n):
                p = w + 8 + 8 * j
                idx, off, ln, _ = struct.unpack_from(e + 'HHHH', sub, p)
                names.append((idx, off, ln))
        elif sig == SIG_COLATTR:
            n = (L - 2 * w - 12) // (w + 8)
            for j in range(n):
                p = w + 8 + (w + 8) * j
                o = self._uw(sub, p)
                wd = struct.unpack_from(e + 'I', sub, p + w)[0]
                fl = struct.unpack_from(e + 'H', sub, p + w + 4)[0]
                ty = sub[p + w + 6]
                attrs.append((o, wd, fl, ty))
        elif sig == SIG_FMTLAB:
            if w == 8:
                oW, oI, oR = 0x18, 0x28, (0x2E, 0x34)
            else:
                oW, oI, oR = 0x0C, 0x1C, (0x22, 0x28)
            fw, fd, iw, idc = struct.unpack_from(e + 'HHHH', sub, oW)
            iref = struct.unpack_from(e + 'HHH', sub, oI)
            fref = struct.unpack_from(e + 'HHH', sub, oR[0])
            lref = struct.unpack_from(e + 'HHH', sub, oR[1])
            fmts.append((fw, fd, iw, idc, iref, fref, lref))

    # ------------------------------------------------------------------
    def _read_rows(self):
        d, e, w, po = self.data, self.e, self.w, self.po
        rl = self.row_length
        remaining = self.row_count
        out = []
        for (base, ptype, bcount, scount) in self._page_info:
            if remaining <= 0:
                break
            hi = ptype & 0xFF00
            if hi == 0x0100:
                start = base + po + 8
                n = bcount
            elif hi == 0x0200:
                start = base + ((po + 8 + scount * self.ps + 7) // 8) * 8
                n = bcount - scount
            else:
                continue
            npage = n
            n = min(n, remaining)
            bitmap = None
            if ptype & 0x0080:
                fb = self._uw(d, base + (24 if w == 8 else 12))
                bstart = start + npage * rl + fb
                nb = (n + 7) // 8
                bitmap = d[bstart: bstart + nb]
            for i in range(n):
                if bitmap is not None and (bitmap[i >> 3] >> (7 - (i & 7))) & 1:
                    continue
                rec = d[start + i * rl: start + (i + 1) * rl]
                out.append(self._decode_row(rec))
            remaining -= n
        self.rows = out

    def _decode_row(self, rec):
        row = []
        le = self.le
        for c in self.columns:
            b = rec[c.offset:c.offset + c.length]
            if c.type == 'n':
                n = len(b)
                if n < 8:
                    b = (b'\x00' * (8 - n) + b) if le else (b + b'\x00' * (8 - n))
                v = struct.unpack(self.e + 'd', b)[0]
                if v != v:
                    if le:
                        code = b[5]
                    else:
                        code = b[2]
                    lab = _missing_label(code)
                    row.append(lab if lab is not None else '.')
                else:
                    row.append(v)
            else:
                if b.count(0) == len(b):
                    b = b''
                b = b.rstrip(b' ')
                if self.raw:
                    row.append(bytes(b))
                else:
                    row.append(self._dec(bytes(b)))
        return row


def n_rows_end(n, rl):
    return n * rl
