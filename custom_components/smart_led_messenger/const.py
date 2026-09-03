"""Constantes de l'integration Smart Led Messenger (EVOLUTIONS-APIS.md §3.21)."""

from __future__ import annotations

DOMAIN = "smart_led_messenger"

# --- Donnees de l'entree de configuration ------------------------------------
CONF_CLE = "cle"
CONF_URL_BASE = "url_base"

URL_BASE_PAR_DEFAUT = "https://www.smartledmessenger.com"

# --- Options ------------------------------------------------------------------
CONF_ENTITES = "entites"
CONF_DUREE = "duree"
CONF_INTERVALLE_MIN = "intervalle_min"
CONF_GABARITS = "gabarits"

# Duree de vie d'un evenement, en minutes. Le serveur applique le meme defaut
# et le meme plafond (cf. Evenements.cs) : les deux valeurs sont recopiees ici
# pour que le formulaire refuse avant l'appel, pas pour faire autorite.
DUREE_PAR_DEFAUT = 5
DUREE_MAX = 120

# Anti-rebond par entite, en secondes. Un contact de portail rebondit, un
# capteur de puissance change en continu : sans plancher, chaque changement
# serait un appel HTTP et une ecriture en base.
#
# 30 s par defaut, qui est aussi la periode de sondage de l'afficheur : en
# dessous, les evenements supplementaires ne seraient de toute facon jamais
# vus.
INTERVALLE_MIN_PAR_DEFAUT = 30

# --- Services -----------------------------------------------------------------
SERVICE_ENVOYER_EVENEMENT = "envoyer_evenement"
SERVICE_ENVOYER_MESSAGE = "envoyer_message"
SERVICE_EFFACER = "effacer"

ATTR_TEXTE = "texte"
ATTR_DUREE = "duree"
