"""Formulaires de configuration (EVOLUTIONS-APIS.md §3.21).

La cle est EPROUVEE A LA SAISIE, et c'est la raison d'etre du config flow.
Sans lui, une cle recopiee de travers ne se decouvre que des semaines plus
tard, en constatant qu'un portail ne s'annonce jamais — push.ashx repondant
« OK » a peu pres a tout (cf. api.py).

Ce que la verification prouve : le serveur repond, et il sait dechiffrer la
cle. Ce qu'elle ne prouve pas : que le compte existe. Le formulaire ne
pretend pas le contraire, et le texte d'aide renvoie au bandeau.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ClientSmartLedMessenger, CleInvalide, ServeurInjoignable
from .const import (
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
    URL_BASE_PAR_DEFAUT,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA_UTILISATEUR = vol.Schema(
    {
        vol.Required(CONF_CLE): str,
        vol.Optional(CONF_URL_BASE, default=URL_BASE_PAR_DEFAUT): str,
    }
)

# Les domaines qui produisent des evenements lisibles sur un bandeau. Le
# selecteur n'interdit rien d'autre par principe, il evite d'avoir a chercher
# une porte parmi six mille entites.
DOMAINES_SUIVABLES = [
    "binary_sensor",
    "cover",
    "device_tracker",
    "input_boolean",
    "light",
    "lock",
    "person",
    "sensor",
    "switch",
    "vacuum",
]

SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_ENTITES, default=list): EntitySelector(
            EntitySelectorConfig(domain=DOMAINES_SUIVABLES, multiple=True)
        ),
        vol.Optional(CONF_DUREE, default=DUREE_PAR_DEFAUT): NumberSelector(
            NumberSelectorConfig(min=1, max=DUREE_MAX, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_INTERVALLE_MIN, default=INTERVALLE_MIN_PAR_DEFAUT): NumberSelector(
            NumberSelectorConfig(min=0, max=3600, step=5, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_GABARITS, default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
        ),
    }
)


async def _verifier(hass, cle: str, url_base: str) -> str | None:
    """Renvoie la cle d'erreur du formulaire, ou None si tout va bien."""
    client = ClientSmartLedMessenger(async_get_clientsession(hass), url_base, cle)
    try:
        await client.verifier()
    except CleInvalide:
        return "cle_invalide"
    except ServeurInjoignable as erreur:
        _LOGGER.debug("Vérification impossible : %s", erreur)
        return "injoignable"
    return None


class FluxConfiguration(ConfigFlow, domain=DOMAIN):
    """Ajout d'un compte."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        erreurs: dict[str, str] = {}

        if user_input is not None:
            cle = user_input[CONF_CLE].strip()
            url_base = user_input.get(CONF_URL_BASE, URL_BASE_PAR_DEFAUT).strip()

            # La cle EST le compte : deux entrees pour la meme cle ecriraient
            # sur le meme bandeau, chacune ignorant l'autre.
            await self.async_set_unique_id(cle)
            self._abort_if_unique_id_configured()

            erreur = await _verifier(self.hass, cle, url_base)
            if erreur:
                erreurs["base"] = erreur
            else:
                return self.async_create_entry(
                    title="Smart Led Messenger",
                    data={CONF_CLE: cle, CONF_URL_BASE: url_base},
                    options={
                        CONF_ENTITES: [],
                        CONF_DUREE: DUREE_PAR_DEFAUT,
                        CONF_INTERVALLE_MIN: INTERVALLE_MIN_PAR_DEFAUT,
                        CONF_GABARITS: "",
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_UTILISATEUR, errors=erreurs
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return FluxOptions()


class FluxOptions(OptionsFlow):
    """Entites suivies, durée de vie, anti-rebond, gabarits."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Les selecteurs numeriques rendent des flottants ; les minutes et
            # les secondes partent telles quelles dans l'URL de push.ashx.
            donnees = dict(user_input)
            donnees[CONF_DUREE] = int(donnees[CONF_DUREE])
            donnees[CONF_INTERVALLE_MIN] = int(donnees[CONF_INTERVALLE_MIN])
            return self.async_create_entry(data=donnees)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                SCHEMA_OPTIONS, self.config_entry.options
            ),
        )
