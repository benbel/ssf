import csv
from functools import cache
from pathlib import Path

from openfisca_core.reforms import Reform
from openfisca_france.model.base import FoyerFiscal, Menage, max_, min_, where

from .legislation import avec_formule, systeme_de_base

DOSSIER = Path(__file__).resolve().parent / "indices"
DEBUT_PARAMETRES = "2017-01-01"
FIN_PLAFONNEMENT = "2020-01-01"
DEBUT_DEGREVEMENT = "2018-01-01"
FIN_DEGREVEMENT = "2023-01-01"
COMMUNES = {"moyenne": "", "q10": "_q10", "q50": "_q50", "q90": "_q90"}


@cache
def montants_moyens():
    with open(DOSSIER / "taxe_habitation.csv") as fichier:
        return {
            int(ligne["annee"]): (float(ligne["seul"]), float(ligne["couple"]))
            for ligne in csv.DictReader(fichier)
            }


@cache
def communes_moyennes():
    with open(DOSSIER / "taxe_habitation_communes.csv") as fichier:
        return {int(ligne["annee"]): {cle: float(valeur) for cle, valeur in ligne.items()} for ligne in csv.DictReader(fichier)}


def commune_moyenne(date, commune):
    annees = communes_moyennes()
    ligne = annees[min(max(int(date[:4]), min(annees)), max(annees))]
    suffixe = COMMUNES[commune]
    return {
        "taux": ligne["taux"],
        "general": ligne["abt_general_base"],
        "deux_premiers": ligne[f"abt_pac_1_2{suffixe}"],
        "suivants": ligne[f"abt_pac_3pl{suffixe}"],
        }


def frais_assiette():
    return systeme_de_base().parameters(DEBUT_PARAMETRES).taxe_habitation.frais_assiette


def montant_moyen(date):
    annees = montants_moyens()
    return annees[min(int(date[:4]), max(annees))]


def seuil_ir(annee_de_revenus):
    return systeme_de_base().parameters(f"{annee_de_revenus}-01-01").impot_revenu.bareme_ir_depuis_1945.bareme.thresholds[1]


def indexation(date):
    if date >= DEBUT_PARAMETRES:
        return 1.0
    return seuil_ir(int(date[:4]) - 1) / seuil_ir(int(DEBUT_PARAMETRES[:4]) - 1)


def parametres(date):
    return systeme_de_base().parameters(max(date, DEBUT_PARAMETRES)).taxe_habitation


def par_demi_parts(parts, base, premieres, nombre_premieres, suivantes):
    demi_parts = max_(2 * (parts - 1), 0)
    return base + premieres * min_(demi_parts, nombre_premieres) + suivantes * max_(demi_parts - nombre_premieres, 0)


def plafonne(montant, rfr, parts, date):
    if date >= FIN_PLAFONNEMENT:
        return montant
    plafonnement = parametres(date).plafonnement
    k = indexation(date)
    plafond = k * par_demi_parts(parts, plafonnement.plaf_rfr.premiere_part, plafonnement.plaf_rfr.premiere_demi_part_supp, 1, plafonnement.plaf_rfr.autres_demi_parts_supp)
    abattement = k * par_demi_parts(parts, plafonnement.abattement_rfr.premiere_part, plafonnement.abattement_rfr.quatre_premieres_demi_parts_supp, 4, plafonnement.abattement_rfr.autres_demi_parts_supp)
    plafonnee = min_(montant, max_(rfr - abattement, 0) * plafonnement.taux_plafonnement_revenu)
    return where(rfr <= plafond, plafonnee, montant)


def entrees_locales(couple, date, commune="moyenne"):
    seul, deux = montant_moyen(date)
    parametres_commune = commune_moyenne(date, commune)
    taux, general = parametres_commune["taux"], parametres_commune["general"]
    moyenne = deux / (taux * (1 + frais_assiette()) * (1 - general))
    brute = moyenne if couple else seul / (taux * (1 + frais_assiette())) + general * moyenne
    return {
        "valeur_locative_cadastrale_brute": brute,
        "valeur_locative_moyenne_th_commune": moyenne,
        "abt_general_base_th_commune": general * moyenne,
        "abt_pac_1_2_th_commune": parametres_commune["deux_premiers"] * moyenne,
        "abt_pac_3pl_th_commune": parametres_commune["suivants"] * moyenne,
        "taux_th_commune": taux,
        }


def taxe_habitation_moyenne(date):
    def formula(menage, period):
        declarants = menage.members.has_role(FoyerFiscal.DECLARANT_PRINCIPAL)
        rfr = menage.sum(menage.members.foyer_fiscal("rfr", period.last_year) * declarants)
        parts = menage.sum(menage.members.foyer_fiscal("nbptr", period.last_year) * declarants)
        enfants = menage.nb_persons(Menage.ENFANT)
        abattements = (
            menage("abt_general_base_th_commune", period)
            + menage("abt_pac_1_2_th_commune", period) * min_(enfants, 2)
            + menage("abt_pac_3pl_th_commune", period) * max_(enfants - 2, 0)
            )
        base = max_(menage("valeur_locative_cadastrale_brute", period) - abattements, 0)
        montant = base * menage("taux_th_commune", period) * (1 + frais_assiette())
        return -plafonne(montant, rfr, parts, date)

    class TaxeHabitationMoyenne(Reform):
        name = f"taxe_habitation_moyenne_{date}"

        def apply(self):
            self.update_variable(avec_formule(self.variables["taxe_habitation"], formula))

    return TaxeHabitationMoyenne


def reformes_taxe_habitation(date):
    if date < DEBUT_PARAMETRES:
        return (taxe_habitation_moyenne(date),)
    return ()
