"""Integration Smart Led Messenger pour Home Assistant.

EVOLUTIONS-APIS.md §3.21 — envoie les evenements de la maison sur le bandeau
LED : « Portail ouvert », « Porte garage ouverte », « Lumiere salon allumee ».

---------------------------------------------------------------------------
 LE SENS DES APPELS
---------------------------------------------------------------------------
 Home Assistant appelle le serveur, JAMAIS l'inverse. Le serveur n'a aucune
 adresse a joindre chez le client, aucun jeton a stocker, rien a sonder. C'est
 ce qui rend cette integration sans risque cote service, la ou un connecteur
 generique poserait les questions du §4 (SSRF, quotas, relais).
---------------------------------------------------------------------------
 CE QUI FAIT LA QUALITE DU RESULTAT : LE FILTRAGE
---------------------------------------------------------------------------
 Un afficheur n'a qu'une ligne. La difficulte n'est pas d'envoyer, c'est de
 n'envoyer que ce qui merite d'etre lu :

   - un changement d'ATTRIBUT seul (luminosite, temperature cible) n'est pas
     un evenement : l'etat n'a pas bouge ;
   - unavailable et unknown ne s'annoncent pas — une passerelle qui redemarre
     en produirait dix d'un coup ;
   - le premier etat connu apres un demarrage de Home Assistant n'est pas un
     evenement non plus : rien ne vient de se passer ;
   - deux changements de la meme entite a quelques secondes d'intervalle (un
     contact qui rebondit) ne valent qu'une phrase.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from .api import ClientSmartLedMessenger, CleInvalide, ServeurInjoignable
from .const import (
    ATTR_DUREE,
    ATTR_TEXTE,
    CONF_CLE,
    CONF_DUREE,
    CONF_ENTITES,
    CONF_GABARITS,
    CONF_INTERVALLE_MIN,
    CONF_URL_BASE,
    DOMAIN,
    DUREE_MAX,
    DUREE_PAR_DEFAUT,
    INTERVALLE_MIN_PAR_DEFAUT,
    SERVICE_EFFACER,
    SERVICE_ENVOYER_EVENEMENT,
    SERVICE_ENVOYER_MESSAGE,
    URL_BASE_PAR_DEFAUT,
)
from .phrases import phrase

_LOGGER = logging.getLogger(__name__)

# Etats qui ne sont pas des evenements, mais des trous.
ETATS_MUETS = {STATE_UNAVAILABLE, STATE_UNKNOWN, None, ""}

SCHEMA_EVENEMENT = vol.Schema(
    {
        vol.Required(ATTR_TEXTE): cv.string,
        vol.Optional(ATTR_DUREE): vol.All(vol.Coerce(int), vol.Range(min=1, max=DUREE_MAX)),
    }
)
SCHEMA_MESSAGE = vol.Schema({vol.Required(ATTR_TEXTE): cv.string})
SCHEMA_EFFACER = vol.Schema({})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Met en place un compte Smart Led Messenger."""
    client = ClientSmartLedMessenger(
        async_get_clientsession(hass),
        entry.data.get(CONF_URL_BASE, URL_BASE_PAR_DEFAUT),
        entry.data[CONF_CLE],
    )

    passerelle = PasserelleEvenements(hass, entry, client)
    entry.runtime_data = passerelle
    passerelle.demarrer()

    # Changer la liste des entites suivies change ce qu'il faut ecouter :
    # l'abonnement se refait au rechargement, pas a chaud.
    entry.async_on_unload(entry.add_update_listener(_sur_changement_options))

    _enregistrer_services(hass)
    return True


async def _sur_changement_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Retire le compte. Les abonnements sont defaits par async_on_unload."""
    if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
        for service in (SERVICE_ENVOYER_EVENEMENT, SERVICE_ENVOYER_MESSAGE, SERVICE_EFFACER):
            hass.services.async_remove(DOMAIN, service)
    return True


class PasserelleEvenements:
    """Ecoute les entites choisies et pousse une phrase par evenement retenu."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: ClientSmartLedMessenger
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        # Derniere poussee par entite, pour l'anti-rebond. Une horloge
        # monotone : l'heure murale peut reculer, pas celle-ci.
        self._derniere: dict[str, float] = {}
        # Home Assistant republie l'etat de tout le monde au demarrage. Tant
        # qu'il n'est pas demarre, on ecoute sans rien envoyer.
        self._pret = hass.is_running

    # -- Reglages ---------------------------------------------------------

    @property
    def entites(self) -> list[str]:
        return list(self.entry.options.get(CONF_ENTITES, []))

    @property
    def duree(self) -> int:
        return int(self.entry.options.get(CONF_DUREE, DUREE_PAR_DEFAUT))

    @property
    def intervalle_min(self) -> int:
        return int(self.entry.options.get(CONF_INTERVALLE_MIN, INTERVALLE_MIN_PAR_DEFAUT))

    @property
    def gabarits(self) -> dict[str, str]:
        """« entity_id: gabarit » par ligne, tel que saisi dans les options."""
        return _lire_gabarits(self.entry.options.get(CONF_GABARITS, ""))

    # -- Cycle de vie -----------------------------------------------------

    def demarrer(self) -> None:
        entites = self.entites
        if not entites:
            _LOGGER.debug("Aucune entité suivie : rien à écouter")
        else:
            self.entry.async_on_unload(
                async_track_state_change_event(self.hass, entites, self._sur_changement)
            )

        if not self._pret:
            self.entry.async_on_unload(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._sur_demarrage)
            )

    @callback
    def _sur_demarrage(self, _event: Event) -> None:
        self._pret = True

    # -- Le filtre --------------------------------------------------------

    @callback
    def _sur_changement(self, event: Event) -> None:
        if not self._pret:
            return

        ancien = event.data.get("old_state")
        nouveau = event.data.get("new_state")
        if nouveau is None:
            return

        # Un changement d'attribut seul n'est pas un evenement : regler la
        # luminosite d'une lampe deja allumee ne s'annonce pas.
        if ancien is not None and ancien.state == nouveau.state:
            return

        # Ni un trou, ni la sortie d'un trou : une passerelle qui revient ne
        # « vient pas d'ouvrir » le portail qu'elle redecouvre ouvert.
        if nouveau.state in ETATS_MUETS or (ancien is not None and ancien.state in ETATS_MUETS):
            return
        if ancien is None:
            return

        entite = event.data["entity_id"]
        maintenant = time.monotonic()
        precedente = self._derniere.get(entite)
        if precedente is not None and maintenant - precedente < self.intervalle_min:
            _LOGGER.debug("%s : changement ignoré (anti-rebond)", entite)
            return

        texte = phrase(
            nom=nouveau.attributes.get("friendly_name") or entite,
            etat=nouveau.state,
            domaine=entite.split(".", 1)[0],
            device_class=nouveau.attributes.get("device_class"),
            unite=nouveau.attributes.get("unit_of_measurement"),
            gabarit=self.gabarits.get(entite),
        )
        if not texte:
            _LOGGER.debug("%s : état « %s » sans phrase, rien envoyé", entite, nouveau.state)
            return

        self._derniere[entite] = maintenant
        self.hass.async_create_task(self._pousser(texte))

    async def _pousser(self, texte: str) -> None:
        """Un evenement rate ne doit rien casser : on trace, on continue."""
        try:
            await self.client.envoyer_evenement(texte, self.duree)
        except CleInvalide:
            _LOGGER.error(
                "Clé refusée par Smart Led Messenger : recopiez-la depuis votre espace "
                "client, encadré « Votre URL personnelle »"
            )
        except ServeurInjoignable as erreur:
            _LOGGER.warning("Événement « %s » non envoyé : %s", texte, erreur)


def _lire_gabarits(brut: str) -> dict[str, str]:
    """« entity_id: gabarit » par ligne. Une ligne fautive est ignoree.

    Ignoree et non refusee : ces lignes sont saisies a la main dans un champ
    libre, et une virgule de travers ne doit pas faire taire les entites qui,
    elles, sont bien ecrites.
    """
    gabarits: dict[str, str] = {}
    for ligne in (brut or "").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or ":" not in ligne:
            continue
        entite, gabarit = ligne.split(":", 1)
        entite, gabarit = entite.strip(), gabarit.strip()
        if entite and gabarit:
            gabarits[entite] = gabarit
    return gabarits


def _enregistrer_services(hass: HomeAssistant) -> None:
    """Les trois services. Enregistres une fois, quel que soit le nombre de comptes."""
    if hass.services.has_service(DOMAIN, SERVICE_ENVOYER_EVENEMENT):
        return

    async def _pour_chaque_compte(appel: ServiceCall, action: str, **kwargs: Any) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            passerelle: PasserelleEvenements | None = getattr(entry, "runtime_data", None)
            if passerelle is None:
                continue
            try:
                await getattr(passerelle.client, action)(**kwargs)
            except (CleInvalide, ServeurInjoignable) as erreur:
                _LOGGER.error("Service %s : %s", appel.service, erreur)

    async def envoyer_evenement(appel: ServiceCall) -> None:
        # Le texte arrive deja rendu : Home Assistant evalue le Jinja de
        # l'appel de service. C'est la l'echappatoire pour tout ce que la
        # phrase automatique ne sait pas dire.
        await _pour_chaque_compte(
            appel,
            "envoyer_evenement",
            texte=appel.data[ATTR_TEXTE],
            duree=appel.data.get(ATTR_DUREE, DUREE_PAR_DEFAUT),
        )

    async def envoyer_message(appel: ServiceCall) -> None:
        await _pour_chaque_compte(appel, "envoyer_message", texte=appel.data[ATTR_TEXTE])

    async def effacer(appel: ServiceCall) -> None:
        await _pour_chaque_compte(appel, "effacer_evenement")

    hass.services.async_register(
        DOMAIN, SERVICE_ENVOYER_EVENEMENT, envoyer_evenement, schema=SCHEMA_EVENEMENT
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ENVOYER_MESSAGE, envoyer_message, schema=SCHEMA_MESSAGE
    )
    hass.services.async_register(DOMAIN, SERVICE_EFFACER, effacer, schema=SCHEMA_EFFACER)
