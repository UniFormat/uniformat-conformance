#!/bin/sh
# Rejoue toutes les verifications de rea_output/10_format_sas7bdat.md et depose les sorties dans rea_output/evidence/.
#   sh rea_output/tools/run_checks.sh [dossier corpus]     (defaut : corpus/ ; une copie locale accelere beaucoup)
set -u
HOTE=$(cd "$(dirname "$0")/../.." && pwd)
C=${1:-$HOTE/corpus}
T=$HOTE/rea_output/tools
E=$HOTE/rea_output/evidence
mkdir -p "$E"
py() { python3 -I "$@"; }
py "$T/compare_csv.py" "$C/files" "" > "$E/compare_csv_files.txt"; tail -1 "$E/compare_csv_files.txt"
py "$T/compare_csv.py" "$C/external" "" > "$E/compare_csv_external.txt"; tail -1 "$E/compare_csv_external.txt"
py "$T/check_contents.py" "$C/files" "" > "$E/check_contents_files.txt"; tail -1 "$E/check_contents_files.txt"
py "$T/fields.py" coverage "$C/files/*/*.sas7bdat" "$C/external/*/*.sas7bdat" > "$E/header_coverage.txt"; tail -1 "$E/header_coverage.txt"
py "$T/fields.py" unknowns "$C/files/*/*.sas7bdat" "$C/external/*/*.sas7bdat" > "$E/zones_non_decodees.md"
py "$T/fields.py" annotate "$C/files/base/base_n100_mix_no.sas7bdat" > "$E/en_tete_annote_base_n100_mix_no.txt"
py "$T/inspect_sas7bdat.py" "$C/files/base/base_n100_mix_no.sas7bdat" --subheaders > "$E/structure_base_n100_mix_no.txt"
py "$T/inspect_sas7bdat.py" "$C/files/suppression/suppression_n100_del10_no.sas7bdat" --subheaders > "$E/structure_suppression_n100_del10_no.txt"
py "$T/inspect_sas7bdat.py" "$C/files/index/index_n100_ix_no.sas7bdat" --subheaders > "$E/structure_index_n100_ix_no.txt"
py "$T/diff_pair.py" "$C/files/base/base_n100_mix_no.sas7bdat" "$C/files/base/base_n2_mix_no.sas7bdat" > "$E/diff_base_n100_vs_n2.txt"
py "$T/diff_pair.py" "$C/files/encodage/encodage_utf8_no.sas7bdat" "$C/files/encodage/encodage_latin1_no.sas7bdat" > "$E/diff_encodage_utf8_vs_latin1.txt"
py "$T/diff_pair.py" "$C/files/plateforme/plateforme_linux_x86_64_no.sas7bdat" "$C/files/plateforme/plateforme_windows_32_no.sas7bdat" > "$E/diff_plateforme_linux64_vs_windows32.txt"
py "$T/diff_pair.py" "$C/files/base/base_n100_mix_no.sas7bdat" "$C/files/suppression/suppression_n100_del10_no.sas7bdat" > "$E/diff_base_vs_suppression.txt"
py "$T/check_spec.py" "$HOTE/rea_output/10_format_sas7bdat.md" "$HOTE/rea_output/60_inconnues.md" > "$E/check_spec.txt"; tail -1 "$E/check_spec.txt"
py "$T/check_compression.py" "$C" corpus > "$E/compression_corpus.txt"; tail -1 "$E/compression_corpus.txt"
grep '^RLE' "$E/compression_corpus.txt" > "$E/compression_rle_corpus.txt"; grep '^RDC' "$E/compression_corpus.txt" > "$E/compression_rdc_corpus.txt"
py "$T/check_compression.py" "$C" externes > "$E/compression_externes.txt"; tail -1 "$E/compression_externes.txt"
py "$T/check_compression.py" "$C" pointeurs > "$E/compression_pointeurs.txt"
py "$T/check_compression.py" "$C" litteraux > "$E/compression_litteraux.txt"; tail -1 "$E/compression_litteraux.txt"
py "$T/test_compression.py" > "$E/compression_vecteurs.txt"; tail -3 "$E/compression_vecteurs.txt"
py "$T/check_display.py" > "$E/verification_affichage.txt"; tail -1 "$E/verification_affichage.txt"
py "$T/check_encoding.py" "$C" > "$E/verification_encodage.txt"; tail -1 "$E/verification_encodage.txt"
py "$T/make_encoding_table.py" "$C" > "$E/table_encodages.md" && echo "table des encodages : tous les codes du corpus presents"
py "$T/format_classification.py" --check
py "$T/catalog_dump.py" "$C/files/catalogue/formats.sas7bcat" > "$E/catalogue_dump_partiel.txt"
# test negatif : un ecart introduit volontairement doit etre signale par compare_csv
N=$(mktemp -d)
mkdir -p "$N/files/base"
cp "$C/files/base/base_n100_mix_no.sas7bdat" "$C/files/base/base_n100_mix_no.csv" "$N/files/base/"
py - "$N/files/base/base_n100_mix_no.sas7bdat" <<'PYEOF'
import sys
p = sys.argv[1]
b = bytearray(open(p, "rb").read())
b[0x10000 + 304 + 4 * 24 + 8 + 6] ^= 0x01   # ligne 5, colonne x : un bit de l'exposant
open(p, "wb").write(b)
PYEOF
py "$T/compare_csv.py" "$N/files" "" > "$E/test_negatif_ecart.txt"; cat "$E/test_negatif_ecart.txt"
rm -rf "$N"
