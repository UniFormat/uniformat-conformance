# Matrice d'écriture rejouée avec le driver (J6)

Fichiers produits par `uniformat_io.sas.write_sas` (cœur Rust) à partir des cas de `write_cases.py`, relus par le driver, pandas, pyreadstat (ReadStat), Parso et `ref_reader.py`. La colonne « octets » compare le fichier à celui de `ref_writer.py` (mêmes entrées, même code de fichier et même date). **SAS (`sas_small`) n'a pas été exécuté** : suite optionnelle, oracle Docker indisponible ici.

Cellules : `OK`, `KO`, `KO CONNU` (limite documentée : assertion négative), `REFUSÉ` (le driver refuse avant d'écrire : erreur typée, aucun fichier), `NON APPLICABLE`.

| cas | description | driver | pandas | pyreadstat | Parso | ref_reader | octets |
|---|---|---|---|---|---|---|---|
| w01_minimal | 1 colonne num, 1 ligne | OK | OK | OK | OK | OK | identique |
| w02_multicol | 2 num + 2 char, 100 lignes | OK | OK | OK | OK | OK | identique |
| w03_num3 | colonne numerique de 3 octets | OK | OK | OK | OK | OK | identique |
| w03_num4 | colonne numerique de 4 octets | OK | OK | OK | OK | OK | identique |
| w03_num5 | colonne numerique de 5 octets | OK | OK | OK | OK | OK | identique |
| w03_num6 | colonne numerique de 6 octets | OK | OK | OK | OK | OK | identique |
| w03_num7 | colonne numerique de 7 octets | OK | OK | OK | OK | OK | identique |
| w03_num8 | colonne numerique de 8 octets | OK | OK | OK | OK | OK | identique |
| w04_missing | 28 manquants speciaux | OK | OK | OK | OK | OK | identique |
| w05_meta | labels, formats et informats | OK | OK | OK | NON APPLICABLE | OK | identique |
| w05b_informat | informat DATE9 seul | OK | OK | OK | NON APPLICABLE | OK | identique |
| w05c_infmt_only_char | informat $CHAR seul | OK | OK | OK | OK | OK | identique |
| w06_names | nom de 32 octets et valeurs non ASCII | OK | OK | OK | OK | OK | identique |
| w07_pages | 3000 lignes : page mixte puis page de donnees | OK | OK | OK | OK | OK | identique |
| w08_pages_buf | page de 4096 octets | OK | OK | OK | OK | OK | identique |
| w09_manycols | 300 colonnes numeriques | OK | OK | OK | OK | OK | identique |
| w10_zero | table a 0 ligne | OK | OK | OK | OK | OK | identique |
| w11_char_one | COMPRESS=CHAR, 1 ligne | OK | OK | OK | OK | OK | identique |
| w11_char_small | COMPRESS=CHAR, 255 lignes compressibles (maximum relu par SAS) | OK | OK | OK | OK | OK | identique |
| w11_char_256 | COMPRESS=CHAR, 256 lignes | OK | OK | OK | OK | OK | identique |
| w11_char_1000 | COMPRESS=CHAR, 1000 lignes | OK | OK | OK | OK | OK | identique |
| w11_char_10000 | COMPRESS=CHAR, 10000 lignes sur plusieurs pages de 65536 octets | OK | OK | OK | OK | OK | identique |
| w11_char_70000 | COMPRESS=CHAR, 70000 lignes (plus de 65535 : cumul de la page marqueur sur 64 bits) | OK | OK | OK | OK | OK | identique |
| w11_char_pg4096 | COMPRESS=CHAR, 300 lignes, pages de 4096 octets | OK | OK | OK | OK | OK | identique |
| w11_char_noise | COMPRESS=CHAR, lignes peu compressibles (texte aleatoire) | OK | OK | OK | OK | OK | identique |
| w11_char_pages | COMPRESS=CHAR, 6000 lignes sur plusieurs pages | OK | OK | OK | OK | OK | identique |
| w11_char_zero | COMPRESS=CHAR, 0 ligne | OK | OK | OK | OK | OK | identique |
| w11_char_mini | COMPRESS=CHAR demande, ligne de 3 octets : table ordinaire | OK | OK | OK | OK | OK | identique |
| w11_char_len15 | COMPRESS=CHAR demande, ligne de 15 octets : table ordinaire | OK | OK | OK | OK | OK | identique |
| w11_char_len16 | COMPRESS=CHAR, ligne de 16 octets | OK | OK | OK | OK | OK | identique |
| w11_binary_one | COMPRESS=BINARY, 1 ligne | OK | OK | OK | OK | OK | identique |
| w11_binary_small | COMPRESS=BINARY, 255 lignes compressibles (maximum relu par SAS) | OK | OK | OK | OK | OK | identique |
| w11_binary_256 | COMPRESS=BINARY, 256 lignes | OK | OK | OK | OK | OK | identique |
| w11_binary_1000 | COMPRESS=BINARY, 1000 lignes | OK | OK | OK | OK | OK | identique |
| w11_binary_10000 | COMPRESS=BINARY, 10000 lignes sur plusieurs pages de 65536 octets | OK | OK | OK | OK | OK | identique |
| w11_binary_70000 | COMPRESS=BINARY, 70000 lignes (plus de 65535 : cumul de la page marqueur sur 64 bits) | OK | OK | OK | OK | OK | identique |
| w11_binary_pg4096 | COMPRESS=BINARY, 300 lignes, pages de 4096 octets | OK | OK | OK | OK | OK | identique |
| w11_binary_noise | COMPRESS=BINARY, lignes peu compressibles (texte aleatoire) | OK | OK | OK | OK | OK | identique |
| w11_binary_pages | COMPRESS=BINARY, 6000 lignes sur plusieurs pages | OK | OK | OK | OK | OK | identique |
| w11_binary_zero | COMPRESS=BINARY, 0 ligne | OK | OK | OK | OK | OK | identique |
| w11_binary_mini | COMPRESS=BINARY demande, ligne de 3 octets : table ordinaire | OK | OK | OK | OK | OK | identique |
| w11_binary_len15 | COMPRESS=BINARY demande, ligne de 15 octets : table ordinaire | OK | OK | OK | OK | OK | identique |
| w11_binary_len16 | COMPRESS=BINARY, ligne de 16 octets | OK | OK | OK | OK | OK | identique |
| w12_latin1 | encodage latin1 (code 29), nom, label et texte accentues | OK | OK | KO CONNU : pyreadstat 1.2.9 refuse le code d'encodage 29 (unsupported character set) ; le code 62 est | OK | OK | identique |
| w12_wlatin1 | encodage wlatin1 (code 62), caracteres 0x80..0x9F | OK | OK | OK | OK | OK | identique |
| w15_gt2gb | table de plus de 2 Go | NON FAISABLE | NON FAISABLE | NON FAISABLE | NON FAISABLE | NON FAISABLE | — |
| w13_page1024 | taille de page 1024 | OK | OK | OK | OK | OK | ref_writer renonce : metadonnees (1728 octets de sous-en-tetes, 9 pointeurs) trop |
| w13_page8192 | taille de page 8192 | OK | OK | OK | OK | OK | identique |
| w13_page131072 | taille de page 131072 | OK | OK | OK | OK | OK | identique |
| w13_page1048576 | taille de page 1048576 | OK | OK | OK | OK | OK | identique |
| w13_page5000 | taille de page 5000 (pas une puissance de 2) | OK | OK | OK | OK | OK | identique |
| w14_name33 | nom de colonne de 33 octets (au dela de la limite SAS) | REFUSÉ : SasWriteError : colonne "nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn" : nom de 33 octets (maximum 32) | REFUSÉ : SasWriteError : colonne "nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn" : nom de 33 octets (maximum 32) | REFUSÉ : SasWriteError : colonne "nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn" : nom de 33 octets (maximum 32) | REFUSÉ : SasWriteError : colonne "nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn" : nom de 33 octets (maximum 32) | REFUSÉ : SasWriteError : colonne "nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn" : nom de 33 octets (maximum 32) | — |
| w14_label256 | label de 256 octets (limite SAS) | OK | OK | OK | OK | OK | identique |
| w14_label257 | label de 257 octets (au dela de la limite) | REFUSÉ : SasWriteError : colonne "x" : label de 257 octets (maximum 256) | REFUSÉ : SasWriteError : colonne "x" : label de 257 octets (maximum 256) | REFUSÉ : SasWriteError : colonne "x" : label de 257 octets (maximum 256) | REFUSÉ : SasWriteError : colonne "x" : label de 257 octets (maximum 256) | REFUSÉ : SasWriteError : colonne "x" : label de 257 octets (maximum 256) | — |
| w14_char32767 | colonne caractere de 32 767 octets (limite SAS) | OK | OK | OK | OK | OK | identique |
| w14_char32768 | colonne caractere de 32 768 octets (au dela de la limite) | REFUSÉ : SasWriteError : colonne "c" : longueur caractère 32768 hors de 1 à 32767 | REFUSÉ : SasWriteError : colonne "c" : longueur caractère 32768 hors de 1 à 32767 | REFUSÉ : SasWriteError : colonne "c" : longueur caractère 32768 hors de 1 à 32767 | REFUSÉ : SasWriteError : colonne "c" : longueur caractère 32768 hors de 1 à 32767 | REFUSÉ : SasWriteError : colonne "c" : longueur caractère 32768 hors de 1 à 32767 | — |
| w14_cols700 | 700 colonnes (metadonnees sur la page 0) | OK | OK | OK | OK | OK | identique |
