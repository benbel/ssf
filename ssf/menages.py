from dataclasses import dataclass

from .legislation import plafond_loyer, smic_annuel_brut
from .taxe_habitation import entrees_locales

ANNEES_DE_REVENUS = 4
AGES_ADULTES = (35, 37)
MODES_DE_RECOUVREMENT = (
    "allegement_general_mode_recouvrement",
    "allegement_cotisation_allocations_familiales_mode_recouvrement",
    "allegement_cotisation_maladie_mode_recouvrement",
    )
EMPLOYEUR = {
    "effectif_entreprise": 100,
    "taux_accident_travail": 0.0212,
    "taux_versement_transport": 0.01,
    }


@dataclass(frozen=True)
class Menage:
    nom: str
    adultes: int = 1
    enfants: tuple[int, ...] = ()
    vie_commune: str = "marie"
    salaire_second: float = 1.0
    zone: str = "zone_2"
    locataire: bool = True
    commune_th: str = "moyenne"
    etudiants: bool = False
    parent_fiscal: int = 0
    case_t: bool = True
    loyer_relatif: float = 1.0


def annees(date):
    return [int(date[:4]) - k for k in range(ANNEES_DE_REVENUS)]


def facteur(annee, date, revenus_passes):
    return revenus_passes[int(date[:4]) - annee]


def statut_marital(menage):
    if menage.adultes == 1 or menage.vie_commune == "concubinage":
        return "celibataire"
    return menage.vie_commune


def foyers_fiscaux(menage, adultes, enfants, date):
    if menage.adultes == 2 and menage.vie_commune == "concubinage":
        return [
            {"declarants": [adulte], "personnes_a_charge": enfants if k == menage.parent_fiscal else []}
            for k, adulte in enumerate(adultes)
            ]
    if menage.adultes == 1 and enfants and menage.case_t:
        return [{"declarants": adultes, "personnes_a_charge": enfants, "caseT": {str(a): True for a in annees(date)}}]
    return [{"declarants": adultes, "personnes_a_charge": enfants}]


def logement(menage, date, systeme):
    if not menage.locataire:
        return {"statut_occupation_logement": "proprietaire"}
    loyer = plafond_loyer(systeme, date, menage.zone, menage.adultes, len(menage.enfants))
    return {
        "statut_occupation_logement": "locataire_vide",
        "zone_apl": menage.zone,
        "loyer": 12 * loyer * menage.loyer_relatif,
        }


def ajoute(situation, i, menage, profil, date, systeme, revenus_passes):
    adultes = [f"adulte{k}_{i}" for k in range(menage.adultes)]
    enfants = [f"enfant{k}_{i}" for k in range(len(menage.enfants))]
    salaires = [0.0, menage.salaire_second * smic_annuel_brut(systeme, date)]
    for nom, age, salaire in zip(adultes, AGES_ADULTES, salaires):
        situation["individus"][nom] = {
            "date_naissance": {"ETERNITY": f"{annees(date)[0] - age}-01-01"},
            "salaire_de_base": {str(a): salaire * facteur(a, date, revenus_passes) for a in annees(date)},
            "statut_marital": {str(a): statut_marital(menage) for a in annees(date)},
            "aide_logement_condition_neutralisation": {str(a): False for a in annees(date)},
            "aide_logement_base_ressources_eval_forfaitaire": {str(a): 0.0 for a in annees(date)},
            **{mode: {str(a): "anticipe" for a in annees(date)} for mode in MODES_DE_RECOUVREMENT},
            **{cle: {str(a): valeur for a in annees(date)} for cle, valeur in EMPLOYEUR.items()},
            }
    for nom, age in zip(enfants, menage.enfants):
        situation["individus"][nom] = {"date_naissance": {"ETERNITY": f"{annees(date)[0] - age}-01-01"}}
        if menage.etudiants and age > 20:
            situation["individus"][nom]["etudiant"] = {str(a): True for a in annees(date)}
    situation["familles"][f"famille_{i}"] = {
        "parents": adultes,
        "enfants": enfants,
        **{f"recours_{nom}": {"ETERNITY": False} for nom in profil.non_recours},
        }
    for k, foyer in enumerate(foyers_fiscaux(menage, adultes, enfants, date)):
        situation["foyers_fiscaux"][f"foyer{k}_{i}"] = foyer
    situation["menages"][f"menage_{i}"] = {
        "personne_de_reference": adultes[:1],
        "conjoint": adultes[1:],
        "enfants": enfants,
        **{cle: {str(a): valeur for a in annees(date)} for cle, valeur in logement(menage, date, systeme).items()},
        **{cle: {str(a): valeur for a in annees(date) + [2000]} for cle, valeur in entrees_locales(menage.adultes == 2, date, menage.commune_th).items()},
        }


def axes(population, date, systeme, parts_smic_max, points, revenus_passes):
    debuts = [0]
    for menage, _ in population:
        debuts.append(debuts[-1] + menage.adultes + len(menage.enfants))
    maximum = parts_smic_max * smic_annuel_brut(systeme, date)
    return [
        {
            "name": "salaire_de_base",
            "count": points,
            "min": 0.0,
            "max": maximum * facteur(a, date, revenus_passes),
            "index": debut,
            "period": str(a),
            }
        for debut in debuts[:-1]
        for a in annees(date)
        ]


def situation(population, date, systeme, parts_smic_max, points, revenus_passes):
    resultat = {"individus": {}, "familles": {}, "foyers_fiscaux": {}, "menages": {}}
    for i, (menage, profil) in enumerate(population):
        ajoute(resultat, i, menage, profil, date, systeme, revenus_passes)
    resultat["axes"] = [axes(population, date, systeme, parts_smic_max, points, revenus_passes)]
    return resultat
