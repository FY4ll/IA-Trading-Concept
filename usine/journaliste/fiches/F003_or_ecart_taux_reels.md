# F003 — L'or revient-il vers sa « valeur » donnée par le taux réel et le dollar ?

Fournée 1 (20/10/2026) — journaliste. Statut : proposée. Risque de déjà-vu : **élevé** (mêmes séries FRED que I008 /
I020 / I004 ; seule la façon de les lire et l'horizon changent).
Marché FTMO : **XAUUSD**.

## 1. Hypothèse
Quand l'or est nettement au-dessus (au-dessous) du prix « expliqué » par le taux réel américain à 10 ans et le dollar,
il fait moins bien (mieux) que d'habitude sur les 20 à 60 jours de Bourse suivants : l'écart se referme.
Signal principal (un seul) : écart = reste d'une régression glissante sur 3 ans du logarithme de l'or sur le taux réel
10 ans et le dollar ; en nombre d'écarts types ; vente si > +1,5, achat si < -1,5 ; sortie à 0 ou après 60 jours.

## 2. Mécanisme
- L'or ne rapporte rien : son coût d'opportunité est le taux réel (obligations indexées sur l'inflation). Les gérants
  « macro » arbitrent lentement entre les deux ; un écart né d'un afflux passager (peur, achat d'un fonds) devrait se
  refermer quand l'afflux cesse.
- Pourquoi pas arbitré : l'arbitrage est risqué (la relation peut casser) et lent (semaines), donc peu de capital s'y
  engage ; les limites à l'arbitrage laissent des écarts durer.
- **Contre-argument fort, à dire tout de suite** : la relation s'est **cassée depuis 2022** (taux réels en forte hausse
  ET or en hausse, achats des banques centrales). Une régression glissante s'adapte, mais pendant la cassure le signal
  aurait dit « vendre » pendant des mois. C'est exactement ce que le test doit montrer.

## 3. Donnée
| point | détail |
|---|---|
| source | FRED (Banque fédérale de St. Louis) : **DFII10** (taux réel 10 ans), **T10YIE** (inflation attendue 10 ans), **DTWEXBGS** (dollar large) — https://fred.stlouisfed.org |
| historique | DFII10 et T10YIE 2003 ->, DTWEXBGS 2006 -> |
| **date de publication** | DFII10 / T10YIE : publication H.15, valeur du jour d connue le jour ouvré suivant (fin d'après-midi New York) -> utilisable à **d+1 clôture**. **DTWEXBGS : publication H.10 HEBDOMADAIRE (le lundi, pour la semaine précédente) -> jusqu'à 7 jours de retard.** Plus simple et plus sûr : remplacer le dollar large par un panier dollar fait avec nos prix de devises locaux (connus en temps réel). Révisions : rares sur ces séries ; à défaut de première publication (ALFRED), décalage prudent déclaré. |
| gratuit et légal | oui (FRED, usage libre ; GVZ appartient à la CBOE, non utilisé ici) |
| présent dans `data/` | **OUI** : `data/maitres/fred/DFII10.csv`, `T10YIE.csv`, `DTWEXBGS.csv` (téléchargés le 19/10/2026). Rien à télécharger. |

## 4. Pourquoi ce n'est pas déjà au registre
- **I008** (cerveau macro FRED, or à 10 jours) : niveaux et variations comme entrées d'un modèle, horizon 10 jours,
  pouvoir de tri 0,48-0,52. **I020** (test d'information) : taux réel en variation 5 / 20 jours et niveau classé sur
  1 an, horizons 1 et 5 jours : rien de stable. **I004** (style H1X) : 17 variables hors or dans une IA, horizon de
  la bougie.
- Différence précise : ici on lit **l'écart de l'or à sa relation** (pas le niveau ni la variation d'une variable), et
  à **20-60 jours** (horizon jamais testé avec ces séries). Si le scientifique juge que cette différence ne suffit pas,
  la fiche est à rejeter : c'est la plus fragile de la fournée.

## 5. Ce qui la réfuterait — ordre de grandeur — frais
- **Réfutation 1** : force < 2 sur 2006-2015 (choix) ou signe inverse sur 2016-2021 -> morte. Contrôle 2022-2023 :
  si le signal perd plus que l'acheteur permanent pendant la cassure, le noter comme limite de fond.
- **Réfutation 2** : l'écart n'apporte rien de plus que « l'écart de l'or à sa moyenne 200 jours » (prix seul, déjà
  ~0 dans I020) -> ce n'est que du retour à la moyenne du prix -> morte.
- **Réfutation 3** : peu de trades indépendants (horizon long) : sur 2006-2023, au plus ~100-200 trades. Si
  l'incertitude reste plus grande que l'effet espéré, conclure « non mesurable » et ne pas insister.
- Ordre de grandeur publié : Erb et Harvey (« The Golden Dilemma », Financial Analysts Journal, 2013) montrent un lien
  fort EN NIVEAU entre or et taux réels sur 1997-2012 ; **aucun gain de trading publié** trouvé sur l'écart.
- Frais FTMO : ~0,02 % + nuits ~3 %/an x 20-60/365 ≈ 0,16-0,49 % -> **~0,2-0,5 % par trade**. L'or bouge de ~4-7 %
  sur 20-60 jours : il faut un avantage moyen de 0,3-0,5 % par trade. Trades rares : risque d'inactivité FTMO (30 jours
  sans ouvrir) -> à associer à autre chose si elle survit.
