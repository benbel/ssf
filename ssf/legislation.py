from functools import cache

from openfisca_core.parameters import Parameter, ParameterScale
from openfisca_core.reforms import Reform
from openfisca_core.variables import Variable
from openfisca_france import FranceTaxBenefitSystem


@cache
def systeme_de_base():
    return FranceTaxBenefitSystem()


def attributs(variable, avec_formules):
    return {
        cle: valeur
        for cle, valeur in vars(type(variable)).items()
        if not cle.startswith("__") and (avec_formules or not cle.startswith("formula"))
        }


def feuilles(noeud):
    for enfant in noeud.get_descendants():
        if isinstance(enfant, Parameter):
            yield enfant
        if isinstance(enfant, ParameterScale):
            for tranche in enfant.brackets:
                yield from tranche.children.values()


def est_datee(variable):
    return list(variable.formulas.keys()) not in ([], ["0001-01-01"])


def par_defaut(variable):
    def formula(entite, period):
        return entite.filled_array(variable.default_value)

    return formula


def avec_formule(variable, formule):
    return type(variable.name, (Variable,), {**attributs(variable, False), "formula": formule})


def terminee(variable, date):
    return variable.end is not None and str(variable.end) < date


def formule_unique(variable, date):
    formule = variable.get_formula(date)
    if formule is None or terminee(variable, date):
        return avec_formule(variable, par_defaut(variable))
    return avec_formule(variable, formule)


PARAMETRES_PARCOURUS = ("prelevements_sociaux.",)
DEBUT_PRELEVEMENT_A_LA_SOURCE = "2019-01-01"
IMPOTS_SUR_LES_REVENUS = ("impot_revenu_restant_a_payer", "ppe")


def bareme_en_vigueur(bareme_ir, date):
    return bareme_ir == "en_vigueur" or (bareme_ir == "reel" and date < DEBUT_PRELEVEMENT_A_LA_SOURCE)


def valeur_figee(parametre, date, bareme_ir):
    if bareme_en_vigueur(bareme_ir, date) and parametre.name.startswith("impot_revenu."):
        un_an_avant = parametre(f"{int(date[:4]) - 1}{date[4:]}")
        if un_an_avant is not None:
            return un_an_avant
    return parametre(date)


def stationnaire(date, bareme_ir="reel"):
    def gele(parametres):
        for parametre in feuilles(parametres):
            valeur = valeur_figee(parametre, date, bareme_ir)
            if valeur is not None or parametre.name.startswith(PARAMETRES_PARCOURUS):
                parametre.update(start="1900-01-01", value=valeur)
        return parametres

    class Stationnaire(Reform):
        name = f"legislation_au_{date}_bareme_ir_{bareme_ir}"

        def apply(self):
            self.modify_parameters(modifier_function=gele)
            for variable in list(self.variables.values()):
                if est_datee(variable) or terminee(variable, date):
                    self.update_variable(formule_unique(variable, date))

    return Stationnaire


def annule(*noms):
    class Annulation(Reform):
        name = "annule_" + "_".join(noms)

        def apply(self):
            for nom in noms:
                self.update_variable(avec_formule(self.variables[nom], par_defaut(self.variables[nom])))

    return Annulation


def compose(*reformes):
    def applique(systeme):
        for reforme in reformes:
            systeme = reforme(systeme)
        return systeme

    return applique


def smic_annuel_brut(systeme, date):
    smic = systeme.parameters(date).marche_travail.salaire_minimum.smic
    return smic.smic_b_horaire * smic.nb_heures_travail_mensuel * 12


def plafond_securite_sociale_annuel(systeme, date):
    return systeme.parameters(date).prelevements_sociaux.pss.plafond_securite_sociale_mensuel * 12


def plafond_loyer(systeme, date, zone, adultes, personnes_a_charge):
    plafonds = (
        systeme.parameters(date)
        .prestations_sociales.aides_logement.allocations_logement.locatif.formule
        .l_plafonds_loyers.par_zone[zone]
        )
    if personnes_a_charge > 0:
        return plafonds.un_enfant + (personnes_a_charge - 1) * plafonds.majoration_par_enf_supp
    if adultes == 2:
        return plafonds.couples
    return plafonds.personnes_seules
