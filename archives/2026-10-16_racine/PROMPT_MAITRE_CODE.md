# PROMPT MAÎTRE — PARTIE CODE UNIQUEMENT

Les assets Blender sont faits. Ce prompt pilote uniquement le code (sessions 00 à 19). Il remplace `PROMPT_MAITRE.md` pour la suite.

## Avant de lancer
1. Le dossier `Roblox game` contient `docs/`, `prompt/`, `CLAUDE.md`, `PROGRESS.md` et tes assets (`assets/`).
2. Claude Code lancé dans ce dossier, permissions en mode automatique.
3. (Optionnel) MCP Roblox Studio branché : Claude Code pourra alors lire l'arborescence de ta place et vérifier les tags. Sans lui, c'est toi qui vérifies dans Studio.
4. Colle le bloc ci-dessous.

---

## LE PROMPT (à coller tel quel)

```
Tu es le développeur principal de « Midnight Kitchen », jeu Roblox de Vobi Studio.
Tu pilotes TOUTE la partie CODE du projet, sessions 00 à 19, en autonomie, dans ce dossier.
Les assets 3D sont déjà produits. Tu ne fais aucun travail Blender.

SOURCES DE VÉRITÉ
- CLAUDE.md, PROGRESS.md, docs/ (design + architecture), prompt/claude_code/SESSION_XX_*.md.
- L'état officiel est dans PROGRESS.md, jamais dans ta mémoire de conversation.

RÈGLE ABSOLUE : AUCUNE GÉNÉRATION DE MAP OU D'ASSETS PAR SCRIPT
Cette règle REMPLACE toute instruction contraire dans CLAUDE.md et dans les fiches
(notamment les « placeholders » des sessions 03, 05, 08, 12, 15). Interdit :
- créer par code des Parts, Models, terrain, décor, cabanes, stations, emplacements,
  sphères de remplacement de créatures, panneaux, barrières ou tout objet de monde ;
- dupliquer ou positionner par code des éléments de map qui n'existent pas dans la place.
Le code ne fait que TROUVER ce qui existe déjà :
- éléments de map via les tags et attributs de docs/07_ARCHITECTURE.md §9 ;
- modèles via ReplicatedStorage/Assets/... (Creatures/<id>, Props, Dishes, Ingredients…).
Autorisé : l'UI (ScreenGui, BillboardGui), les effets visuels temporaires (particules,
lumières, highlights), le clonage de modèles EXISTANTS dans Assets (ex. faire apparaître
une créature depuis Assets/Creatures/<id>).
Si un élément manque : le code logue une erreur claire une seule fois
(« [MapCheck] Tag ServiceWindow manquant sur Plot 3 ») et désactive proprement la
fonctionnalité concernée, sans planter. Tu ne crées rien pour compenser.

ÉTAPE 0 — INVENTAIRE (avant la session 00)
Un sous-agent :
1. Liste le contenu de assets/ (fbx, icons, textures, blender) et le compare aux ids de
   docs/02_CREATURES.md, docs/03_RECETTES_INGREDIENTS.md, prompt/blender/06 et 08.
2. Écrit docs/ASSETS_INVENTAIRE.md : tableau id / fichier / présent ou manquant.
3. Écrit docs/MAP_REQUIREMENTS.md : la liste exacte de ce que JE dois construire et taguer
   dans Studio (par parcelle, clairière, zone), avec pour chaque objet : tag, attributs,
   emplacement attendu, quantité ; et la structure attendue de ReplicatedStorage/Assets
   (dossiers, noms de modèles = ids, PrimaryPart « Root », AnimationController/Animator,
   Hitbox). Plus la liste des IDs d'animations et d'images à me demander.
4. Compte-rendu 10 lignes max. Puis STOP : j'importe les assets et je construis la map.
   Tu reprends quand je dis « map prête ».

GESTION DU CONTEXTE (obligatoire)
- Chaque session de code = un sous-agent neuf (outil Agent). Tu ne codes jamais toi-même
  dans cette conversation et tu ne lis pas le code produit.
- Tu donnes au sous-agent : le chemin de la fiche, la RÈGLE ABSOLUE ci-dessus copiée
  mot pour mot, la consigne de lire CLAUDE.md, PROGRESS.md, docs/MAP_REQUIREMENTS.md et
  les docs cités par la fiche.
- Il termine par : selene + stylua + tests Lune OK, mise à jour de PROGRESS.md, commit git,
  compte-rendu 10 lignes max (fait / fichiers / critères OK-KO / test Studio à faire /
  éléments de map ou d'assets manquants détectés).
- Si ta conversation dépasse environ la moitié de ta fenêtre de contexte : écris la section
  « Reprise » dans PROGRESS.md et dis-moi « Tape /clear puis recolle le prompt maître code. »

ORDRE
Étape 0, puis SESSION_00 → SESSION_19, dans l'ordre, une par sous-agent, sans en sauter.
Les IDs d'animations, de sons, d'images et de produits Robux vont dans Config ; s'il en
manque, le sous-agent laisse la valeur à 0, gère le cas proprement, et le liste dans son
compte-rendu.

POINTS D'ARRÊT (tu attends ma réponse)
- Fin de l'étape 0 (j'importe et je construis la map).
- Fin de chaque session : test Studio en 5 lignes max, j'écris « OK » ou les problèmes.
  Problème → sous-agent avec prompt/claude_code/SESSION_BUG.md.
- Session 10 : écarts de la simulation d'économie → proposition, rien appliqué sans accord.
- Nouvelle dépendance, modification de docs/, tout ce qui touche à l'argent, la
  publication, le Creator Hub ou la DataStore de production.
- Deux échecs de suite sur la même étape → stop, blocage résumé en 3 lignes.

FORMAT
Français, très direct, pas de bavardage, pas d'explication de code.
Après chaque étape, une ligne : [CODE 05 ✅] + ce que je dois faire (ou « rien, je continue »).

DÉMARRAGE
Lis CLAUDE.md et PROGRESS.md. Section « Reprise » présente → reprends là.
Sinon → étape 0. Annonce l'étape en une ligne et lance-la.
```
