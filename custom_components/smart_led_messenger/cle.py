"""Normalisation de la cle du compte (EVOLUTIONS-APIS.md §3.21).

---------------------------------------------------------------------------
 LA CLE EST AFFICHEE ENCODEE, ET ELLE NE DOIT PAS ETRE ENVOYEE AINSI
---------------------------------------------------------------------------
 L'espace client montre la cle DANS UNE URL, donc deja percent-encodee :

     ...push.ashx?key=bh4z6VUfQJtInweFk8TW%2BQ%3D%3D&message=...

 La page domotique.html insiste, a juste titre, pour qu'on la recopie telle
 quelle : collee dans une barre d'adresse ou dans un rest_command, c'est la
 forme correcte.

 Mais ici la cle n'est pas collee dans une URL : elle est passee en parametre
 a aiohttp, qui l'encode LUI-MEME. Transmise telle quelle, %2B devient
 %252B, le serveur lit « %2B » comme trois caracteres litteraux, n'y voit
 plus du base64 valide, et repond « Cle invalide ». Constate le 01/09/2026
 sur une vraie installation, avec une cle parfaitement valide.

 On decode donc avant d'envoyer. unquote est SANS DANGER sur une cle deja
 decodee : la forme decodee d'une cle est du base64 (A-Z a-z 0-9 + / =), ou
 « % » ne peut pas apparaitre. Les deux formes sont donc acceptees, et c'est
 tant mieux — personne ne devrait avoir a savoir laquelle il possede.
---------------------------------------------------------------------------
"""

from __future__ import annotations

from urllib.parse import unquote, urlsplit

PREFIXE_PARAMETRE = "key="


def normaliser_cle(saisie: str | None) -> str:
    """La cle telle qu'on peut la coller, ramenee a la forme a envoyer.

    Trois formes admises, parce que ce sont les trois qu'on a sous la main :
      - la cle recopiee depuis l'URL de l'espace client (percent-encodee) ;
      - la cle deja decodee ;
      - l'URL personnelle entiere, collee sans reflechir. C'est le geste le
        plus naturel apres avoir clique sur « Afficher mon URL », et rien ne
        justifie de le punir.
    """
    texte = (saisie or "").strip()
    if not texte:
        return ""

    if texte.lower().startswith(("http://", "https://")):
        # unquote a la main plutot que parse_qs : celui-ci transforme aussi
        # « + » en espace, ce qui mutilerait une cle decodee.
        for morceau in urlsplit(texte).query.split("&"):
            if morceau.startswith(PREFIXE_PARAMETRE):
                return unquote(morceau[len(PREFIXE_PARAMETRE) :])
        return ""

    return unquote(texte)
