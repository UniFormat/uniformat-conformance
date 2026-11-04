#!/usr/bin/env python3
"""Controle de forme de rea_output/10_format_sas7bdat.md et 60_inconnues.md.

Usage : python3 -I rea_output/tools/check_spec.py fichier.md [...]
Verifie, pour chaque entree "#### nom" : presence des sept rubriques du modele de prompts/README.md
(Emplacement, Taille / type, Semantique, Valeurs observees, Ecriture, Preuve, Confiance), valeur de confiance
autorisee, et qu'aucune entree "confirme" ne manque de double preuve (fonction@adresse + preuve fichier).
Signale aussi tout pseudo-code (blocs ``` contenant "if "/"for "/"while ").
"""
import re
import sys

RUBRICS = ["Emplacement", "Taille / type", "Sémantique", "Valeurs observées", "Écriture", "Preuve", "Confiance"]
ALLOWED = ("confirmé", "inféré", "inconnu")


def main(paths):
    bad = 0
    for p in paths:
        text = open(p, encoding="utf-8").read()
        parts = re.split(r"(?m)^#### ", text)[1:]
        for part in parts:
            title, _, body = part.partition("\n")
            body = re.split(r"(?m)^#{1,3} |^---$", body)[0]
            missing = [r for r in RUBRICS if not re.search(rf"(?m)^- {re.escape(r)} ?:", body)]
            conf = re.search(r"(?m)^- Confiance ?: *(.*)$", body)
            if missing:
                bad += 1
                print(f"{p}: « {title.strip()} » : rubriques absentes : {', '.join(missing)}")
            if conf and not any(conf.group(1).strip().startswith(a) for a in ALLOWED):
                bad += 1
                print(f"{p}: « {title.strip()} » : confiance invalide : {conf.group(1)!r}")
            if conf and conf.group(1).strip().startswith("confirmé") and "@" not in body:
                bad += 1
                print(f"{p}: « {title.strip()} » : confirmé sans fonction@adresse")
        for blk in re.findall(r"```.*?```", text, flags=re.S):
            if re.search(r"\b(if|for|while)\b ", blk):
                bad += 1
                print(f"{p}: bloc de code suspect (pseudo-code ?)")
        print(f"{p}: {len(parts)} entrees")
    print(f"--- {bad} probleme(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
