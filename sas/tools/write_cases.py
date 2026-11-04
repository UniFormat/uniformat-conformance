"""Cas de la montee en complexite de l'ecrivain de reference (rea_output/tools/validate_write.py)."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_writer as W  # noqa: E402


def case(name, desc, cols, rows, **kw):
    return dict(name=name, desc=desc, cols=cols, rows=rows, **kw)


def cases():
    out = []
    out.append(case("w01_minimal", "1 colonne num, 1 ligne", [W.Col("x", "n", 8)], [[1.5]]))
    # 5.1 plusieurs colonnes num et char
    cols = [W.Col("i", "n", 8), W.Col("x", "n", 8), W.Col("c", "c", 5), W.Col("t", "c", 20)]
    rows = [[k, k * 1.5, "%05d" % k, "ligne %d" % k] for k in range(1, 101)]
    out.append(case("w02_multicol", "2 num + 2 char, 100 lignes", cols, rows))
    # 5.2 longueurs numeriques 3 a 8
    for n in range(3, 9):
        out.append(case(f"w03_num{n}", f"colonne numerique de {n} octets", [W.Col("i", "n", 8), W.Col("x", "n", n)], [[1, 1.25], [2, 2.5], [3, -0.5], [4, 100.0], [5, 0.0]]))
    # 5.3 manquants speciaux
    miss = [".", "_"] + [chr(c) for c in range(65, 91)]
    out.append(case("w04_missing", "28 manquants speciaux", [W.Col("x", "n", 8)], [[m] for m in miss]))
    # 5.4 labels, formats, informats
    cols = [W.Col("d", "n", 8, label="Date de naissance", fmt=("DATE", 9, 0)), W.Col("m", "n", 8, label="Montant", fmt=("COMMA", 10, 2), informat=("DATE", 9, 0)),
            W.Col("s", "c", 10, label="Libell\u00e9 accentu\u00e9 \u00e9 \u00fc \u00f1", fmt=("$CHAR", 10, 0))]
    out.append(case("w05_meta", "labels, formats et informats", cols, [[0, 1234.5, "abc"], [21915, -0.25, "defghij"]], skip=("Parso",), skip_why="Parso rend les dates en java.util.Date"))
    out.append(case("w05b_informat", "informat DATE9 seul", [W.Col("d", "n", 8, informat=("DATE", 9, 0))], [[0], [21915]], skip=("Parso",), skip_why="Parso rend les dates en java.util.Date"))
    out.append(case("w05c_infmt_only_char", "informat $CHAR seul", [W.Col("s", "c", 8, informat=("$CHAR", 8, 0))], [["abc"]]))
    # 5.5 noms longs et non ASCII
    n32 = "abcdefghijklmnopqrstuvwxyz123456"
    out.append(case("w06_names", "nom de 32 octets et valeurs non ASCII", [W.Col(n32, "n", 8), W.Col("texte", "c", 30)], [[1, "caf\u00e9 \u65e5\u672c\u8a9e"], [2, "\u00e9t\u00e9 \u00f1"]]))
    # 5.6 plusieurs pages
    out.append(case("w07_pages", "3000 lignes : page mixte puis page de donnees", [W.Col("i", "n", 8), W.Col("x", "n", 8), W.Col("c", "c", 5)],
                    [[k, k / 4, "%05d" % k] for k in range(1, 3001)]))
    out.append(case("w08_pages_buf", "page de 4096 octets", [W.Col("i", "n", 8), W.Col("c", "c", 20)], [[k, "v%d" % k] for k in range(1, 500)], page_length=4096))
    # 5.7 beaucoup de colonnes
    cols = [W.Col("v%d" % k, "n", 8) for k in range(1, 301)]
    out.append(case("w09_manycols", "300 colonnes numeriques", cols, [[k + j for j in range(300)] for k in range(1, 4)]))
    # 5.8 table a 0 ligne
    out.append(case("w10_zero", "table a 0 ligne", [W.Col("x", "n", 8), W.Col("c", "c", 4)], []))
    # 5.10 tables compressees : COMPRESS=CHAR (RLE) puis COMPRESS=BINARY (RDC)
    import random
    rnd = random.Random(7)
    def noise(k):
        return "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(k))
    for algo, tag in (("CHAR", "char"), ("BINARY", "binary")):
        cols = [W.Col("i", "n", 8), W.Col("x", "n", 8), W.Col("a", "c", 40), W.Col("b", "c", 12)]
        out.append(case(f"w11_{tag}_one", f"COMPRESS={algo}, 1 ligne", cols, [[1, 2.5, "bonjour", "xyz"]], compress=algo))
        out.append(case(f"w11_{tag}_small", f"COMPRESS={algo}, 255 lignes compressibles (maximum relu par SAS)", cols,
                        [[k, k / 4, "ligne %d" % (k % 7), "ab" * (k % 5)] for k in range(1, 256)], compress=algo))
        out.append(case(f"w11_{tag}_256", f"COMPRESS={algo}, 256 lignes", cols, [[k, k / 4, "ligne %d" % (k % 7), "ab" * (k % 5)] for k in range(1, 257)], compress=algo))
        out.append(case(f"w11_{tag}_1000", f"COMPRESS={algo}, 1000 lignes", cols, [[k, k / 4, "ligne %d" % (k % 7), "ab" * (k % 5)] for k in range(1, 1001)], compress=algo))
        out.append(case(f"w11_{tag}_10000", f"COMPRESS={algo}, 10000 lignes sur plusieurs pages de 65536 octets", cols,
                        [[k, k / 4, "ligne %d" % (k % 7), "ab" * (k % 5)] for k in range(1, 10001)], compress=algo))
        out.append(case(f"w11_{tag}_70000", f"COMPRESS={algo}, 70000 lignes (plus de 65535 : cumul de la page marqueur sur 64 bits)", cols,
                        [[k, k / 4, "ligne %d" % (k % 7), "ab" * (k % 5)] for k in range(1, 70001)], compress=algo))
        out.append(case(f"w11_{tag}_pg4096", f"COMPRESS={algo}, 300 lignes, pages de 4096 octets", cols,
                        [[k, k / 4, "ligne %d" % (k % 7), "ab" * (k % 5)] for k in range(1, 301)], compress=algo, page_length=4096))
        cols2 = [W.Col("i", "n", 8), W.Col("a", "c", 100)]
        out.append(case(f"w11_{tag}_noise", f"COMPRESS={algo}, lignes peu compressibles (texte aleatoire)", cols2,
                        [[k, noise(100)] for k in range(1, 121)], compress=algo))
        out.append(case(f"w11_{tag}_pages", f"COMPRESS={algo}, 6000 lignes sur plusieurs pages", cols,
                        [[k, k / 4, "ligne %d" % (k % 97), noise(k % 12)] for k in range(1, 6001)], compress=algo))
        out.append(case(f"w11_{tag}_zero", f"COMPRESS={algo}, 0 ligne", cols, [], compress=algo))
        out.append(case(f"w11_{tag}_mini", f"COMPRESS={algo} demande, ligne de 3 octets : table ordinaire", [W.Col("x", "n", 3)], [[1.0], [2.0], [3.0]], compress=algo))
        out.append(case(f"w11_{tag}_len15", f"COMPRESS={algo} demande, ligne de 15 octets : table ordinaire", [W.Col("x", "n", 8), W.Col("c", "c", 7)], [[1.0, "ab"], [2.0, "cd"]], compress=algo))
        out.append(case(f"w11_{tag}_len16", f"COMPRESS={algo}, ligne de 16 octets", [W.Col("x", "n", 8), W.Col("c", "c", 8)], [[1.0, "ab"], [2.0, "cd"], [3.0, "efghijkl"]], compress=algo))
    # 5.11 encodages non UTF-8 (30_formats_encodages.md section 6)
    cols = [W.Col("i", "n", 8), W.Col("caf\u00e9", "n", 8, label="Libell\u00e9 \u00e0 accents"), W.Col("t", "c", 20)]
    out.append(case("w12_latin1", "encodage latin1 (code 29), nom, label et texte accentues", cols, [[1, 2.5, "\u00e9t\u00e9 \u00fc \u00f1"], [2, -1, "\u00e0 bient\u00f4t"]], enc_code=29, codec="latin-1",
                    known_ko={"pyreadstat": "pyreadstat 1.2.9 refuse le code d'encodage 29 (unsupported character set) ; le code 62 est accepte (20_ecriture.md 6.4)"}))
    out.append(case("w12_wlatin1", "encodage wlatin1 (code 62), caracteres 0x80..0x9F", cols, [[1, 2.5, "prix 5\u20ac \u0153uvre"], [2, -1, "\u201cguillemets\u201d"]], enc_code=62, codec="cp1252"))
    # 5.9 gros volume (> 2 Go)
    out.append(case("w15_gt2gb", "table de plus de 2 Go", [W.Col("c", "c", 32767)], [], not_feasible="non faisable ici : l'ecrivain de reference garde toutes les lignes en memoire (plus de 65 000 lignes de 32 767 octets pour depasser 2 Go) ; la relecture par SAS sous emulation x86-64 coute plusieurs minutes par gigaoctet ; les decalages et compteurs de pages sont des u64 dans le format, aucun champ de 32 bits n'a ete releve (inconnue W08)"))
    # 6.1 tailles de page non par defaut
    for pl in (1024, 8192, 131072, 1048576):
        out.append(case(f"w13_page{pl}", f"taille de page {pl}", [W.Col("i", "n", 8), W.Col("c", "c", 20)], [[k, "v%d" % k] for k in range(1, 400)], page_length=pl))
    out.append(case("w13_page5000", "taille de page 5000 (pas une puissance de 2)", [W.Col("i", "n", 8), W.Col("c", "c", 20)], [[k, "v%d" % k] for k in range(1, 400)], page_length=5000))
    # 6.3 limites
    n32 = "n" * 32
    out.append(case("w14_name33", "nom de colonne de 33 octets (au dela de la limite SAS)", [W.Col("n" * 33, "n", 8)], [[1]],
                    known_ko={"SAS": "limite de 32 octets : SAS tronque le nom et signale ERROR (« contains more than 32 bytes »)"}))
    out.append(case("w14_label256", "label de 256 octets (limite SAS)", [W.Col("x", "n", 8, label="L" * 256)], [[1]]))
    out.append(case("w14_label257", "label de 257 octets (au dela de la limite)", [W.Col("x", "n", 8, label="L" * 257)], [[1]],
                    known_ko={"SAS": "limite de 256 octets : SAS tronque le label et signale WARNING (donnees perdues au transcodage)"}))
    out.append(case("w14_char32767", "colonne caractere de 32 767 octets (limite SAS)", [W.Col("c", "c", 32767)], [["a" * 100], ["b" * 32767]], no_print=True, csv_plain=True))
    out.append(case("w14_char32768", "colonne caractere de 32 768 octets (au dela de la limite)", [W.Col("c", "c", 32768)], [["a" * 100]], no_print=True,
                    known_ko={"SAS": "limite de 32 767 octets : SAS refuse (insufficient memory)", "pyreadstat": "ReadStat refuse une colonne de 32 768 octets"}))
    out.append(case("w14_cols700", "700 colonnes (metadonnees sur la page 0)", [W.Col("v%d" % k, "n", 8) for k in range(1, 701)], [[k + j for j in range(700)] for k in range(1, 3)], page_length=131072))
    return out


def build(c, path):
    W.write(path, c["cols"], c["rows"], seed=hash(c["name"]) & 0xFFFFFFFF, **{k: v for k, v in c.items() if k in ("compress", "page_length", "enc_code", "codec")})
