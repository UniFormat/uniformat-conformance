#!/usr/bin/env python3
"""Vérificateur d'affichage des formats SAS : reproduit PUT(valeur, format) pour les formats de 30_formats_encodages.md.

Usage (module) : sasfmt.fmt(valeur, "date9.") -> str ; valeur = float, ou str pour un manquant (".", "._", ".A".. ".Z").
Les algorithmes sont déduits des sorties de l'oracle sas_small (corpus/gen/probe/fmt, evidence/fmt_display_*.txt),
jamais du code SAS. Les cas non reproduits sont listés par check_display.py.
"""
import datetime
import re
from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 400
EPOCH = datetime.date(1960, 1, 1)
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MONTHS_FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
DAYS_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MIN_YEAR, MAX_YEAR = 1582, 20000
# SAS ne reconnaît pas de 29 février en 4000 et en 8000 : à partir de ces jours le calendrier avance d'un jour de plus
GREG_4000 = (datetime.date(4000, 2, 29) - EPOCH).days if False else None


def _g(y, m, d):
    # date grégorienne proleptique au-delà de datetime.date (années ≥ 10000) : calcul direct du numéro de jour
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    jdn = d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    return jdn - 2436935  # 2436935 = JDN du 1960-01-01


def civil(days):
    """(année, mois, jour, jour de la semaine 0 = lundi, jour de l'année) d'un nombre de jours SAS, ou None hors plage."""
    n = int(days // 1)
    adj = n + sum(1 for k in (4000, 8000, 12000, 16000, 20000) if n >= _g(k, 2, 29))
    jdn = adj + 2436935
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    if year < MIN_YEAR or year > MAX_YEAR:
        return None
    wd = (n + 4) % 7  # 1960-01-01 est un vendredi (4 avec lundi = 0)
    doy = adj - _g(year, 1, 1) + 1
    return year, month, day, wd, doy


def parse_spec(spec):
    m = re.fullmatch(r"(\$?[A-Za-z]*)(\d*)\.?(\d*)(?: (\d+))?", spec.strip())
    return m.group(1).upper(), (int(m.group(2)) if m.group(2) else None), (int(m.group(3)) if m.group(3) else None)


def missing_char(tok):
    return "_" if tok == "._" else "." if tok == "." else tok[1:]


def D(x):
    return Decimal(repr(float(x)))


def rnd(x, d):
    return D(x).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)


def fixed(x, d, comma=False):
    v = rnd(abs(x), d)
    return f"{v:,.{d}f}" if comma else f"{v:.{d}f}"


def stars(w):
    return "*" * w


# ---------------------------------------------------------------------------- numériques
def best(x, w):
    if x == 0:
        return "0"
    neg = x < 0
    a = abs(x)
    room = w - (1 if neg else 0)
    sign = "-" if neg else ""
    ip = len(str(int(a))) if a >= 1 else 1
    if ip <= room and (a >= 1e-4 or a == 0):
        for d in range(min(max(0, room - ip - 1), 14), -1, -1):
            s = f"{rnd(a, d):f}"
            if "." in s:
                s = s.rstrip("0").rstrip(".")
            if len(s) <= room and (Decimal(s) != 0):
                return sign + s
        return sign + "0"
    for dig in range(14, 0, -1):
        m, e = f"{a:.{dig - 1}E}".split("E")
        if "." in m:
            m = m.rstrip("0").rstrip(".")
        s = f"{m}E{int(e)}"
        if len(s) <= room:
            return sign + s
    return stars(w)


def missing_wd(c, w, d, extra=0):
    """un manquant s'aligne sur la position du point décimal : largeur w - d (- extra), complétée à droite"""
    return (c.rjust(max(1, w - (d or 0) - extra))).ljust(w)


def f_wd(x, w, d):
    neg = x < 0
    for dd in range(d, -1, -1):
        s = ("-" if neg else "") + fixed(x, dd)
        if len(s) <= w:
            return s.rjust(w)
        if s.lstrip("-").startswith("0."):
            t = ("-" if neg else "") + s.lstrip("-")[1:]
            if len(t) <= w:
                return t.rjust(w)
    return best(x, w).rjust(w)


def f_comma(x, w, d, sym="", paren=False):
    neg = x < 0
    for dd in (d,):
        for comma, usesym in ((True, True), (False, True), (False, False)):
            body = fixed(x, dd, comma)
            s = (sym if usesym else "") + body
            if neg:
                s = f"({s})" if paren else (sym if usesym else "") + "-" + body
            elif paren:
                s = s + " "
            if len(s) <= w:
                return s.rjust(w)
    return best(x, w).rjust(w)


def f_percent(x, w, d):
    y = D(x) * 100
    neg = y < 0
    body = fixed(float(y), d) + "%"
    if neg:
        inner = body
        if len(inner) + 2 <= w:
            return "(" + inner.rjust(w - 2) + ")"
        return "(" + "*" * max(0, w - 3) + "%)"
    s = body + " "
    if len(s) <= w:
        return s.rjust(w)
    return (" " + "*" * max(0, w - 3) + "% ")[:w]


def f_z(x, w, d):
    neg = x < 0
    s = fixed(x, d)
    if neg:
        s = "-" + s
    if len(s) <= w:
        return ("-" + s[1:].rjust(w - 1, "0")) if neg else s.rjust(w, "0")
    b = f_wd(x, w, d)
    return b if "*" in b else b.replace(" ", "0")


def f_e(x, w, d):
    dd = max(0, w - 7) if d is None else max(0, w - 7)
    neg = x < 0
    a = abs(Decimal(repr(float(x)))) if x else Decimal(0)
    if a == 0:
        mant, ex = Decimal(0), 0
    else:
        ex = a.adjusted()
        mant = a.scaleb(-ex).quantize(Decimal(1).scaleb(-dd), rounding=ROUND_HALF_UP)
        if mant >= 10:
            ex += 1
            mant = (mant / 10).quantize(Decimal(1).scaleb(-dd), rounding=ROUND_HALF_UP)
    m = f"{mant:.{dd}f}" + ("." if dd == 0 else "")
    if dd == 0 and not neg:
        m = f"{mant:.1f}"
    s = ("-" if neg else "") + f"{m}E{'-' if ex < 0 else '+'}{abs(ex):02d}"
    return s.rjust(w) if len(s) <= w else best(x, w).rjust(w)


def f_roman(x, w):
    n = int(rnd(abs(x), 0))
    if n == 0:
        return "0".ljust(w)
    if n > 3999:
        return stars(w)
    out = ""
    for v, s in [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]:
        while n >= v:
            out += s
            n -= v
    if x < 0:
        out = "-" + out
    return out.ljust(w)[:w] if len(out) <= w else stars(w)


def f_ssn(x, w):
    n = int(abs(x) // 1) if x >= 0 else -1
    if x < 0 or n > 999999999:
        return "...-..-....".rjust(w) if w >= 11 else stars(w)
    s = f"{n:09d}"
    return f"{s[:3]}-{s[3:5]}-{s[5:]}"


# ---------------------------------------------------------------------------- dates, dates-heures, heures
def wrap(s, w):
    return s.rjust(w) if len(s) <= w else stars(w)


def f_date_family(x, name, w):
    c = civil(x)
    if c is None:
        return stars(w)
    y, mo, d, wd, doy = c
    yy = f"{y % 100:02d}"
    y4 = f"{y:04d}" if y <= 9999 else "****"
    dd, mon = f"{d:02d}", MONTHS[mo - 1]
    if name == "DATE":
        if w >= 11:
            return wrap(f"{dd}-{mon}-{y4}", w)
        if w == 10 or w == 9:
            return wrap(dd + mon + y4, w)
        return wrap({5: dd + mon, 6: dd + mon + yy[1], 7: dd + mon + yy, 8: dd + mon + yy}.get(w, ""), w)
    m = re.fullmatch(r"(YYMMDD|DDMMYY|MMDDYY)([BCDNPS]?)", name)
    if m:
        base, suf = m.groups()
        sep = {"": "-" if base == "YYMMDD" else "/", "B": " ", "C": ":", "D": "-", "N": "", "P": ".", "S": "/"}[suf]
        long_ = w >= 10 if suf != "N" else w >= 8
        yr = y4 if long_ else yy
        parts = {"YYMMDD": (yr, f"{mo:02d}", dd), "DDMMYY": (dd, f"{mo:02d}", yr), "MMDDYY": (f"{mo:02d}", dd, yr)}[base]
        if w <= 6 and suf != "N":
            parts = {"YYMMDD": (yy, f"{mo:02d}", dd), "DDMMYY": (dd, f"{mo:02d}", yy), "MMDDYY": (f"{mo:02d}", dd, yy)}[base]
            return wrap("".join(parts), w)
        if suf == "N" and w < 8:
            parts = {"YYMMDD": (yy, f"{mo:02d}", dd), "DDMMYY": (dd, f"{mo:02d}", yy), "MMDDYY": (f"{mo:02d}", dd, yy)}[base]
        return wrap(sep.join(parts), w)
    if name == "MONYY":
        return wrap(mon + (y4 if w >= 7 else yy), w)
    if name == "YYMON":
        return wrap((y4 if w >= 7 else yy) + mon, w)
    m = re.fullmatch(r"(YYMM|MMYY)([CDNPS]?)", name)
    if m:
        base, suf = m.groups()
        sep = {"": "M", "C": ":", "D": "-", "N": "", "P": ".", "S": "/"}[suf]
        yr = y4 if w >= (6 if suf == "N" else 7) else yy
        return wrap(sep.join((yr, f"{mo:02d}") if base == "YYMM" else (f"{mo:02d}", yr)), w)
    if name == "YYQ":
        return wrap((y4 if w >= 6 else yy) + f"Q{(mo - 1) // 3 + 1}", w)
    if name == "YYQR":
        return wrap((y4 if w >= 8 else yy) + "Q" + ["I", "II", "III", "IV"][(mo - 1) // 3], w)
    if name == "WORDDATE":
        s = f"{MONTHS_FULL[mo - 1]} {d}, {y}"
        return wrap(s[:w] if w < len(s) and False else s, w) if w >= len(s) else wrap(MONTHS_FULL[mo - 1][:w], w)
    if name == "WEEKDATE":
        full = f"{DAYS_FULL[wd]}, {MONTHS_FULL[mo - 1]} {d}, {y}"
        short = f"{DAYS_FULL[wd][:3]}, {MONTHS_FULL[mo - 1][:3]} {d}, {y}"
        return wrap(full if w >= len(full) else short, w)
    if name == "DOWNAME":
        return wrap(DAYS_FULL[wd][: (w if w else 9)], w)
    if name == "MONNAME":
        return wrap(MONTHS_FULL[mo - 1][: (w if w else 9)], w)
    if name == "MONTH":
        return wrap(str(mo), w)
    if name == "YEAR":
        return wrap(y4 if w >= 4 else yy, w)
    if name == "DAY":
        return wrap(str(d), w)
    if name == "QTR":
        return wrap(str((mo - 1) // 3 + 1), w)
    if name == "QTRR":
        return wrap(["I", "II", "III", "IV"][(mo - 1) // 3], w)
    if name == "WEEKDAY":
        return wrap(str((wd + 1) % 7 + 1), w)
    if name == "JULIAN":
        return stars(w) if (y > 9999 and w >= 7) else wrap((y4 if w >= 7 else yy) + f"{doy:03d}", w)
    if name == "JULDAY":
        return wrap(str(doy), w)
    raise KeyError(name)


def sec_round(x):
    return int(D(x).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def f_datetime(x, name, w, d):
    tot = sec_round(x) if not d else None
    base = x if d else tot
    days, rem = divmod(int(Decimal(repr(float(base))) // 1), 86400)
    c = civil(days)
    if c is None:
        return stars(w)
    y, mo, dd_, _, _ = c
    h, mi, s = rem // 3600, (rem % 3600) // 60, rem % 60
    frac = D(base) - (D(base) // 1) if d else Decimal(0)
    if name == "DATETIME":
        if w <= 12:
            return wrap(f"{dd_:02d}{MONTHS[mo - 1]}{y:04d}"[: max(w, 9)], w)
        yr = f"{y:04d}" if w >= 18 else f"{y % 100:02d}"
        secs = f":{s:02d}" if w >= 16 else ""
        if d and w >= 19 + 0:
            secs = f":{rnd(s + frac, d):0{3 + d}f}"
        return wrap(f"{dd_:02d}{MONTHS[mo - 1]}{yr}:{h:02d}:{mi:02d}{secs}", w)
    if name == "DATEAMPM":
        ap = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        yr = f"{y:04d}" if w >= 19 else f"{y % 100:02d}"
        if w >= 19:
            return wrap(f"{dd_:02d}{MONTHS[mo - 1]}{yr}:{h12:02d}:{mi:02d}:{s:02d} {ap}", w)
        return wrap(f"{dd_:02d}{MONTHS[mo - 1]}{yr}:{h:02d}", w)
    if name == "TOD":
        sec = f"{rnd(s + frac, d):0{3 + d}f}" if d else f"{s:02d}"
        return wrap(f"{h:02d}:{mi:02d}:{sec}", w)
    raise KeyError(name)


def f_time(x, name, w, d):
    neg = x < 0
    a = abs(x)
    tot = sec_round(a)
    if name == "TIME":
        if d:
            hh, rest = divmod(int(a // 1), 3600)
            mm, ss = divmod(rest, 60)
            sec = f"{rnd(ss + (D(a) - D(a) // 1), d):0{3 + d}f}"
            s = f"{hh}:{mm:02d}:{sec}"
        else:
            hh, rest = divmod(tot, 3600)
            mm, ss = divmod(rest, 60)
            s = f"{hh}:{mm:02d}:{ss:02d}" if w >= 8 else f"{hh}:{mm:02d}" if w >= 5 else f"{hh}"
            if len(("-" if neg else "") + s) > w:
                s = str(int(a // 3600))
        return wrap(("-" if neg else "") + s, w)
    if name == "HHMM":
        t = int(D(a / 60).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        hh, mm = divmod(t, 60)
        s = ("-" if neg else "") + f"{hh}:{mm:02d}"
        return s.rjust(w) if len(s) <= w else (best(float(hh), w).rjust(w) if w > 3 else stars(w))
    if name == "HOUR":
        v = D(a) / 3600
        s = f"{rnd(float(v), d or 0):f}"
        return s.rjust(w) if len(s) <= w else best(float(v), w).rjust(w)
    if name == "MMSS":
        t = tot
        mm, ss = divmod(t, 60)
        s = ("-" if neg else "") + f"{mm}:{ss:02d}"
        if len(s) > w:
            s = ("-" if neg else "") + str(int(a // 60))
        return wrap(s, w)
    if name == "TIMEAMPM":
        t = tot % 86400 if not neg else (-tot) % 86400
        hh, rest = divmod(t, 3600)
        mm, ss = divmod(rest, 60)
        ap = "AM" if hh < 12 else "PM"
        h12 = hh % 12 or 12
        return wrap(f"{h12}:{mm:02d}:{ss:02d} {ap}" if w >= 11 else f"{h12}:{mm:02d} {ap}" if w >= 8 else f"{h12} {ap}", w)
    raise KeyError(name)


# ---------------------------------------------------------------------------- point d'entrée
DATE_NAMES = {"DATE", "MONYY", "YYMON", "YYQ", "YYQR", "WORDDATE", "WEEKDATE", "DOWNAME", "MONNAME", "MONTH", "YEAR", "DAY", "QTR",
              "QTRR", "WEEKDAY", "JULIAN", "JULDAY"}


DEFAULT_W = {"DOWNAME": 9, "MONNAME": 9, "MONTH": 2, "DAY": 2, "QTR": 1, "QTRR": 3, "WEEKDAY": 1, "JULDAY": 3, "YEAR": 4, "DATE": 7,
             "MONYY": 5, "YYMON": 7, "YYQ": 6, "YYQR": 8, "WORDDATE": 18, "WEEKDATE": 29, "JULIAN": 5, "NLDATEMN": 9, "HOUR": 2, "HHMM": 5, "MMSS": 5}


def fmt(value, spec):
    name, w, d = parse_spec(spec)
    if isinstance(value, str):  # manquant
        c = missing_char(value)
        if name in ("", "F", "COMMA", "DOLLAR", "Z", "E") or re.fullmatch(r"(YYMMDD|DDMMYY|MMDDYY).*|YYMM.*", name):
            return missing_wd(c, w, d if name in ("", "F", "COMMA", "DOLLAR", "Z") else 0)
        if name == "PERCENT":
            return missing_wd(c, w, d, extra=2)
        return c.rjust(w or DEFAULT_W.get(name) or 12)
    x = float(value)
    if name in ("", "F"):
        return f_wd(x, w or 12, d or 0)
    if name == "BEST":
        return best(x, w or 12).rjust(w or 12)
    if name == "E":
        return f_e(x, w or 12, d)
    if name == "COMMA":
        return f_comma(x, w or 6, d or 0)
    if name == "DOLLAR":
        return f_comma(x, w or 6, d or 0, sym="$")
    if name == "PERCENT":
        return f_percent(x, w or 6, d or 0)
    if name == "Z":
        return f_z(x, w or 8, d or 0)
    if name == "NEGPAREN":
        return f_comma(x, w or 6, d or 0, paren=True)
    if name == "ROMAN":
        return f_roman(x, w or 6)
    if name == "SSN":
        return f_ssn(x, w or 11)
    if w is None and name in DEFAULT_W:
        w = DEFAULT_W[name]
    if name in DATE_NAMES or re.fullmatch(r"(YYMMDD|DDMMYY|MMDDYY)[BCDNPS]?|(YYMM|MMYY)[CDNPS]?", name):
        return f_date_family(x, name, w or 7)
    if name in ("DATETIME", "DATEAMPM", "TOD"):
        return f_datetime(x, name, w or 16, d)
    if name in ("TIME", "HHMM", "HOUR", "MMSS", "TIMEAMPM"):
        return f_time(x, name, w or 8, d)
    raise KeyError(spec)


def fmt_char(v, spec):
    name, w, d = parse_spec(spec)
    if name in ("$CHAR", "$F", "$", "$HEX", "$BINARY", "$OCTAL"):
        return v[:w].rstrip(" ") if name == "$" else v[:w]
    if name == "$QUOTE":
        return '"' + v[: w - 2].rstrip(" ") + '"' if w and w > 2 else '""'[:w]
    raise KeyError(spec)
