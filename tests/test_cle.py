"""Normalisation de la clé (EVOLUTIONS-APIS.md §3.21).

Ces tests naissent d'un vrai défaut, constaté le 01/09/2026 sur une
installation Home Assistant réelle : le formulaire répondait « Le serveur
refuse cette clé » avec une clé parfaitement valide.

La cause : l'espace client montre la clé **dans une URL**, donc déjà
percent-encodée (`%2B`, `%3D`). L'utilisateur la recopie telle quelle — c'est
ce que la documentation lui demande, à juste titre pour un `rest_command`.
Mais `aiohttp` encode à son tour ce qu'on lui passe en paramètre : `%2B`
devient `%252B`, le serveur lit trois caractères littéraux là où il attendait
du base64, et refuse.

Le module est sans dépendance : `python -m pytest` suffit.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "smart_led_messenger"))

from cle import normaliser_cle  # noqa: E402

# La clé réelle qui a échoué, telle que l'espace client l'affiche.
ENCODEE = "bh4z6VUfQJtInweFk8TW%2BQ%3D%3D"
DECODEE = "bh4z6VUfQJtInweFk8TW+Q=="


def test_la_cle_recopiee_depuis_l_url_est_decodee():
    # Le défaut d'origine, verrouillé nommément.
    assert normaliser_cle(ENCODEE) == DECODEE


def test_une_cle_deja_decodee_ne_bouge_pas():
    # Idempotence : on ne sait pas laquelle des deux formes l'utilisateur a
    # sous la main, et il n'a aucune raison de le savoir non plus.
    assert normaliser_cle(DECODEE) == DECODEE
    assert normaliser_cle(normaliser_cle(ENCODEE)) == DECODEE


def test_l_url_personnelle_entiere_est_acceptee():
    # Le geste le plus naturel après avoir cliqué sur « Afficher mon URL ».
    url = (
        "https://www.smartledmessenger.com/push.ashx"
        f"?key={ENCODEE}&message=MONNOUVEAUMESSAGE"
    )
    assert normaliser_cle(url) == DECODEE


def test_l_ordre_des_parametres_de_l_url_est_indifferent():
    url = f"https://www.smartledmessenger.com/push.ashx?message=Test&key={ENCODEE}"
    assert normaliser_cle(url) == DECODEE


def test_une_url_sans_cle_ne_produit_rien():
    # Mieux vaut vide — et donc refusé par le formulaire — qu'une URL prise
    # pour une clé.
    assert normaliser_cle("https://www.smartledmessenger.com/domotique.html") == ""


def test_le_plus_d_une_cle_decodee_survit_a_une_url():
    # parse_qs transformerait ce « + » en espace : c'est la raison pour
    # laquelle il n'est pas utilisé.
    url = f"https://www.smartledmessenger.com/push.ashx?key={DECODEE}"
    assert normaliser_cle(url) == DECODEE


@pytest.mark.parametrize("saisie", ["", "   ", None])
def test_une_saisie_vide_reste_vide(saisie):
    assert normaliser_cle(saisie) == ""


def test_les_espaces_autour_sont_coupes():
    # Un copier-coller emporte souvent une espace ou un retour à la ligne.
    assert normaliser_cle(f"  {ENCODEE}\n") == DECODEE
