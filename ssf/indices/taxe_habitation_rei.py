import csv
import io
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import openfisca_france

DOSSIER = Path(__file__).resolve().parent
REI = Path(openfisca_france.__file__).resolve().parent / "assets" / "taxe_habitation"
COMPARATEUR = "https://www.insee.fr/fr/statistiques/fichier/2521169/comparateur_csv.zip"
ANNEES = range(2017, 2023)
ANNEE_RECENSEMENT = {2017: "2017", 2018: "2017", 2019: "2017", 2020: "2023", 2021: "2023", 2022: "2023"}
QUANTILES = (0.1, 0.5, 0.9)


def residences_principales():
    with urllib.request.urlopen(COMPARATEUR) as reponse:
        archive = zipfile.ZipFile(io.BytesIO(reponse.read()))
    resultat = {}
    with archive.open("comparateur.csv") as fichier:
        for ligne in csv.reader(io.TextIOWrapper(fichier, encoding="utf-8"), delimiter=";"):
            if ligne[1] == "COM" and ligne[5] == "DWELLINGS_OCS_DW_MAIN" and ligne[3] in ("2017", "2023") and ligne[6]:
                resultat[(ligne[3], ligne[2])] = float(ligne[6])
    return resultat


def nombre(valeur):
    return float(valeur) if valeur else 0.0


def commune(ligne):
    taux_com, taux_epci = nombre(ligne["taux_com"]), nombre(ligne["taux_epci"])
    taux = taux_com + taux_epci
    if taux <= 0:
        return None
    parts = {}
    for nom in ("abt_general_base", "abt_pac_1_2", "abt_pac_3pl"):
        partiel = 0.0
        for niveau, poids in (("com", taux_com), ("epci", taux_epci)):
            moyenne = nombre(ligne[f"valeur_locative_moyenne_{niveau}"]) or nombre(ligne["valeur_locative_moyenne_com"])
            if moyenne > 0:
                partiel += poids * nombre(ligne[f"{nom}_{niveau}"]) / moyenne
        parts[nom] = partiel / taux
    return taux, parts


def quantile_pondere(valeurs, poids, q):
    ordre = np.argsort(valeurs)
    cumul = np.cumsum(poids[ordre]) / poids.sum()
    return float(valeurs[ordre][np.searchsorted(cumul, q)])


def main():
    rp = residences_principales()
    lignes = []
    for annee in ANNEES:
        taux, poids, parts = [], [], {nom: [] for nom in ("abt_general_base", "abt_pac_1_2", "abt_pac_3pl")}
        with open(REI / f"parametres_th_{annee}.csv") as fichier:
            for ligne in csv.DictReader(fichier):
                poids_commune = rp.get((ANNEE_RECENSEMENT[annee], ligne["code_insee_commune"]))
                resultat = commune(ligne)
                if poids_commune and resultat:
                    taux.append(resultat[0])
                    poids.append(poids_commune)
                    for nom, valeur in resultat[1].items():
                        parts[nom].append(valeur)
        taux, poids = np.array(taux), np.array(poids)
        ligne = {"annee": annee, "communes": len(taux), "residences_principales": round(poids.sum()), "taux": round(float(np.average(taux, weights=poids)), 4)}
        for nom, valeurs in parts.items():
            valeurs = np.array(valeurs)
            ligne[nom] = round(float(np.average(valeurs, weights=poids)), 4)
            for q in QUANTILES:
                ligne[f"{nom}_q{int(q * 100)}"] = round(quantile_pondere(valeurs, poids, q), 4)
        lignes.append(ligne)
    with open(DOSSIER / "taxe_habitation_communes.csv", "w", newline="") as fichier:
        sortie = csv.DictWriter(fichier, fieldnames=list(lignes[0]))
        sortie.writeheader()
        sortie.writerows(lignes)


if __name__ == "__main__":
    main()
