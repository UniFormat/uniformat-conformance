"""Compresseurs et decompresseurs de reference RLE (SASYZCRL, COMPRESS=CHAR) et RDC (SASYZCR2, COMPRESS=BINARY).

Ecrits par un agent n'ayant lu que rea_output/15_compression.md (sections 3, 4, 5) et les vecteurs de
rea_output/tools/compression_vectors/. Le compresseur RLE reproduit les octets de SAS sur les 14 628 lignes compressees CHAR du corpus complementaire ; le compresseur RDC ne
cherche pas a les reproduire (ses flots sont plus courts, 240 lignes sur 390 differentes) : tout flot produit est decodable par les
decompresseurs de la specification (choix libres, 15_compression.md section 5).
Le choix brut / compresse est laisse a l'appelant."""

# ---------------------------------------------------------------- RLE (section 3)


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


def _rle_literal(out, lit):
    i = 0
    n_all = len(lit)
    while i < n_all:
        n = min(n_all - i, 4159)
        if n <= 64:
            hi = (n - 1) // 16
            out.append(0x80 + 16 * hi + (n - 1 - 16 * hi))
        else:
            v = n - 64
            out.append((v >> 8) & 0x0F)
            out.append(v & 0xFF)
        out += lit[i:i + n]
        i += n


def _rle_run(out, b, n):
    """Emet n >= (2 ou 3) fois b, en decoupant."""
    special = {0x40: (0x50, 0xD0), 0x20: (0x60, 0xE0), 0x00: (0x70, 0xF0)}
    while n > 0:
        if b in special:
            long_c, short_c = special[b]
            if n <= 17:
                out.append(short_c + n - 2)
                n = 0
            else:
                m = min(n, 4112)
                if 0 < n - m < 2:
                    m = n - 2
                v = m - 17
                out.append(long_c + (v >> 8))
                out.append(v & 0xFF)
                n -= m
        else:
            if n <= 18:
                out.append(0xC0 + n - 3)
                out.append(b)
                n = 0
            else:
                m = min(n, 4113)
                if 0 < n - m < 3:
                    m = n - 3
                v = m - 18
                out.append(0x40 + (v >> 8))
                out.append(v & 0xFF)
                out.append(b)
                n -= m


def rle_compress(raw: bytes) -> bytes:
    raw = bytes(raw)
    n = len(raw)
    out = bytearray()
    lit = bytearray()
    i = 0
    while i < n:
        b = raw[i]
        j = i
        while j < n and raw[j] == b:
            j += 1
        r = j - i
        minrun = 2 if b in (0x40, 0x20, 0x00) else 3
        if j == n:
            minrun += 1  # fin de ligne : SAS exige un octet de plus pour coder une suite (15_compression.md 3.2 ; 14 628 lignes identiques)
        if r >= minrun:
            if lit:
                _rle_literal(out, lit)
                lit = bytearray()
            # evite un reste de 1 octet apres decoupage d'une tres longue suite
            _rle_run(out, b, r)
            i = j
        else:
            lit += raw[i:j]
            i = j
    if lit:
        _rle_literal(out, lit)
    return bytes(out)


# ---------------------------------------------------------------- RDC (section 4)


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


def rdc_compress(raw: bytes) -> bytes:
    raw = bytes(raw)
    n = len(raw)
    elems = []  # (is_cmd, bytes)
    table = {}  # sequence de 3 octets -> positions (croissantes)
    pos = 0

    def register(p):
        if p + 3 <= n:
            table.setdefault(raw[p:p + 3], []).append(p)

    while pos < n:
        b = raw[pos]
        r = 1
        while pos + r < n and raw[pos + r] == b and r < 4114:
            r += 1
        # meilleure reference arriere (decalage 3..4098)
        best_len, best_ofs = 0, 0
        if pos + 3 <= n:
            cands = table.get(raw[pos:pos + 3], ())
            k = 0
            for q in reversed(cands):
                ofs = pos - q
                if ofs > _MAXOFS:
                    break
                if ofs >= 3:
                    L = 0
                    while pos + L < n and L < 271 and raw[pos + L] == raw[pos + L - ofs]:
                        L += 1
                    if L > best_len:
                        best_len, best_ofs = L, ofs
                        if L == 271:
                            break
                k += 1
                if k >= _MAXCAND:
                    break
        if r >= 3 and r >= best_len:
            if r <= 18:
                elems.append((True, bytes([0x00 | (r - 3), b])))
            else:
                v = r - 19
                elems.append((True, bytes([0x10 | (v & 0x0F), v >> 4, b])))
            step = r
        elif best_len >= 3:
            v = best_ofs - 3
            if best_len <= 15:
                elems.append((True, bytes([(best_len << 4) | (v & 0x0F), v >> 4])))
            else:
                elems.append((True, bytes([0x20 | (v & 0x0F), v >> 4, best_len - 16])))
            step = best_len
        else:
            elems.append((False, bytes([b])))
            step = 1
        for p in range(pos, pos + step):
            register(p)
        pos += step

    out = bytearray()
    for g in range(0, len(elems), 16):
        grp = elems[g:g + 16]
        ctrl = 0
        for j, (is_cmd, _) in enumerate(grp):
            if is_cmd:
                ctrl |= 0x8000 >> j
        out.append(ctrl >> 8)
        out.append(ctrl & 0xFF)
        for _, bs in grp:
            out += bs
    return bytes(out)
