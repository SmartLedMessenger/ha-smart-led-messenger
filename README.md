# Intégration Home Assistant — Smart Led Messenger

Envoie les événements de la maison sur le bandeau LED : « Portail ouvert »,
« Porte garage ouverte », « Lumière salon allumée ».

Les phrases sont composées côté Home Assistant ; le serveur ne reçoit qu'un
texte déjà prêt.

## Ce qu'elle fait, et ce qu'elle ne fait pas

Vous choisissez des entités. Quand leur état change, l'intégration compose une
phrase française et l'envoie sur votre afficheur, où elle défile quelques
minutes avant de disparaître seule.

Elle **ne remplace pas votre message personnel** et n'active pas son
affichage : l'événement occupe un emplacement distinct, qui lui est réservé.
C'est la différence avec la recette `rest_command` de la page
[Domotique](https://www.smartledmessenger.com/domotique.html), qui reste
valable pour un texte permanent — et pour Jeedom, Node-RED et tout le reste.

Elle n'expose **aucune entité** dans Home Assistant : rien à afficher, rien à
historiser. Elle écoute et elle pousse.

Le serveur n'appelle jamais votre installation. Tout part de chez vous.

## Installation

### Par HACS, en dépôt personnalisé

C'est la voie recommandée : elle apporte les mises à jour.

Il faut **HACS déjà installé** dans Home Assistant. Si l'entrée « HACS »
n'apparaît pas dans votre menu latéral, commencez par
<https://hacs.xyz/docs/use/download/download/>.

1. Menu latéral, **HACS**.
2. En haut à droite, le menu **⋮** → **Dépôts personnalisés**.
3. Dans **Dépôt**, collez :
   `https://github.com/SmartLedMessenger/ha-smart-led-messenger`
4. Dans **Type**, choisissez **Integration**.
5. **Ajouter**, puis fermez la fenêtre.
6. Cherchez **Smart Led Messenger** dans HACS, ouvrez la fiche,
   **Télécharger**.
7. **Redémarrez Home Assistant** — Paramètres → Système → bouton
   **Redémarrer**. Sans ce redémarrage, l'intégration reste invisible.

### Mettre à jour

Installée par HACS, l'intégration signale elle-même ses nouvelles versions :
la fiche affiche une mise à jour disponible, vous téléchargez, vous redémarrez
Home Assistant. Vos réglages sont conservés.

Si la nouvelle version n'apparaît pas encore, HACS ne l'a pas vue : menu
**⋮ → Recharger les données**, ou redémarrez Home Assistant.

### À la main

Copiez le dossier `custom_components/smart_led_messenger/` — **le dossier
lui-même**, pas son contenu en vrac — dans le dossier `custom_components/` de
votre configuration Home Assistant, puis redémarrez.

Installée ainsi, l'intégration ne se met pas à jour : il faut recopier le
dossier à chaque version.

Le chemin obtenu doit être exactement :

```
config/custom_components/smart_led_messenger/manifest.json
```

Si `custom_components` n'existe pas, créez-le à côté de
`configuration.yaml`.
## Configuration

**Paramètres → Appareils et services → Ajouter une intégration → Smart Led
Messenger.**

La **clé** demandée est celle de votre lien personnel : espace client, encadré
« Votre URL personnelle », la valeur du paramètre `key`.

Trois formes sont acceptées, parce que ce sont celles qu'on a sous la main : la
clé telle qu'elle apparaît dans l'URL (avec ses `%2B` et `%3D`), la clé déjà
décodée, ou **l'URL personnelle entière** collée sans réfléchir.

Elle est éprouvée à la saisie, par une requête qui **n'écrit rien** : on
demande volontairement un emplacement inexistant, que le serveur refuse après
avoir vérifié la clé. Le bandeau n'est pas touché.

Deux limites, dites franchement :

- la vérification prouve que le serveur répond, qu'il sait déchiffrer la clé,
  et qu'il gère les événements ;
- elle ne prouve pas que le compte existe : `push.ashx` répond `OK` à une clé
  bien formée mais inconnue. Après la configuration, regardez le bandeau une
  fois.

Si le formulaire répond que **le serveur ne gère pas encore les événements**,
la clé est bonne : c'est le service qui n'est pas à jour.

Ensuite, **Configurer** ouvre les options :

| Option | Ce qu'elle règle |
|---|---|
| Entités suivies | Ce qui s'annonce. Trois ou quatre valent mieux que trente : l'afficheur n'a qu'une ligne. |
| Durée d'affichage | Minutes avant disparition. 5 par défaut, 120 au maximum. |
| Intervalle minimal | Secondes entre deux envois d'une même entité. 30 par défaut. |
| Formulations personnalisées | Une ligne par entité, `entity_id: texte`. |

Changer une option recharge l'intégration : les nouvelles entités sont écoutées
immédiatement.

## Les phrases

Elles sont déduites du domaine, du `device_class` et du nom que **vous** avez
donné à l'entité.

L'accord en genre vient du nom, pas du capteur : « Portail » et « Porte garage »
sont le même `device_class`, et ne s'accordent pas pareil. Un petit lexique des
noms féminins courants d'une maison s'en charge, avec le masculin pour défaut —
une lacune donne « Trappe ouvert », qui se lit ; l'inverse donnerait « Portail
ouverte », qui accroche l'œil.

Quelques exemples :

| Entité | État | Phrase |
|---|---|---|
| `binary_sensor` `garage_door` « Portail » | `on` | Portail ouvert |
| `binary_sensor` `garage_door` « Porte garage » | `on` | Porte garage ouverte |
| `light` « Lumière salon » | `on` | Lumière salon allumée |
| `binary_sensor` `motion` « Détecteur salon » | `on` | Mouvement détecté, Détecteur salon |
| `lock` « Verrou garage » | `unlocked` | Verrou garage déverrouillé |
| `person` « Margot » | `home` | Margot est à la maison |
| `sensor` « Température salon », °C | `21.4` | Température salon : 21,4 °C |

### Ce qui reste silencieux, volontairement

- `unavailable` et `unknown` — une passerelle qui redémarre en produirait dix
  d'un coup ;
- la sortie d'un de ces trous : redécouvrir un portail ouvert n'est pas
  l'ouvrir ;
- un changement d'attribut seul (régler la luminosité d'une lampe allumée) ;
- la fin d'un mouvement, d'une fuite, d'une alerte ;
- un volet en cours de course : il s'annoncera arrivé ;
- tout état d'un domaine que le générateur ne sait pas dire. Posez un gabarit,
  ou passez par le service.

### Changer une formulation

Dans les options, une ligne par entité :

```
binary_sensor.portail: Quelqu'un arrive
sensor.temperature_salon: Il fait {etat}{unite} au salon
```

Champs disponibles : `{nom}`, `{etat}`, `{unite}`. Ce sont des champs simples,
pas du Jinja : le Jinja est disponible là où Home Assistant le rend nativement,
c'est-à-dire dans les appels de service ci-dessous.

## Services

### `smart_led_messenger.envoyer_evenement`

Le texte y est un modèle Home Assistant ordinaire — c'est l'échappatoire pour
tout ce que la phrase automatique ne sait pas dire.

```yaml
automation:
  - alias: Lave-linge terminé
    triggers:
      - trigger: numeric_state
        entity_id: sensor.lave_linge_puissance
        below: 5
        for: "00:05:00"
    actions:
      - action: smart_led_messenger.envoyer_evenement
        data:
          texte: "Lave-linge terminé, {{ now().strftime('%H:%M') }}"
          duree: 30
```

### `smart_led_messenger.envoyer_message`

Remplace le **message personnel** et force son affichage : permanent, jusqu'au
prochain envoi. C'est le comportement historique de `push.ashx`. Un texte vide
l'efface.

### `smart_led_messenger.effacer`

Retire l'événement en cours sans attendre sa péremption.

## Délais

Un événement n'est pas instantané. L'afficheur interroge le serveur toutes les
30 secondes environ : c'est le plancher, et l'intervalle minimal par défaut est
réglé dessus. En dessous, les envois supplémentaires ne seraient de toute façon
jamais vus.

## Développement

Le générateur de phrases n'importe rien de Home Assistant, et se teste seul :

```bash
python -m pytest tests/
```

C'est délibéré : la logique qui décide de ce qui s'affiche sur un mur doit
pouvoir s'éprouver sans installer une domotique.
