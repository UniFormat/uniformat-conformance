# Matrice de validation de l'écrivain de référence

Fichiers produits par `rea_output/tools/ref_writer.py` (cas dans `write_cases.py`, boucle dans `validate_write.py`), relus par les lecteurs disponibles :

| lecteur | version | usage |
|---|---|---|
| SAS | 9.4 TS1M7, oracle `sas_small` (Docker linux/amd64, `oracle/run_sas.sh`) | `PROC CONTENTS`, `PROC PRINT`, `data _null_; set lib.t`, journal sans `ERROR` ni `WARNING` |
| pandas | 2.3.3 (Python 3.9, venv hors dépôt) | `read_sas`, données |
| pyreadstat | 1.2.9 (ReadStat) | données et métadonnées |
| Parso | 2.0.14 (Java 26) | données (`ParsoDump.java`) |
| `ref_reader.py` | écrit depuis `10_format_sas7bdat.md` | données et métadonnées |

Lecteurs non disponibles : SAS complet (les tables compressées de plus de 255 lignes ne peuvent pas être comparées à un fichier de SAS 9.4M7, inconnue W01).

## Matrice

Chaque cellule : `OK`, `KO` (cause), `KO CONNU` (limite documentée dans `20_ecriture.md`, hors critère de fin), `NON APPLICABLE` ou `NON FAISABLE` (raison) ; le journal SAS de chaque cas est `rea_output/evidence/write/<cas>_sas.log`. **Note 1 (`OK*`)** : `sas_small` ne sait pas charger les informats (`WARNING: The informat @DATE could not be loaded, probably due to insufficient memory`) ; le même avertissement apparait pour un fichier écrit par le SAS complet (`corpus/files/metadonnees/metadonnees_infmt_date9_no`, journal `rea_output/evidence/write_informat_oracle_ref.log`) : ce n'est pas un défaut du fichier produit.

| cas | description | SAS | pandas | pyreadstat | Parso | ref_reader | journal SAS |
|---|---|---|---|---|---|---|---|
| w01_minimal | 1 colonne num, 1 ligne | OK | OK | OK | OK | OK | `w01_minimal_sas.log` |
| w02_multicol | 2 num + 2 char, 100 lignes | OK | OK | OK | OK | OK | `w02_multicol_sas.log` |
| w03_num3 | colonne numerique de 3 octets | OK | OK | OK | OK | OK | `w03_num3_sas.log` |
| w03_num4 | colonne numerique de 4 octets | OK | OK | OK | OK | OK | `w03_num4_sas.log` |
| w03_num5 | colonne numerique de 5 octets | OK | OK | OK | OK | OK | `w03_num5_sas.log` |
| w03_num6 | colonne numerique de 6 octets | OK | OK | OK | OK | OK | `w03_num6_sas.log` |
| w03_num7 | colonne numerique de 7 octets | OK | OK | OK | OK | OK | `w03_num7_sas.log` |
| w03_num8 | colonne numerique de 8 octets | OK | OK | OK | OK | OK | `w03_num8_sas.log` |
| w04_missing | 28 manquants speciaux | OK | OK | OK | OK | OK | `w04_missing_sas.log` |
| w05_meta | labels, formats et informats | OK* | OK | OK | NON APPLICABLE : Parso rend les dates en java.util.Date | OK | `w05_meta_sas.log` |
| w05b_informat | informat DATE9 seul | OK* | OK | OK | NON APPLICABLE : Parso rend les dates en java.util.Date | OK | `w05b_informat_sas.log` |
| w05c_infmt_only_char | informat $CHAR seul | OK | OK | OK | OK | OK | `w05c_infmt_only_char_sas.log` |
| w06_names | nom de 32 octets et valeurs non ASCII | OK | OK | OK | OK | OK | `w06_names_sas.log` |
| w07_pages | 3000 lignes : page mixte puis page de donnees | OK | OK | OK | OK | OK | `w07_pages_sas.log` |
| w08_pages_buf | page de 4096 octets | OK | OK | OK | OK | OK | `w08_pages_buf_sas.log` |
| w09_manycols | 300 colonnes numeriques | OK | OK | OK | OK | OK | `w09_manycols_sas.log` |
| w10_zero | table a 0 ligne | OK | OK | OK | OK | OK | `w10_zero_sas.log` |
| w11_char_one | COMPRESS=CHAR, 1 ligne | OK | OK | OK | OK | OK | `w11_char_one_sas.log` |
| w11_char_small | COMPRESS=CHAR, 255 lignes compressibles (maximum relu par SAS) | OK | OK | OK | OK | OK | `w11_char_small_sas.log` |
| w11_char_256 | COMPRESS=CHAR, 256 lignes | OK | OK | OK | OK | OK | `w11_char_256_sas.log` |
| w11_char_1000 | COMPRESS=CHAR, 1000 lignes | OK | OK | OK | OK | OK | `w11_char_1000_sas.log` |
| w11_char_10000 | COMPRESS=CHAR, 10000 lignes sur plusieurs pages de 65536 octets | OK | OK | OK | OK | OK | `w11_char_10000_sas.log` |
| w11_char_70000 | COMPRESS=CHAR, 70000 lignes (plus de 65535 : cumul de la page marqueur sur 64 bits) | OK | OK | OK | OK | OK | `w11_char_70000_sas.log` |
| w11_char_pg4096 | COMPRESS=CHAR, 300 lignes, pages de 4096 octets | OK | OK | OK | OK | OK | `w11_char_pg4096_sas.log` |
| w11_char_noise | COMPRESS=CHAR, lignes peu compressibles (texte aleatoire) | OK | OK | OK | OK | OK | `w11_char_noise_sas.log` |
| w11_char_pages | COMPRESS=CHAR, 6000 lignes sur plusieurs pages | OK | OK | OK | OK | OK | `w11_char_pages_sas.log` |
| w11_char_zero | COMPRESS=CHAR, 0 ligne | OK | OK | OK | OK | OK | `w11_char_zero_sas.log` |
| w11_char_mini | COMPRESS=CHAR demande, ligne de 3 octets : table ordinaire | OK | OK | OK | OK | OK | `w11_char_mini_sas.log` |
| w11_char_len15 | COMPRESS=CHAR demande, ligne de 15 octets : table ordinaire | OK | OK | OK | OK | OK | `w11_char_len15_sas.log` |
| w11_char_len16 | COMPRESS=CHAR, ligne de 16 octets | OK | OK | OK | OK | OK | `w11_char_len16_sas.log` |
| w11_binary_one | COMPRESS=BINARY, 1 ligne | OK | OK | OK | OK | OK | `w11_binary_one_sas.log` |
| w11_binary_small | COMPRESS=BINARY, 255 lignes compressibles (maximum relu par SAS) | OK | OK | OK | OK | OK | `w11_binary_small_sas.log` |
| w11_binary_256 | COMPRESS=BINARY, 256 lignes | OK | OK | OK | OK | OK | `w11_binary_256_sas.log` |
| w11_binary_1000 | COMPRESS=BINARY, 1000 lignes | OK | OK | OK | OK | OK | `w11_binary_1000_sas.log` |
| w11_binary_10000 | COMPRESS=BINARY, 10000 lignes sur plusieurs pages de 65536 octets | OK | OK | OK | OK | OK | `w11_binary_10000_sas.log` |
| w11_binary_70000 | COMPRESS=BINARY, 70000 lignes (plus de 65535 : cumul de la page marqueur sur 64 bits) | OK | OK | OK | OK | OK | `w11_binary_70000_sas.log` |
| w11_binary_pg4096 | COMPRESS=BINARY, 300 lignes, pages de 4096 octets | OK | OK | OK | OK | OK | `w11_binary_pg4096_sas.log` |
| w11_binary_noise | COMPRESS=BINARY, lignes peu compressibles (texte aleatoire) | OK | OK | OK | OK | OK | `w11_binary_noise_sas.log` |
| w11_binary_pages | COMPRESS=BINARY, 6000 lignes sur plusieurs pages | OK | OK | OK | OK | OK | `w11_binary_pages_sas.log` |
| w11_binary_zero | COMPRESS=BINARY, 0 ligne | OK | OK | OK | OK | OK | `w11_binary_zero_sas.log` |
| w11_binary_mini | COMPRESS=BINARY demande, ligne de 3 octets : table ordinaire | OK | OK | OK | OK | OK | `w11_binary_mini_sas.log` |
| w11_binary_len15 | COMPRESS=BINARY demande, ligne de 15 octets : table ordinaire | OK | OK | OK | OK | OK | `w11_binary_len15_sas.log` |
| w11_binary_len16 | COMPRESS=BINARY, ligne de 16 octets | OK | OK | OK | OK | OK | `w11_binary_len16_sas.log` |
| w12_latin1 | encodage latin1 (code 29), nom, label et texte accentues | OK | OK | KO CONNU : pyreadstat 1.2.9 refuse le code d'encodage 29 (unsupported character set) ; le code 62 est accepte (20_ecriture.md 6.4) — ReadstatError: Fi | OK | OK | `w12_latin1_sas.log` |
| w12_wlatin1 | encodage wlatin1 (code 62), caracteres 0x80..0x9F | OK | OK | OK | OK | OK | `w12_wlatin1_sas.log` |
| w15_gt2gb | table de plus de 2 Go | NON FAISABLE : non faisable ici : l'ecrivain de reference garde toutes les lignes en memoire (plus de 65 000 lignes de 32 767 octets pour depasser 2 G | NON FAISABLE : non faisable ici : l'ecrivain de reference garde toutes les lignes en memoire (plus de 65 000 lignes de 32 767 octets pour depasser 2 G | NON FAISABLE : non faisable ici : l'ecrivain de reference garde toutes les lignes en memoire (plus de 65 000 lignes de 32 767 octets pour depasser 2 G | NON FAISABLE : non faisable ici : l'ecrivain de reference garde toutes les lignes en memoire (plus de 65 000 lignes de 32 767 octets pour depasser 2 G | NON FAISABLE : non faisable ici : l'ecrivain de reference garde toutes les lignes en memoire (plus de 65 000 lignes de 32 767 octets pour depasser 2 G | — |
| w13_page1024 | taille de page 1024 | NON FAISABLE : metadonnees (1728 octets de sous-en-tetes, 9 pointeurs) trop grandes pour la page 0 de 1024 octets : plusieurs pages de metadonnees non | NON FAISABLE : metadonnees (1728 octets de sous-en-tetes, 9 pointeurs) trop grandes pour la page 0 de 1024 octets : plusieurs pages de metadonnees non | NON FAISABLE : metadonnees (1728 octets de sous-en-tetes, 9 pointeurs) trop grandes pour la page 0 de 1024 octets : plusieurs pages de metadonnees non | NON FAISABLE : metadonnees (1728 octets de sous-en-tetes, 9 pointeurs) trop grandes pour la page 0 de 1024 octets : plusieurs pages de metadonnees non | NON FAISABLE : metadonnees (1728 octets de sous-en-tetes, 9 pointeurs) trop grandes pour la page 0 de 1024 octets : plusieurs pages de metadonnees non | — |
| w13_page8192 | taille de page 8192 | OK | OK | OK | OK | OK | `w13_page8192_sas.log` |
| w13_page131072 | taille de page 131072 | OK | OK | OK | OK | OK | `w13_page131072_sas.log` |
| w13_page1048576 | taille de page 1048576 | OK | OK | OK | OK | OK | `w13_page1048576_sas.log` |
| w13_page5000 | taille de page 5000 (pas une puissance de 2) | OK | OK | OK | OK | OK | `w13_page5000_sas.log` |
| w14_name33 | nom de colonne de 33 octets (au dela de la limite SAS) | KO CONNU : limite de 32 octets : SAS tronque le nom et signale ERROR (« contains more than 32 bytes ») — 5 ERROR/WARNING : WARNING: Some character dat | OK | OK | OK | OK | `w14_name33_sas.log` |
| w14_label256 | label de 256 octets (limite SAS) | OK | OK | OK | OK | OK | `w14_label256_sas.log` |
| w14_label257 | label de 257 octets (au dela de la limite) | KO CONNU : limite de 256 octets : SAS tronque le label et signale WARNING (donnees perdues au transcodage) — 3 ERROR/WARNING : WARNING: Some character | OK | OK | OK | OK | `w14_label257_sas.log` |
| w14_char32767 | colonne caractere de 32 767 octets (limite SAS) | OK | OK | OK | OK | OK | `w14_char32767_sas.log` |
| w14_char32768 | colonne caractere de 32 768 octets (au dela de la limite) | KO CONNU : limite de 32 767 octets : SAS refuse (insufficient memory) — 2 ERROR/WARNING : ERROR: The SAS System stopped processing this step because o | OK | KO CONNU : ReadStat refuse une colonne de 32 768 octets — ReadstatError: Invalid file, or file has unsupported features | OK | OK | `w14_char32768_sas.log` |
| w14_cols700 | 700 colonnes (metadonnees sur la page 0) | OK | OK | OK | OK | OK | `w14_cols700_sas.log` |
