"""Appels a push.ashx (EVOLUTIONS-APIS.md §3.21).

---------------------------------------------------------------------------
 CE QUE LA ROUTE REPOND, ET CE QU'ELLE NE DIT PAS
---------------------------------------------------------------------------
 push.ashx repond du texte brut, en 200, dans tous les cas :

   « OK »           -> la cle a pu etre dechiffree, l'ecriture est partie ;
   « Clé invalide » -> la cle n'est pas dechiffrable (recopiee de travers) ;
   « Slot inconnu…» -> le parametre slot ne vaut ni message ni evenement.

 « OK » NE PROUVE PAS que le compte existe : une cle bien formee mais inconnue
 met a jour zero ligne et repond « OK » quand meme. C'est un constat du §4 du
 document, pas un defaut qu'on corrige ici — on se contente de ne pas
 pretendre le contraire dans le formulaire de configuration.

 Les parametres sont lus dans la QUERY STRING uniquement : un POST avec un
 corps de formulaire est ignore, et repond « OK ». D'ou le GET, toujours.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

DELAI_MAX = 15

REPONSE_CLE_INVALIDE = "Clé invalide"


class CleInvalide(Exception):
    """La cle n'a pas pu etre dechiffree par le serveur."""


class ServeurInjoignable(Exception):
    """Reseau, DNS, delai depasse, 5xx."""


class ClientSmartLedMessenger:
    """Un compte Smart Led Messenger, vu depuis Home Assistant."""

    def __init__(self, session: aiohttp.ClientSession, url_base: str, cle: str) -> None:
        self._session = session
        self._url_base = url_base.rstrip("/")
        self._cle = cle

    async def envoyer_evenement(self, texte: str, duree: int) -> None:
        """Pose l'evenement ephemere. Texte vide : l'efface."""
        await self._push({"message": texte, "slot": "evenement", "duree": str(duree)})

    async def effacer_evenement(self) -> None:
        """Retire l'evenement avant sa peremption."""
        await self.envoyer_evenement("", 1)

    async def envoyer_message(self, texte: str) -> None:
        """Remplace le MESSAGE PERSONNEL et force son affichage.

        Le comportement historique de push.ashx : permanent, jusqu'au prochain
        appel. Fourni pour les usages ou c'est ce qu'on veut vraiment (un texte
        qui doit rester), pas pour les evenements.
        """
        await self._push({"message": texte})

    async def verifier(self) -> None:
        """Eprouve la cle depuis le formulaire de configuration.

        La sonde est un EFFACEMENT d'evenement : c'est la seule ecriture
        totalement inoffensive de la route — elle ne touche ni au message
        personnel, ni a l'interrupteur, et vide un emplacement dont
        l'integration est de toute facon la seule a se servir.

        Leve CleInvalide si le serveur refuse la cle, ServeurInjoignable s'il
        ne repond pas. Ne peut pas garantir que le compte existe (cf. l'en-tete
        du module).
        """
        await self.effacer_evenement()

    async def _push(self, parametres: dict[str, str]) -> None:
        url = f"{self._url_base}/push.ashx"
        params = {"key": self._cle, **parametres}

        try:
            async with self._session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=DELAI_MAX)
            ) as reponse:
                reponse.raise_for_status()
                corps = (await reponse.text()).strip()
        except asyncio.TimeoutError as erreur:
            raise ServeurInjoignable(f"{url} n'a pas répondu en {DELAI_MAX} s") from erreur
        except aiohttp.ClientError as erreur:
            raise ServeurInjoignable(str(erreur)) from erreur

        if corps.startswith(REPONSE_CLE_INVALIDE):
            raise CleInvalide(corps)

        if corps != "OK":
            # « Slot inconnu », ou toute reponse future qu'on ne connait pas :
            # tracer plutot que lever, l'evenement n'est pas assez important
            # pour faire echouer quoi que ce soit dans Home Assistant.
            _LOGGER.warning("Réponse inattendue de %s : %s", url, corps)
