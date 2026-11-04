#!/bin/sh
# Execute tous les programmes de generation du corpus.
#
#   corpus/gen/run_all.sh small   # oracle sas_small (Docker) : variantes COMPRESS=NO uniquement
#   SAS_FULL_CMD=/chemin/sas_u8 corpus/gen/run_all.sh full   # SAS complet d'origine : tout
#
# Les deux modes ecrivent dans des dossiers distincts pour ne jamais s'ecraser :
#   small -> corpus/files_sas_small/  et journaux dans corpus/out/
#   full  -> corpus/files/            et journaux dans corpus/out_full/
# Resume ecrit dans <journaux>/run_summary.tsv (programme, code retour, nombre de lignes ERROR).
# Un programme qui echoue n'arrete pas les suivants.
set -u
MODE=${1:-small}
HOTE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$HOTE"

case "$MODE" in
  small)
    GEN=corpus/gen
    FILES=files_sas_small
    OUT=corpus/out
    python3 -I corpus/gen/build_programs.py --files-dir "$FILES" >/dev/null
    ;;
  full)
    : "${SAS_FULL_CMD:?definir SAS_FULL_CMD (lanceur du SAS complet, ex. .../sas_u8)}"
    GEN=corpus/gen_full
    FILES=files
    OUT=corpus/out_full
    mkdir -p "$GEN"
    python3 -I corpus/gen/build_programs.py --root "$HOTE/corpus" --outdir "$GEN" --files-dir "$FILES" >/dev/null
    ;;
  *) echo "usage: $0 small|full" >&2; exit 2 ;;
esac

mkdir -p "$OUT"
tail -n +2 "$GEN/tables.tsv" | cut -f2 | sort -u | while read -r fam; do mkdir -p "corpus/$FILES/$fam"; done
: > "$OUT/run_summary.tsv"

tail -n +2 "$GEN/programmes.tsv" | while IFS="$(printf '\t')" read -r prog oracle; do
  if [ "$MODE" = small ] && [ "$oracle" != small ]; then
    printf '%s\tNON_EXECUTE\t-\t(necessite le SAS complet)\n' "$prog" >> "$OUT/run_summary.tsv"
    continue
  fi
  nom=$(basename "$prog" .sas)
  if [ "$MODE" = small ]; then
    oracle/run_sas.sh "gen/$prog" >/dev/null 2>&1
  else
    "$SAS_FULL_CMD" -sysin "$GEN/$prog" -log "$OUT/$nom.log" -print "$OUT/$nom.lst" >/dev/null 2>&1
  fi
  rc=$?
  python3 -I corpus/gen/split_listing.py "$OUT/$nom.lst" "$FILES" >/dev/null 2>&1
  err=$(grep -c '^ERROR' "$OUT/$nom.log" 2>/dev/null || true)
  printf '%s\t%s\t%s\t\n' "$prog" "$rc" "$err" >> "$OUT/run_summary.tsv"
  echo "$prog rc=$rc ERROR=$err"
done
