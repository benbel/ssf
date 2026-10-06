from pathlib import Path

from openfisca_core.simulation_builder import SimulationBuilder

from .menages import Menage, situation
from .recours import PROFILS
from .simulation import VARIABLES, annuel, systeme

SORTIE = Path(__file__).resolve().parent.parent / "sortie"
DATES = tuple(f"{annee}-{mois}-01" for annee in range(2011, 2027) for mois in ("01", "07"))
PARTS_MAX = 6.0
POINTS = 25
MENAGES = (
    Menage("seul"),
    Menage("couple_0", 2),
    Menage("couple_3", 2, (1, 8, 15)),
    Menage("concubins_2", 2, (7, 9), vie_commune="concubinage"),
    Menage("monoparental_2", 1, (2, 9)),
    Menage("couple_etudiant", 2, (16, 22), etudiants=True),
    )
COMPLEMENTS = ("salaire_super_brut", "credit_impot_competitivite_emploi")


def decalage(source, cible):
    if source == cible:
        return "meme_periode"
    if source.stop < cible.start:
        return "anterieure"
    return "chevauchante"


def aretes(simulation):
    resultat = set()
    pile = list(simulation.tracer.trees)
    while pile:
        noeud = pile.pop()
        for enfant in noeud.children:
            resultat.add((enfant.name, noeud.name, "variable", decalage(enfant.period, noeud.period)))
            pile.append(enfant)
        for parametre in noeud.parameters:
            resultat.add((parametre.name, noeud.name, "parametre", ""))
    return resultat


def trace(date):
    systeme_date = systeme(date)
    population = [(menage, profil) for menage in MENAGES for profil in PROFILS]
    simulation = SimulationBuilder().build_from_entities(systeme_date, situation(population, date, systeme_date, PARTS_MAX, POINTS, (1.0, 1.0, 1.0, 1.0)))
    simulation.trace = True
    for variable in VARIABLES + COMPLEMENTS:
        annuel(simulation, variable, date, "reel")
    libelles = {nom: variable.label or "" for nom, variable in systeme_date.variables.items()}
    return aretes(simulation), libelles

