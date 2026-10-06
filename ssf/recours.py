from dataclasses import dataclass

from openfisca_core.periods import ETERNITY
from openfisca_core.reforms import Reform
from openfisca_core.variables import Variable

from .legislation import attributs

PRESTATIONS = ("rsa", "ppa", "aide_logement", "asf")


@dataclass(frozen=True)
class Profil:
    nom: str
    non_recours: tuple[str, ...] = ()


PROFILS = (
    Profil("recours_rsa_ppa"),
    Profil("recours_rsa_seul", ("ppa",)),
    Profil("recours_ppa_seul", ("rsa",)),
    Profil("non_recours_rsa_ppa", ("rsa", "ppa")),
    Profil("non_recours_aide_logement", ("aide_logement",)),
    )


def indicateur(nom, entite):
    return type(
        f"recours_{nom}",
        (Variable,),
        {
            "value_type": bool,
            "default_value": True,
            "entity": entite,
            "definition_period": ETERNITY,
            "label": f"Recours à {nom}",
            },
        )


def percue(nom, variable):
    def formula(entite, period):
        return entite(f"{nom}_droit", period) * entite(f"recours_{nom}", period)

    return type(nom, (Variable,), {**attributs(variable, False), "formula": formula})


class Recours(Reform):
    name = "recours"

    def apply(self):
        for nom in PRESTATIONS:
            variable = self.variables[nom]
            self.add_variable(type(f"{nom}_droit", (Variable,), attributs(variable, True)))
            self.add_variable(indicateur(nom, attributs(variable, False)["entity"]))
            self.update_variable(percue(nom, variable))
