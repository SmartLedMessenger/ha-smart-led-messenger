"""Mise en phrase francaise d'un changement d'etat Home Assistant.

EVOLUTIONS-APIS.md §3.21. C'est le coeur de l'integration, et volontairement
le seul module qui N'IMPORTE PAS Home Assistant : une fonction pure, testable
sans rien installer (cf. ../../tests/test_phrases.py).

---------------------------------------------------------------------------
 L'ACCORD EN GENRE NE SE DEDUIT PAS DU device_class
---------------------------------------------------------------------------
 « Portail ouvert » mais « Porte garage ouverte » : c'est le meme capteur, la
 meme classe, le meme etat. Le genre appartient au NOM QUE L'UTILISATEUR A
 DONNE a son entite, pas au type de l'appareil.

 On accorde donc sur le premier mot du nom, avec un petit lexique des noms
 feminins courants d'une maison. Le masculin est le defaut, parce que c'est la
 forme non marquee du francais : une lacune du lexique donne « Trappe ouvert »,
 qui se lit ; l'inverse donnerait « Portail ouverte », qui accroche l'oeil.

 Quand le lexique se trompe, l'utilisateur pose un gabarit sur l'entite.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import unicodedata

# Adjectifs, au masculin puis au feminin. Les DEUX formes sont ecrites : une
# regle « ajouter un e » suffirait pour ceux-ci, mais pas pour le premier
# irregulier venu, et une table se relit mieux qu'une regle.
OUVERT = ("ouvert", "ouverte")
FERME = ("fermé", "fermée")
ALLUME = ("allumé", "allumée")
ETEINT = ("éteint", "éteinte")
VERROUILLE = ("verrouillé", "verrouillée")
DEVERROUILLE = ("déverrouillé", "déverrouillée")
CONNECTE = ("connecté", "connectée")
DECONNECTE = ("déconnecté", "déconnectée")
ACTIF = ("actif", "active")
INACTIF = ("inactif", "inactive")

# Une valeur de regle est :
#   - un couple (masculin, feminin) : accorde au nom, phrase « Nom adjectif » ;
#   - une chaine contenant {nom}    : phrase complete, invariable ;
#   - None                          : on n'annonce rien.
#
# None est un choix, pas un oubli. La fin d'un mouvement ou d'une fuite
# n'interesse personne sur un bandeau, et chaque phrase inutile chasse une
# phrase utile : l'afficheur n'a qu'une ligne.

# Par domaine, quand le domaine suffit a decider.
_PAR_DOMAINE: dict[str, dict[str, object]] = {
    "light": {"on": ALLUME, "off": ETEINT},
    "switch": {"on": ALLUME, "off": ETEINT},
    "input_boolean": {"on": ACTIF, "off": INACTIF},
    "fan": {"on": ALLUME, "off": ETEINT},
    "siren": {"on": ALLUME, "off": ETEINT},
    "humidifier": {"on": ALLUME, "off": ETEINT},
    "media_player": {"playing": "{nom} joue", "paused": None, "idle": None, "off": ETEINT},
    # Un volet en cours de course ne s'annonce pas : il s'annoncera arrive.
    "cover": {"open": OUVERT, "closed": FERME, "opening": None, "closing": None},
    "lock": {"locked": VERROUILLE, "unlocked": DEVERROUILLE, "locking": None, "unlocking": None},
    "device_tracker": {"home": "{nom} est à la maison", "not_home": "{nom} est parti"},
    "person": {"home": "{nom} est à la maison", "not_home": "{nom} est parti"},
    "vacuum": {
        "cleaning": "{nom} nettoie",
        "returning": None,
        "docked": "{nom} est à sa base",
        "error": "{nom} est en panne",
    },
}

# Par device_class : c'est la seule chose qui distingue deux binary_sensor.
_PAR_CLASSE: dict[str, dict[str, object]] = {
    "door": {"on": OUVERT, "off": FERME},
    "garage_door": {"on": OUVERT, "off": FERME},
    "garage": {"on": OUVERT, "off": FERME},
    "window": {"on": OUVERT, "off": FERME},
    "opening": {"on": OUVERT, "off": FERME},
    "gate": {"on": OUVERT, "off": FERME},
    # Un binary_sensor de serrure est a l'envers : on = deverrouille.
    "lock": {"on": DEVERROUILLE, "off": VERROUILLE},
    "light": {"on": ALLUME, "off": ETEINT},
    "power": {"on": ALLUME, "off": ETEINT},
    "plug": {"on": ALLUME, "off": ETEINT},
    "connectivity": {"on": CONNECTE, "off": DECONNECTE},
    "running": {"on": "{nom} en marche", "off": "{nom} à l'arrêt"},
    "motion": {"on": "Mouvement détecté, {nom}", "off": None},
    "occupancy": {"on": "Présence détectée, {nom}", "off": None},
    "presence": {"on": "Présence détectée, {nom}", "off": None},
    "moisture": {"on": "Fuite d'eau, {nom}", "off": None},
    "smoke": {"on": "Fumée détectée, {nom}", "off": None},
    "gas": {"on": "Gaz détecté, {nom}", "off": None},
    "carbon_monoxide": {"on": "Monoxyde de carbone détecté, {nom}", "off": None},
    "problem": {"on": "Problème, {nom}", "off": None},
    "safety": {"on": "Alerte, {nom}", "off": None},
    "tamper": {"on": "{nom} a été manipulé", "off": None},
    "battery": {"on": "{nom} : batterie faible", "off": None},
    "update": {"on": "{nom} : mise à jour disponible", "off": None},
}

# Un binary_sensor sans device_class ne dit pas ce qu'il mesure. On reste
# neutre plutot que de parier sur « ouvert ».
_BINAIRE_PAR_DEFAUT: dict[str, object] = {"on": ACTIF, "off": INACTIF}

# Noms feminins courants d'une maison. Le premier mot du nom de l'entite
# suffit : « Porte garage », « Lumiere salon », « Fenetre chambre » commencent
# tous par le nom de l'objet. Sans accents ni casse (cf. _pivot).
_FEMININS = frozenset(
    """
    alarme allee ampoule applique baie balise barriere boite borne bouilloire
    box cafetiere camera cave chaine chambre chaudiere cheminee clim
    climatisation cloture console cuisine douche enceinte entree fenetre
    fontaine grille guirlande hotte imprimante lampe led lessive lumiere
    machine mezzanine motorisation ouverture piece piscine pompe porte prise
    rampe salle serre serrure sonnette suspension tablette telecommande
    television tele terrasse tondeuse trappe tv vanne veranda vitre vmc voiture
    """.split()
)


def _pivot(mot: str) -> str:
    """Mot compare au lexique : sans accents, sans casse, sans ponctuation."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", mot) if unicodedata.category(c) != "Mn"
    )
    return "".join(c for c in sans_accents.lower() if c.isalpha())


def est_feminin(nom: str) -> bool:
    """Le nom de l'entite designe-t-il un objet feminin ?

    Sur le PREMIER mot : c'est lui qui porte l'objet, le reste situe la piece
    (« Porte garage », « Lumiere salon »). Masculin par defaut.
    """
    mots = nom.split()
    return bool(mots) and _pivot(mots[0]) in _FEMININS


def _regle(domaine: str, device_class: str | None) -> dict[str, object] | None:
    """Table applicable, du plus specifique au plus general."""
    if domaine == "binary_sensor":
        return _PAR_CLASSE.get(device_class or "", _BINAIRE_PAR_DEFAUT)
    if domaine in _PAR_DOMAINE:
        return _PAR_DOMAINE[domaine]
    # Domaine inconnu de la table : sa classe est parfois parlante quand meme.
    return _PAR_CLASSE.get(device_class or "")


def _est_mesure(etat: str) -> bool:
    try:
        float(etat)
    except (TypeError, ValueError):
        return False
    return True


def phrase(
    nom: str,
    etat: str,
    domaine: str,
    device_class: str | None = None,
    unite: str | None = None,
    gabarit: str | None = None,
) -> str | None:
    """Phrase a faire defiler, ou None s'il n'y a rien a annoncer.

    Un gabarit pose par l'utilisateur l'emporte sur tout le reste. Il admet
    {nom}, {etat} et {unite} : des champs simples, et non du Jinja. Le Jinja
    reste disponible la ou Home Assistant le rend nativement, c'est-a-dire
    dans l'appel de service smart_led_messenger.envoyer_evenement — plutot que
    reimplemente a moitie ici.
    """
    nom = " ".join((nom or "").split())
    if not nom:
        return None

    if gabarit:
        try:
            rendu = gabarit.format(nom=nom, etat=etat, unite=unite or "")
        except (KeyError, IndexError, ValueError):
            # Un gabarit fautif ne doit pas faire taire l'evenement : on
            # retombe sur la phrase automatique.
            pass
        else:
            return " ".join(rendu.split()) or None

    regle = _regle(domaine, device_class)
    if regle is not None and etat in regle:
        forme = regle[etat]
        if forme is None:
            return None
        if isinstance(forme, tuple):
            return f"{nom} {forme[1] if est_feminin(nom) else forme[0]}"
        return forme.format(nom=nom)

    # Un capteur de mesure : la valeur et son unite, c'est tout ce qu'on peut
    # en dire d'utile — et c'est deja la moitie de ce que les gens y branchent.
    if domaine == "sensor" and _est_mesure(etat):
        valeur = etat.replace(".", ",")
        return f"{nom} : {valeur} {unite}".strip() if unite else f"{nom} : {valeur}"

    # Etat inconnu (unavailable, unknown, etat non couvert d'un domaine
    # exotique) : SILENCE. « Portail unavailable » sur un mur est pire que
    # rien, et une passerelle qui redemarre en produirait dix d'un coup.
    return None
