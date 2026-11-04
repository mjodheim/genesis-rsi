# CIRCUIT2 — note de résultat négatif

Note générée mécaniquement à partir de `results/circuit2_adjudication_full.json`, du plan gelé et de `results/circuit2_provenance.json` (lecture seule).

## Paramètres lus dans le fichier

- scale : "full"
- task_budget : 16
- plan_digest : "d6ddfbe570364b0c8df9c46ae979547a61bda327a77ba3a1363a8e3493ac1ad4"
- machinery_commit : "c993a2f4db97e20b109da0a230eb9658a37a0eb5"

## Données par bras

### Bras fixed_procedure

- Nombre de lignes : 20
- held_out_yield (ordre du fichier, null si absent) : [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
- stop_reason (ensemble) : generation_limit
- Empreintes de bibliothèque distinctes : 1 (préfixes : 03922f7a)

### Bras frozen_engine

- Nombre de lignes : 20
- held_out_yield (ordre du fichier, null si absent) : [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
- stop_reason (ensemble) : generation_limit
- Empreintes de bibliothèque distinctes : 1 (préfixes : 03922f7a)

### Bras inherited_lineage

- Nombre de lignes : 20
- held_out_yield (ordre du fichier, null si absent) : [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
- stop_reason (ensemble) : generation_limit
- Empreintes de bibliothèque distinctes : 1 (préfixes : 03922f7a)

### Bras random_procedure

- Nombre de lignes : 20
- held_out_yield (ordre du fichier, null si absent) : [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
- stop_reason (ensemble) : generation_limit
- Empreintes de bibliothèque distinctes : 3 (préfixes : 03922f7a, 223505bd, e68ac1b1)

## (a) Résultat négatif

Critère préenregistré, lu dans le plan gelé — seuils : {"ablation": "initial procedure restored, gain must disappear", "final_vs_fixed_points": 10, "final_vs_random_points": 10, "min_seeds_won": 16, "of_seeds": 20, "successive_transitions": 2, "transition_points": 5}.

Texte du critère : succès seulement si la procédure finale gagne au moins 10 points de rendement contre la procédure fixe et contre l'aléatoire ; si deux transitions successives de procédure gagnent chacune au moins 5 points à bibliothèque initiale identique ; si chacune de ces comparaisons gagne dans au moins 16 graines sur 20 ; et si le gain disparaît sous ablation (procédure initiale restaurée). Sinon échec publié. Aucun critère n'est modifiable après gel.

Aucun gain : tous les rendements held_out_yield calculés sont nuls. Le critère préenregistré n'est pas atteint.

## Provenance

Sources : `results/circuit2_provenance.json` (campagne complète et pilote) et `results/circuit2_provenance_adjudication_full.json` (adjudication complète). Tout ce que ces relevés n'établissent pas est marqué « non vérifié ».

- `results/circuit2_campaign_full.json` : commit résolu "245661e0c8d0f2668f74a3f637f22141cae46fd1", verdict "ancetre_de_head" ; comptes non comparés (fichier non lu en entier), non vérifié
- `results/circuit2_adjudication_s0-1_g6.json` : commit résolu "e60a37e1913dc95841777570fbdc00a438477e9f", verdict "ancetre_de_head" ; pilote (nom et commit connus seulement par la provenance), contenu non relu ici
- `results/circuit2_adjudication_full.json` : machinery_commit lu dans le fichier "c993a2f4db97e20b109da0a230eb9658a37a0eb5" ; commit résolu "c993a2f4db97e20b109da0a230eb9658a37a0eb5", verdict "ancetre_de_head" (relevé complémentaire `results/circuit2_provenance_adjudication_full.json`) ; concordance valeur / commit_resolu / machinery_commit contrôlée
- machinery_commit du plan (lu dans le plan) : "245661e0c8d0f2668f74a3f637f22141cae46fd1"
- Digest du plan : "d6ddfbe570364b0c8df9c46ae979547a61bda327a77ba3a1363a8e3493ac1ad4", égal au plan_digest de l'adjudication ; recalcul du digest : non vérifié

## (b) Limites

- Identité du code entre les commits cités dans la section provenance : non vérifié.
- État de la CI : non vérifié.
- `results/circuit2_campaign_full.json` : non relu en entier ; comptes non comparés, non vérifié.
- Recalcul du digest du plan : non vérifié (égalité des champs seulement).
