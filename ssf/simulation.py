import csv

import numpy as np
from openfisca_core.periods import DateUnit
from openfisca_core.simulation_builder import SimulationBuilder
from openfisca_france.model.base import Famille, FoyerFiscal

from .indices.series import revenus_passes_constants
from .legislation import DEBUT_PRELEVEMENT_A_LA_SOURCE, IMPOTS_SUR_LES_REVENUS, compose, smic_annuel_brut, stationnaire, systeme_de_base
from .menages import situation
from .recours import Recours
from .taxe_habitation import reformes_taxe_habitation

VARIABLES = (
    "salaire_de_base",
    "salaire_net",
    "csg_deductible_salaire",
    "csg_imposable_salaire",
    "crds_salaire",
    "impot_revenu_restant_a_payer",
    "ppe",
    "taxe_habitation",
    "rsa",
    "ppa_nette_crds",
    "aefa",
    "aide_logement",
    "af_nettes_crds",
    "cf_net_crds",
    "ars_nette_crds",
    "asf_nette_crds",
    "paje_nette_crds",
    "revenu_disponible",
    )

COMPOSANTES_REVENU_DISPONIBLE = (
    "salaire_net",
    "impot_revenu_restant_a_payer",
    "ppe",
    "taxe_habitation",
    "rsa",
    "ppa_nette_crds",
    "aefa",
    "aide_logement",
    "af_nettes_crds",
    "cf_net_crds",
    "ars_nette_crds",
    "asf_nette_crds",
    "paje_nette_crds",
    )

PREMIER = {"famille": Famille.DEMANDEUR, "foyer_fiscal": FoyerFiscal.DECLARANT_PRINCIPAL}


def systeme(date, reformes=(), bareme_ir="reel"):
    return compose(stationnaire(date, bareme_ir), *reformes_taxe_habitation(date), *reformes, Recours)(systeme_de_base())


def annee_de_l_impot(variable, date, bareme_ir):
    if bareme_ir == "reel" and date < DEBUT_PRELEVEMENT_A_LA_SOURCE and variable in IMPOTS_SUR_LES_REVENUS:
        return str(int(date[:4]) - 1)
    return date[:4]


def annuel(simulation, variable, date, bareme_ir):
    if simulation.tax_benefit_system.variables[variable].definition_period == DateUnit.MONTH:
        return 12 * simulation.calculate(variable, date[:7])
    return simulation.calculate(variable, annee_de_l_impot(variable, date, bareme_ir))


def par_menage(simulation, variable, valeurs):
    entite = simulation.tax_benefit_system.variables[variable].entity.key
    menages = simulation.populations["menage"]
    if entite == "menage":
        return valeurs
    if entite == "individu":
        return menages.sum(valeurs)
    premiers = simulation.populations["individu"].has_role(PREMIER[entite])
    return menages.sum(simulation.populations[entite].project(valeurs) * premiers)


def simule(population, date, parts_smic_max=6.0, points=601, reformes=(), variables=VARIABLES, revenus_passes=(1.0, 1.0, 1.0, 1.0), bareme_ir="reel"):
    systeme_date = systeme(date, reformes, bareme_ir)
    simulation = SimulationBuilder().build_from_entities(
        systeme_date,
        situation(population, date, systeme_date, parts_smic_max, points, revenus_passes),
        )
    return {
        variable: (
            par_menage(simulation, variable, annuel(simulation, variable, date, bareme_ir))
            .reshape(points, len(population))
            )
        for variable in variables
        }


def revenu_disponible(resultats):
    return sum(resultats[variable] for variable in COMPOSANTES_REVENU_DISPONIBLE)


def lignes(population, date, parts_smic_max, points, resultats):
    parts = np.linspace(0.0, parts_smic_max, points)
    for p, part in enumerate(parts):
        for i, (menage, profil) in enumerate(population):
            yield [date, menage.nom, profil.nom, round(float(part), 4)] + [
                round(float(valeurs[p, i]), 2) for valeurs in resultats.values()
                ]


def bruts(date, parts_smic_max, points):
    return np.linspace(0.0, parts_smic_max, points) * smic_annuel_brut(systeme_de_base(), date)


def ecrit(chemin, dates, population, parts_smic_max=6.0, points=601, reformes=(), variables=VARIABLES, revenus_passes=revenus_passes_constants, bareme_ir="reel"):
    with open(chemin, "w", newline="") as fichier:
        sortie = csv.writer(fichier)
        sortie.writerow(["date", "menage", "profil", "parts_smic"] + list(variables))
        for date in dates:
            resultats = simule(population, date, parts_smic_max, points, reformes, variables, revenus_passes(date), bareme_ir)
            sortie.writerows(lignes(population, date, parts_smic_max, points, resultats))
