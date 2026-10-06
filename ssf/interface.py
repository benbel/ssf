import json
import sys
from textwrap import wrap

import networkx as nx

from .legislation import systeme_de_base
from .trace import DATES, SORTIE, trace

RACINE = "revenu_disponible"
EXPLORATEUR = "https://legislation.fr.openfisca.org/"
MOIS = {"01": "janvier", "07": "juillet"}
CARACTERE = 9.1
ECART = 70
ESPACE = 10
LIGNE_NOM = 21
LIGNE_LIBELLE = 17
LARGEUR_LIBELLE = 40
CARACTERE_LIBELLE = 7.9
BALAYAGES = 8
LIGNES = 36
MARGE = 60
ECART_BLOCS = 400
ECART_COLONNES = 900
PROPORTION = 1.6
LARGEUR_SANS_REPLI = 2400
BLOCS = (
    ("Caractéristiques du ménage", 0, ("caracteristiques_socio_demographiques",)),
    ("Revenus d'activité", 0, ("revenus/activite",)),
    ("Revenus du capital", 0, ("revenus/capital",)),
    ("Revenus de remplacement et autres revenus", 0, ("revenus/remplacement", "revenus/autres")),
    ("Cotisations et contributions sociales", 1, ("prelevements_obligatoires/prelevements_sociaux",)),
    ("Impôt sur le revenu", 1, ("prelevements_obligatoires/impot_revenu",)),
    ("Impôt sur la fortune", 1, ("prelevements_obligatoires/isf",)),
    ("Minima sociaux et prime d'activité", 2, ("prestations/minima_sociaux", "rsa", "ppa")),
    ("Prestations familiales", 2, ("prestations/prestations_familiales", "asf")),
    ("Aides au logement", 2, ("prestations/aides_logement", "prestations/reduction_loyer_solidarite", "aide_logement")),
    ("Autres prestations", 2, ("prestations", "covid19")),
    ("Agrégats", 3, ("mesures",)),
    )

MODELE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITRE__</title>
<style>
body { margin: 1.5rem 2rem; line-height: 1.6; font-size: 16px; background-color: #fcfcfc; color: #111111; font-family: monospace; }
header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.3em 2em; }
h1 { font-size: 1.3em; margin: 0; }
header p { margin: 0; }
#detail { max-width: 45em; }
a { color: #111111; text-decoration: none; cursor: pointer; border-bottom: 1px solid #286c44; }
a.externe { border-bottom: 0; }
a.externe::after { content: "⟡"; color: #286c44; font-size: 10px; vertical-align: super; }
input { font: inherit; background: transparent; border: 0; border-bottom: 1px solid #bbbbbb; width: 26em; max-width: 100%; }
ul { list-style: none; padding-left: 1em; }
li { margin-bottom: 0.3em; }
li::before { content: "› "; margin-left: -1em; }
#cadre { position: relative; overflow: hidden; margin: 0.8em 0 1.5em; width: 100%; height: calc(100vh - 6.5rem); cursor: grab; touch-action: none; }
#cadre.glisse { cursor: grabbing; }
#carte { position: absolute; left: 0; top: 0; width: 100%; height: 100%; transform-origin: 0 0; }
@media (max-width: 60em) { body { margin: 1rem; } }
</style>
</head>
<body>
<header>
<h1>__TITRE__</h1>
<p>Reproduit d'après <a class="externe" href="https://github.com/openfisca/openfisca-france">openfisca-france</a></p>
<p><input id="recherche" list="noms" placeholder="rechercher une variable"><datalist id="noms"></datalist></p>
</header>
<div id="cadre"><canvas id="carte"></canvas></div>
<div id="detail"></div>
<script>
const D = __DONNEES__;
const toile = document.getElementById("carte");
const zone = document.getElementById("cadre");
const ctx = toile.getContext("2d");
const indice = {}, entrees = D.noeuds.map(() => []), sorties = D.noeuds.map(() => []);
D.noeuds.forEach(([nom], i) => { indice[nom] = i; });
D.aretes.forEach(([s, c], k) => { sorties[s].push(k); entrees[c].push(k); });
Object.keys(indice).sort().forEach(n => document.getElementById("noms").append(new Option(n)));

const CASE = 1500, LARGEUR_CARTE = 4096;

function ajouteArete(chemin, k) {
  const [s, c] = D.aretes[k];
  const [, xs, ys, ls] = D.noeuds[s], [, xc, yc] = D.noeuds[c];
  const x1 = xs + ls, milieu = (x1 + xc) / 2;
  chemin.moveTo(x1, ys);
  chemin.bezierCurveTo(milieu, ys, milieu, yc, xc, yc);
}
function ajouteNoeud(chemin, i) {
  const [, x, y, l, , , h] = D.noeuds[i];
  chemin.rect(x, y - h / 2, l, h);
}

const cases = new Map();
function caseDe(x, y) {
  const cle = Math.floor(x / CASE) + "," + Math.floor(y / CASE);
  if (!cases.has(cle)) cases.set(cle, { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity, internes: new Path2D(), entre: new Path2D(), noeuds: new Path2D() });
  return cases.get(cle);
}
function etend(g, x0, y0, x1, y1) {
  g.x0 = Math.min(g.x0, x0); g.y0 = Math.min(g.y0, y0); g.x1 = Math.max(g.x1, x1); g.y1 = Math.max(g.y1, y1);
}
D.aretes.forEach(([s, c, , autre], k) => {
  const a = D.noeuds[s], b = D.noeuds[c];
  const x0 = Math.min(a[1] + a[3], b[1]), x1 = Math.max(a[1] + a[3], b[1]), y0 = Math.min(a[2], b[2]), y1 = Math.max(a[2], b[2]);
  const g = caseDe((x0 + x1) / 2, (y0 + y1) / 2);
  ajouteArete(autre ? g.entre : g.internes, k);
  etend(g, x0, y0, x1, y1);
});
D.noeuds.forEach(([, x, y, l, , , h], i) => {
  const g = caseDe(x + l / 2, y);
  ajouteNoeud(g.noeuds, i);
  etend(g, x, y - h / 2, x + l, y + h / 2);
});
const cadres = new Path2D();
D.blocs.forEach(([, x, y, l, h]) => cadres.rect(x, y, l, h));

const [EX, EY, EL, EH] = D.etendue;
const carte = document.createElement("canvas"), echelleCarte = LARGEUR_CARTE / EL;
carte.width = LARGEUR_CARTE;
carte.height = Math.ceil(EH * echelleCarte);
let echelle = 1, tx = 0, ty = 0, rendu = null, attente = null;
let choisi = null, voisins = new Set(), noeudsChoisis = new Path2D();
let directes = new Path2D(), directesAnterieures = new Path2D(), indirectes = new Path2D(), indirectesAnterieures = new Path2D();

function ratio() { return window.devicePixelRatio || 1; }
function rend() {
  clearTimeout(attente);
  const r = ratio();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, toile.width, toile.height);
  if (echelle * r <= echelleCarte * 1.5) {
    const k = r * echelle / echelleCarte;
    ctx.setTransform(k, 0, 0, k, r * (EX * echelle + tx), r * (EY * echelle + ty));
    ctx.drawImage(carte, 0, 0);
  } else {
    ctx.setTransform(r * echelle, 0, 0, r * echelle, r * tx, r * ty);
    dessine(ctx, echelle, { x0: -tx / echelle, y0: -ty / echelle, x1: (zone.clientWidth - tx) / echelle, y1: (zone.clientHeight - ty) / echelle });
  }
  rendu = { echelle, tx, ty };
  toile.style.transform = "";
}
function bouge() {
  const k = echelle / rendu.echelle;
  toile.style.transform = `translate(${tx - k * rendu.tx}px, ${ty - k * rendu.ty}px) scale(${k})`;
  clearTimeout(attente);
  attente = setTimeout(rend, 200);
}
function rendCarte() {
  const c = carte.getContext("2d");
  c.setTransform(1, 0, 0, 1, 0, 0);
  c.clearRect(0, 0, carte.width, carte.height);
  c.setTransform(echelleCarte, 0, 0, echelleCarte, -EX * echelleCarte, -EY * echelleCarte);
  dessine(c, echelleCarte, null);
}
function dimensionne() {
  const r = ratio();
  toile.width = zone.clientWidth * r;
  toile.height = zone.clientHeight * r;
  rend();
}
function ensemble() {
  echelle = Math.min(zone.clientWidth / EL, zone.clientHeight / EH);
  tx = (zone.clientWidth - EL * echelle) / 2 - EX * echelle;
  ty = (zone.clientHeight - EH * echelle) / 2 - EY * echelle;
  rend();
}
function centre(i) {
  const [, x, y, l] = D.noeuds[i];
  echelle = 1;
  tx = zone.clientWidth / 2 - (x + l / 2);
  ty = zone.clientHeight / 2 - y;
}
function trait(c, e, chemin, couleur, largeur, pointilles) {
  c.strokeStyle = couleur;
  c.lineWidth = largeur / e;
  c.setLineDash(pointilles ? [4 / e, 3 / e] : []);
  c.stroke(chemin);
}
function dessine(c, e, vue) {
  const focus = choisi !== null;
  const visibles = [...cases.values()].filter(g => !vue || (g.x1 >= vue.x0 && g.x0 <= vue.x1 && g.y1 >= vue.y0 && g.y0 <= vue.y1));
  trait(c, e, cadres, "#dddddd", 1, false);
  c.fillStyle = "#111111";
  c.font = "150px monospace";
  D.blocs.forEach(([titre, x, y]) => c.fillText(titre, x, y - 50));
  visibles.forEach(g => trait(c, e, g.entre, focus ? "#f3f3f3" : "#ebebeb", 0.5, false));
  visibles.forEach(g => trait(c, e, g.internes, focus ? "#ededed" : "#b5b5b5", 0.6, false));
  c.fillStyle = "#fcfcfc";
  visibles.forEach(g => { c.fill(g.noeuds); trait(c, e, g.noeuds, focus ? "#ececec" : "#bbbbbb", 1, false); });
  if (focus) {
    trait(c, e, indirectes, "#9cc8ac", 1, false);
    trait(c, e, indirectesAnterieures, "#9cc8ac", 1, true);
    trait(c, e, directes, "#1f5a37", 1.6, false);
    trait(c, e, directesAnterieures, "#1f5a37", 1.6, true);
    c.fillStyle = "#fcfcfc";
    c.fill(noeudsChoisis);
    trait(c, e, noeudsChoisis, "#bbbbbb", 1, false);
    const [, x, y, l, , , h] = D.noeuds[choisi];
    trait(c, e, new Path2D(`M${x},${y - h / 2}h${l}v${h}h${-l}z`), "#286c44", 2, false);
  }
  if (!vue || e * 15 < 5) return;
  c.fillStyle = "#111111";
  D.noeuds.forEach(([nom, x, y, l, , lignes, h]) => {
    if (x + l < vue.x0 || x > vue.x1 || y + h < vue.y0 || y - h > vue.y1) return;
    const haut = y - h / 2;
    c.font = "15px monospace";
    c.fillText(nom, x + 7, haut + 20);
    c.font = "13px monospace";
    lignes.forEach((ligne, k) => c.fillText(ligne, x + 7, haut + 37 + 17 * k));
  });
}

function sous(e) {
  const boite = zone.getBoundingClientRect();
  const x = (e.clientX - boite.left - tx) / echelle, y = (e.clientY - boite.top - ty) / echelle;
  return D.noeuds.findIndex(([, nx, ny, l, , , h]) => x >= nx && x <= nx + l && Math.abs(y - ny) <= h / 2);
}

let cumul = 0;
function niveaux() {
  const base = Math.min(zone.clientWidth / EL, zone.clientHeight / EH), liste = [];
  for (let e = base; e < 2.5; e *= 2) liste.push(e);
  return liste;
}
zone.addEventListener("wheel", e => {
  e.preventDefault();
  cumul += e.deltaMode ? e.deltaY * 40 : e.deltaY;
  if (Math.abs(cumul) < 60) return;
  const sens = cumul < 0 ? 1 : -1;
  cumul = 0;
  const liste = niveaux();
  const actuel = liste.reduce((meilleur, n, k) => Math.abs(Math.log(n / echelle)) < Math.abs(Math.log(liste[meilleur] / echelle)) ? k : meilleur, 0);
  const cible = liste[Math.min(liste.length - 1, Math.max(0, actuel + sens))];
  if (cible === echelle) return;
  const boite = zone.getBoundingClientRect();
  const px = e.clientX - boite.left, py = e.clientY - boite.top;
  const facteur = cible / echelle;
  tx = px - (px - tx) * facteur;
  ty = py - (py - ty) * facteur;
  echelle = cible;
  bouge();
}, { passive: false });

let depart = null, deplace = false, survole = -1;
zone.addEventListener("pointerdown", e => { depart = { x: e.clientX, y: e.clientY, tx, ty }; deplace = false; });
window.addEventListener("pointermove", e => {
  if (depart) {
    const dx = e.clientX - depart.x, dy = e.clientY - depart.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) { deplace = true; zone.classList.add("glisse"); }
    tx = depart.tx + dx;
    ty = depart.ty + dy;
    bouge();
  } else if (zone.contains(e.target)) {
    const i = sous(e);
    if (i === survole) return;
    survole = i;
    zone.style.cursor = i >= 0 ? "pointer" : "";
    zone.title = i >= 0 ? D.noeuds[i][4] || D.noeuds[i][0] : "";
  }
});
window.addEventListener("pointerup", e => {
  if (depart && !deplace && zone.contains(e.target)) {
    const i = sous(e);
    if (i >= 0) choisit(i, false);
  }
  depart = null;
  zone.classList.remove("glisse");
});
window.addEventListener("keydown", e => {
  if (e.key === "Escape") { choisi = null; document.getElementById("detail").innerHTML = ""; rendCarte(); ensemble(); }
});
window.addEventListener("resize", dimensionne);

function lien(nom) {
  const a = document.createElement("a");
  a.textContent = nom;
  a.addEventListener("click", () => choisit(indice[nom], true));
  return a;
}
function lienExterne(nom, texte) {
  const a = document.createElement("a");
  a.className = "externe";
  a.href = D.explorateur + nom;
  a.target = "_blank";
  a.textContent = texte;
  return a;
}
function liste(titre, noms, fabrique) {
  const bloc = document.createElement("div");
  if (!noms.length) return bloc;
  const p = document.createElement("p");
  p.textContent = titre + " (" + noms.length + ") :";
  const ul = document.createElement("ul");
  noms.forEach(n => { const li = document.createElement("li"); li.append(fabrique(n)); ul.append(li); });
  bloc.append(p, ul);
  return bloc;
}
function choisit(i, recentre) {
  choisi = i;
  const directs = new Set(entrees[i].concat(sorties[i]));
  const lies = new Set(directs);
  [[entrees, 0], [sorties, 1]].forEach(([sens, bout]) => {
    const pile = [i], vus = new Set([i]);
    while (pile.length) {
      sens[pile.pop()].forEach(k => {
        lies.add(k);
        const suivant = D.aretes[k][bout];
        if (!vus.has(suivant)) { vus.add(suivant); pile.push(suivant); }
      });
    }
  });
  voisins = new Set([i]);
  noeudsChoisis = new Path2D();
  directes = new Path2D(); directesAnterieures = new Path2D(); indirectes = new Path2D(); indirectesAnterieures = new Path2D();
  lies.forEach(k => {
    const [s, c, anterieure] = D.aretes[k];
    voisins.add(s);
    voisins.add(c);
    ajouteArete(directs.has(k) ? (anterieure ? directesAnterieures : directes) : (anterieure ? indirectesAnterieures : indirectes), k);
  });
  voisins.forEach(v => ajouteNoeud(noeudsChoisis, v));
  if (recentre) centre(i);
  rendCarte();
  rend();
  const nom = D.noeuds[i][0];
  const detail = document.getElementById("detail");
  detail.innerHTML = "";
  const titre = document.createElement("p");
  titre.innerHTML = "<b></b> <span></span> ";
  titre.querySelector("b").textContent = nom;
  titre.querySelector("span").textContent = D.noeuds[i][4];
  titre.append(lienExterne(nom, "formule"));
  detail.append(titre);
  detail.append(liste("entrées", entrees[i].map(k => D.noeuds[D.aretes[k][0]][0]), lien));
  detail.append(liste("utilisée par", sorties[i].map(k => D.noeuds[D.aretes[k][1]][0]), lien));
  detail.append(liste("paramètres lus", D.parametres[nom] || [], p => lienExterne(p, p)));
}

document.getElementById("recherche").addEventListener("change", e => { if (e.target.value in indice) choisit(indice[e.target.value], true); });
rendCarte();
dimensionne();
ensemble();
</script>
</body>
</html>
"""


def graphe(aretes):
    complet = nx.DiGraph()
    parametres = {}
    for source, cible, nature, decalage in sorted(aretes):
        if nature == "variable":
            complet.add_edge(source, cible, anterieure=decalage == "anterieure")
        else:
            parametres.setdefault(cible, set()).add(source)
    noms = nx.ancestors(complet, RACINE) | {RACINE}
    return complet.subgraph(noms).copy(), parametres


def chemin(nom, variables):
    variable = variables.get(nom)
    if variable is None:
        return nom.replace("recours_", "").replace("_droit", "")
    fichier = getattr(sys.modules.get(type(variable).__module__), "__file__", "") or ""
    return fichier.replace("\\", "/").split("/model/")[-1]


def bloc(nom, variables):
    lieu = chemin(nom, variables)
    for titre, _, prefixes in BLOCS:
        if lieu.startswith(prefixes):
            return titre
    return "Agrégats"


def couches(g):
    couche = {}
    for nom in reversed(list(nx.topological_sort(g))):
        couche[nom] = 1 + max((couche[c] for c in g.successors(nom)), default=-1)
    return couche


def barycentre(noms, voisins, position):
    def cle(nom):
        rangs = [position[voisin] for voisin in voisins(nom)]
        return sum(rangs) / len(rangs) if rangs else position[nom]
    return sorted(noms, key=cle)


def ordonne(g, couche):
    rangs = {}
    for nom in sorted(g):
        rangs.setdefault(couche[nom], []).append(nom)
    position = {}
    for noms in rangs.values():
        position.update({nom: k - (len(noms) - 1) / 2 for k, nom in enumerate(noms)})
    for balayage in range(BALAYAGES):
        vers_la_gauche = balayage % 2 == 0
        ordre = sorted(rangs, reverse=not vers_la_gauche)[1:]
        voisins = g.successors if vers_la_gauche else g.predecessors
        for c in ordre:
            rangs[c] = barycentre(rangs[c], voisins, position)
            position.update({nom: k - (len(rangs[c]) - 1) / 2 for k, nom in enumerate(rangs[c])})
    return rangs


def lignes(nom, libelles):
    return wrap(libelles.get(nom, ""), LARGEUR_LIBELLE)


def largeur_noeud(nom, libelles):
    return 16 + max([CARACTERE * len(nom)] + [CARACTERE_LIBELLE * len(ligne) for ligne in lignes(nom, libelles)])


def hauteur_noeud(nom, libelles):
    return 8 + LIGNE_NOM + LIGNE_LIBELLE * len(lignes(nom, libelles))


def disposition_bloc(g, noms, libelles):
    sous = nx.DiGraph([(s, c) for s, c, anterieure in g.subgraph(noms).edges(data="anterieure") if not anterieure])
    sous.add_nodes_from(noms)
    rangs = ordonne(sous, couches(sous))
    colonnes = [rangs[c][k:k + LIGNES] for c in sorted(rangs, reverse=True) for k in range(0, len(rangs[c]), LIGNES)]
    largeurs = [max(largeur_noeud(nom, libelles) for nom in colonne) for colonne in colonnes]
    hauteurs = [sum(hauteur_noeud(nom, libelles) + ESPACE for nom in colonne) - ESPACE for colonne in colonnes]
    hauteur_rangee = max(hauteurs)
    surface = sum(l + ECART for l in largeurs) * (hauteur_rangee + ECART)
    limite = max(max(largeurs), LARGEUR_SANS_REPLI, (surface * PROPORTION) ** 0.5)
    place, x, y, largeur = {}, MARGE, MARGE, 0.0
    for colonne, l, h in zip(colonnes, largeurs, hauteurs):
        if x > MARGE and x + l > MARGE + limite:
            x, y = MARGE, y + hauteur_rangee + ECART
        haut = y + (hauteur_rangee - h) / 2
        for nom in colonne:
            hauteur = hauteur_noeud(nom, libelles)
            place[nom] = (x, haut + hauteur / 2, l)
            haut += hauteur + ESPACE
        x += l + ECART
        largeur = max(largeur, x - ECART)
    return place, largeur + MARGE, y + hauteur_rangee + MARGE


def disposition(g, libelles):
    variables = systeme_de_base().variables
    membres = {}
    for nom in g:
        membres.setdefault(bloc(nom, variables), []).append(nom)
    place, cadres, x = {}, [], 0.0
    for colonne in sorted({c for _, c, _ in BLOCS}):
        titres = [titre for titre, c, _ in BLOCS if c == colonne and titre in membres]
        mesures = {titre: disposition_bloc(g, membres[titre], libelles) for titre in titres}
        hauteur = sum(h for _, _, h in mesures.values()) + ECART_BLOCS * (len(titres) - 1)
        largeur, y = max(l for _, l, _ in mesures.values()), -hauteur / 2
        for titre in titres:
            interne, l, h = mesures[titre]
            cadres.append([titre, round(x, 1), round(y, 1), round(l, 1), round(h, 1)])
            for nom, (bx, by, bl) in interne.items():
                place[nom] = (x + bx, y + by, bl)
            y += h + ECART_BLOCS
        x += largeur + ECART_COLONNES
    return place, cadres


def donnees(aretes, libelles):
    g, parametres = graphe(aretes)
    place, cadres = disposition(g, libelles)
    noms = sorted(g)
    indice = {nom: i for i, nom in enumerate(noms)}
    variables = systeme_de_base().variables
    blocs = {nom: bloc(nom, variables) for nom in noms}
    xs = [place[n][0] for n in noms]
    ys = [place[n][1] for n in noms]
    fins = [place[n][0] + place[n][2] for n in noms]
    return {
        "racine": RACINE,
        "explorateur": EXPLORATEUR,
        "noeuds": [[nom, round(place[nom][0], 1), round(place[nom][1], 1), round(place[nom][2], 1), libelles.get(nom, ""), lignes(nom, libelles), hauteur_noeud(nom, libelles)] for nom in noms],
        "aretes": [[indice[s], indice[c], int(a), int(blocs[s] != blocs[c])] for s, c, a in sorted(g.edges(data="anterieure"))],
        "blocs": cadres,
        "etendue": [min(xs) - 100, min(c[2] for c in cadres) - 200, max(fins) - min(xs) + 200, max(c[2] + c[4] for c in cadres) - min(c[2] for c in cadres) + 300],
        "parametres": {nom: sorted(parametres[nom]) for nom in noms if nom in parametres},
        }


def page(date, aretes, libelles):
    titre = f"Système socio-fiscal, {MOIS[date[5:7]]} {date[2:4]}"
    contenu = json.dumps(donnees(aretes, libelles), ensure_ascii=False, separators=(",", ":"))
    return MODELE.replace("__TITRE__", titre).replace("__DONNEES__", contenu)


def main(date=DATES[-1]):
    if date not in DATES:
        raise SystemExit(f"date inconnue : {date} (dates possibles : {DATES[0]} à {DATES[-1]}, janvier et juillet)")
    aretes, libelles = trace(date)
    SORTIE.mkdir(parents=True, exist_ok=True)
    contenu = page(date, aretes, libelles)
    (SORTIE / "index.html").write_text(contenu, encoding="utf-8")
    print(SORTIE / "index.html", date, len(contenu) // 1024, "ko")

