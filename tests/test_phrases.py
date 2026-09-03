"""Générateur de phrases (EVOLUTIONS-APIS.md §3.21).

Aucun import de Home Assistant : `python -m pytest` suffit, sans installer
quoi que ce soit. C'est la raison pour laquelle phrases.py ne connaît rien de
Home Assistant — la logique qui décide de ce qui s'affiche sur un mur doit
pouvoir s'éprouver seule.

Les cas verrouillés ici sont ceux de la demande d'origine, plus tout ce qui
doit rester SILENCIEUX : un bandeau d'une seule ligne se gâche plus vite par
ce qu'on y met en trop que par ce qu'on y oublie.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "smart_led_messenger"))

from phrases import est_feminin, phrase  # noqa: E402


# ---------------------------------------------------------------------------
#  Les trois exemples de la demande
# ---------------------------------------------------------------------------


def test_portail_ouvert():
    assert phrase("Portail", "on", "binary_sensor", "garage_door") == "Portail ouvert"


def test_porte_garage_ouverte():
    # Même capteur, même classe, même état que le portail : seul le nom change,
    # et c'est lui qui porte le genre.
    assert phrase("Porte garage", "on", "binary_sensor", "garage_door") == "Porte garage ouverte"


def test_lumiere_salon_allumee():
    assert phrase("Lumière salon", "on", "light") == "Lumière salon allumée"


# ---------------------------------------------------------------------------
#  L'accord
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nom",
    ["Porte", "porte d'entrée", "Fenêtre chambre", "Lumière", "Véranda", "Baie vitrée", "TV salon"],
)
def test_noms_feminins(nom):
    assert est_feminin(nom)


@pytest.mark.parametrize("nom", ["Portail", "Volet salon", "Garage", "Store terrasse", "Bureau"])
def test_noms_masculins(nom):
    assert not est_feminin(nom)


def test_un_nom_inconnu_du_lexique_passe_au_masculin():
    # La forme non marquée : « Sas ouvert » se lit, « Portail ouverte » accroche.
    assert phrase("Sas", "on", "binary_sensor", "door") == "Sas ouvert"


def test_l_accord_ignore_la_casse_et_les_accents():
    assert phrase("PORTE cave", "off", "binary_sensor", "door") == "PORTE cave fermée"
    assert phrase("Fenetre cuisine", "on", "binary_sensor", "window") == "Fenetre cuisine ouverte"


# ---------------------------------------------------------------------------
#  Ce qui doit rester silencieux
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("etat", ["unavailable", "unknown", ""])
def test_les_trous_ne_s_annoncent_pas(etat):
    # Une passerelle qui redémarre ne doit pas remplir le bandeau.
    assert phrase("Portail", etat, "binary_sensor", "garage_door") is None


def test_la_fin_d_un_mouvement_ne_s_annonce_pas():
    assert phrase("Détecteur salon", "on", "binary_sensor", "motion") == "Mouvement détecté, Détecteur salon"
    assert phrase("Détecteur salon", "off", "binary_sensor", "motion") is None


def test_un_volet_en_cours_de_course_ne_s_annonce_pas():
    assert phrase("Volet salon", "opening", "cover") is None
    assert phrase("Volet salon", "open", "cover") == "Volet salon ouvert"


def test_un_domaine_sans_regle_reste_muet():
    assert phrase("Thermostat", "heat", "climate") is None


def test_un_nom_vide_ne_produit_rien():
    assert phrase("", "on", "light") is None


# ---------------------------------------------------------------------------
#  Les autres familles d'appareils
# ---------------------------------------------------------------------------


def test_la_serrure_binaire_est_a_l_envers():
    # binary_sensor device_class lock : on = déverrouillé.
    assert phrase("Serrure entrée", "on", "binary_sensor", "lock") == "Serrure entrée déverrouillée"
    assert phrase("Serrure entrée", "off", "binary_sensor", "lock") == "Serrure entrée verrouillée"


def test_le_domaine_lock_est_a_l_endroit():
    assert phrase("Verrou garage", "locked", "lock") == "Verrou garage verrouillé"
    assert phrase("Verrou garage", "unlocked", "lock") == "Verrou garage déverrouillé"


def test_une_presence_est_une_phrase_complete():
    assert phrase("Margot", "home", "person") == "Margot est à la maison"
    assert phrase("Margot", "not_home", "person") == "Margot est parti"


def test_une_fuite_d_eau():
    assert phrase("Capteur cave", "on", "binary_sensor", "moisture") == "Fuite d'eau, Capteur cave"


def test_un_binary_sensor_sans_classe_reste_neutre():
    # On ne parie pas sur « ouvert » : le capteur ne dit pas ce qu'il mesure.
    assert phrase("Capteur", "on", "binary_sensor") == "Capteur actif"


# ---------------------------------------------------------------------------
#  Capteurs de mesure
# ---------------------------------------------------------------------------


def test_un_capteur_de_mesure_donne_sa_valeur_avec_son_unite():
    # Virgule décimale : le bandeau est français.
    assert phrase("Température salon", "21.4", "sensor", unite="°C") == "Température salon : 21,4 °C"


def test_un_capteur_texte_sans_regle_reste_muet():
    assert phrase("Machine", "standby", "sensor") is None


# ---------------------------------------------------------------------------
#  Gabarits
# ---------------------------------------------------------------------------


def test_un_gabarit_l_emporte_sur_la_phrase_automatique():
    assert (
        phrase("Portail", "on", "binary_sensor", "garage_door", gabarit="Quelqu'un arrive")
        == "Quelqu'un arrive"
    )


def test_un_gabarit_peut_reprendre_le_nom_l_etat_et_l_unite():
    assert (
        phrase("Température salon", "21.4", "sensor", unite="°C", gabarit="Il fait {etat}{unite}")
        == "Il fait 21.4°C"
    )


def test_un_gabarit_fautif_retombe_sur_la_phrase_automatique():
    # Ne pas faire taire l'événement à cause d'une accolade de travers.
    assert (
        phrase("Portail", "on", "binary_sensor", "garage_door", gabarit="{inconnu}")
        == "Portail ouvert"
    )


def test_un_gabarit_multiligne_revient_sur_une_ligne():
    # L'afficheur n'a qu'une ligne ; le serveur le garantit aussi, mais autant
    # ne pas lui envoyer n'importe quoi.
    assert phrase("Portail", "on", "binary_sensor", "gate", gabarit="Portail\n  ouvert") == "Portail ouvert"
