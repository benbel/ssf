import csv
from functools import cache
from pathlib import Path

import numpy as np

DOSSIER = Path(__file__).resolve().parent


@cache
def series():
    resultat = {}
    with open(DOSSIER / "series_insee.csv") as fichier:
        for ligne in csv.DictReader(fichier):
            resultat.setdefault(ligne["serie"], {})[ligne["periode"]] = float(ligne["valeur"])
    return resultat


def sous_periode(periode):
    return periode[5:]


def annuel(observations):
    par_annee = {}
    for periode, valeur in observations.items():
        par_annee.setdefault(int(periode[:4]), {})[sous_periode(periode)] = valeur
    complet = max(len(valeurs) for valeurs in par_annee.values())
    resultat = {}
    for annee in sorted(par_annee):
        valeurs = par_annee[annee]
        if len(valeurs) == complet or annee - 1 not in resultat:
            resultat[annee] = float(np.mean(list(valeurs.values())))
        else:
            precedentes = [par_annee[annee - 1][cle] for cle in valeurs]
            resultat[annee] = resultat[annee - 1] * float(np.mean(list(valeurs.values())) / np.mean(precedentes))
    return resultat


def prolonge(base, relais):
    resultat = dict(base)
    for annee in sorted(relais):
        if annee - 1 in resultat and annee not in resultat:
            resultat[annee] = resultat[annee - 1] * relais[annee] / relais[annee - 1]
    return resultat


@cache
def salaire_moyen_annuel():
    return prolonge(
        annuel(series()["salaire_net_moyen_eqtp_prive"]),
        annuel(series()["indice_salaire_mensuel_base"]),
        )


def salaire_moyen(date):
    return salaire_moyen_annuel()[int(date[:4])]


def prix(date):
    return series()["ipc_hors_tabac"][date[:7]]


def trimestre(date):
    return f"{date[:4]}-Q{(int(date[5:7]) - 1) // 3 + 1}"


def irl(date):
    observations = series()["irl"]
    publies = [periode for periode in sorted(observations) if periode <= trimestre(date)]
    return observations[publies[-1]]


@cache
def medianes_niveau_de_vie():
    with open(DOSSIER / "niveau_de_vie_median.csv") as fichier:
        publiees = {int(ligne["annee"]): float(ligne["mediane_annuelle_euros_courants"]) for ligne in csv.DictReader(fichier)}
    return prolonge(publiees, salaire_moyen_annuel())


def niveau_de_vie_median(date):
    return medianes_niveau_de_vie()[int(date[:4])]


@cache
def quantiles_salaires_publies():
    resultat = {}
    with open(DOSSIER / "quantiles_salaires.csv") as fichier:
        for ligne in csv.DictReader(fichier):
            resultat.setdefault(int(ligne["annee"]), {})[float(ligne["quantile"])] = float(ligne["salaire_net_annuel_eqtp"])
    return resultat


def quantiles_salaires(annee):
    publies = quantiles_salaires_publies()
    derniere = min(annee, max(publies))
    echelle = salaire_moyen_annuel()[annee] / salaire_moyen_annuel()[derniere]
    return {p: valeur * echelle for p, valeur in sorted(publies[derniere].items())}


def revenus_passes_constants(date):
    return (1.0, 1.0, 1.0, 1.0)


def revenus_passes_salaire_moyen(date):
    annee = int(date[:4])
    return tuple(salaire_moyen_annuel()[annee - k] / salaire_moyen_annuel()[annee] for k in range(4))
