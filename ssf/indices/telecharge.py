import csv
import io
import re
import urllib.request
from pathlib import Path

import openpyxl

DOSSIER = Path(__file__).resolve().parent
URL = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{}?startPeriod=2003"

SERIES = {
    "ipc_hors_tabac": "011814056",
    "salaire_net_moyen_eqtp_prive": "010752333",
    "indice_salaire_mensuel_base": "010562695",
    "irl": "001515333",
    }

SEUILS_PAUVRETE = "https://www.insee.fr/fr/statistiques/fichier/8731526/irsocerfs2023_IG_A.xlsx"

QUANTILES_SALAIRES = {
    0.10: "010752336",
    0.25: "010752339",
    0.50: "010752342",
    0.75: "010752345",
    0.90: "010752348",
    0.95: "010752351",
    0.99: "010752354",
    }


def observations(idbank):
    with urllib.request.urlopen(URL.format(idbank)) as reponse:
        texte = reponse.read().decode()
    return sorted(
        (periode, float(valeur))
        for periode, valeur in re.findall(r'TIME_PERIOD="([^"]+)" OBS_VALUE="([^"]+)"', texte)
        )


def classeur(url):
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(requete) as reponse:
        return openpyxl.load_workbook(io.BytesIO(reponse.read()), data_only=True).active


def medianes_niveau_de_vie(url=SEUILS_PAUVRETE):
    lignes = [list(ligne) for ligne in classeur(url).iter_rows(values_only=True)]
    entete = next(ligne for ligne in lignes if sum(str(cellule).startswith(("19", "20")) for cellule in ligne if cellule) >= 5)
    courants = next(i for i, ligne in enumerate(lignes) if ligne[0] and "courants" in str(ligne[0]))
    seuil_60 = next(ligne for ligne in lignes[courants:] if ligne[1] and "60" in str(ligne[1]))
    medianes = {}
    for colonne, valeur in zip(entete, seuil_60):
        if colonne and str(colonne)[:4].isdigit() and isinstance(valeur, (int, float)):
            medianes[int(str(colonne)[:4])] = round(valeur * 12 / 0.6)
    return sorted(medianes.items())


def ecrit(chemin, entete, lignes):
    with open(chemin, "w", newline="") as fichier:
        sortie = csv.writer(fichier)
        sortie.writerow(entete)
        sortie.writerows(lignes)


def main():
    ecrit(
        DOSSIER / "series_insee.csv",
        ["serie", "idbank", "periode", "valeur"],
        [
            [nom, idbank, periode, valeur]
            for nom, idbank in SERIES.items()
            for periode, valeur in observations(idbank)
            ],
        )
    ecrit(
        DOSSIER / "quantiles_salaires.csv",
        ["quantile", "idbank", "annee", "salaire_net_annuel_eqtp"],
        [
            [quantile, idbank, periode, valeur]
            for quantile, idbank in QUANTILES_SALAIRES.items()
            for periode, valeur in observations(idbank)
            ],
        )
    ecrit(
        DOSSIER / "niveau_de_vie_median.csv",
        ["annee", "mediane_annuelle_euros_courants", "source"],
        [[annee, mediane, SEUILS_PAUVRETE] for annee, mediane in medianes_niveau_de_vie()],
        )


if __name__ == "__main__":
    main()
