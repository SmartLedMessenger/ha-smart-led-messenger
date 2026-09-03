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

from .cle import normaliser_cle

_LOGGER = logging.getLogger(__name__)

DELAI_MAX = 15

REPONSE_CLE_INVALIDE = "Clé invalide"
REPONSE_SLOT_INCONNU = "Slot inconnu"

# Slot volontairement inexistant, utilise comme sonde : sur un serveur a jour,
# il est refuse AVANT toute ecriture (cf. push.ashx), ce qui valide la cle sans
# rien changer au bandeau.
SLOT_SONDE = "verification"


class CleInvalide(Exception):
    """La cle n'a pas pu etre dechiffree par le serveur."""


class ServeurSansEvenements(Exception):
    """Le serveur repond, mais ignore le parametre slot.

    Autrement dit : il est anterieur au §3.21. L'integration ne peut pas y
    fonctionner — chaque evenement irait ecraser le message personnel du
    client, ce que l'emplacement dedie existe justement pour eviter.
    """


class ServeurInjoignable(Exception):
    """Reseau, DNS, delai depasse, 5xx."""


class ClientSmartLedMessenger:
    """Un compte Smart Led Messenger, vu depuis Home Assistant."""

    def __init__(self, session: aiohttp.ClientSession, url_base: str, cle: str) -> None:
        self._session = session
        self._url_base = url_base.rstrip("/")
        # aiohttp encode ce qu'on lui donne : la cle doit partir DECODEE, sans
        # quoi le %2B de l'espace client arrive en %252B (cf. cle.py).
        self._cle = normaliser_cle(cle)

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
        """Eprouve la cle ET le serveur, depuis le formulaire de configuration.

        La sonde est un SLOT INEXISTANT, et c'est ce qui la rend sans effet :
        un serveur a jour verifie la cle, refuse le slot, et n'ecrit rien du
        tout. Le bandeau du client n'est pas touche, meme pas son emplacement
        evenement.

        En prime, la reponse dit si le serveur connait les evenements — un
        « OK » signifie qu'il a ignore le slot, donc qu'il est anterieur au
        §3.21. Mieux vaut le dire dans le formulaire que de le decouvrir en
        voyant son message personnel ecrase par le premier portail ouvert.

        Leve CleInvalide, ServeurSansEvenements ou ServeurInjoignable.
        """
        reponse = await self._push({"slot": SLOT_SONDE})
        if reponse == "OK":
            raise ServeurSansEvenements(
                "Le serveur a ignoré le paramètre slot : il ne gère pas encore les événements."
            )

    async def _push(self, parametres: dict[str, str]) -> str:
        """Appelle la route et rend le corps de la reponse, deja controle."""
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

        if corps != "OK" and not corps.startswith(REPONSE_SLOT_INCONNU):
            # Toute reponse future qu'on ne connait pas : tracer plutot que
            # lever, un evenement n'est pas assez important pour faire echouer
            # quoi que ce soit dans Home Assistant.
            _LOGGER.warning("Réponse inattendue de %s : %s", url, corps)

        return corps
