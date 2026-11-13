# Circuit2 — clôture du jalon 1 — 2026-11-13

L'hypothèse est clôturée négativement dans le moteur de circuits, dans le
périmètre des données committées. Un résultat constant est un résultat négatif
conservé, pas une anomalie à corriger. Cette clôture ne démontre pas une
impossibilité générale.

## Comptages à contrôler sur les JSON committés

- 20 graines × 4 bras × 6 générations.
- 80 couples bras/graine exacts, avec rendement tenu à l'écart nul.
- 100 transitions héritées.
- 0 changement de library_digest.
- 0 changement de procedure_digest.
- Relevé budget 16 : 2 candidats et 0 admis.

Les sources canoniques sont :

- `results/circuit2_campaign_full.json` pour les graines, bras, générations
  et transitions des deux digests.
- `results/circuit2_adjudication_full.json` pour les 80 lignes, l'identité
  exacte des couples bras/graine, six générations par ligne et
  `held_out_yield` nul sur chaque ligne.
- `results/circuit2_budget16_stdout.json` pour `parametres.budget` égal à 16,
  `etape_a.candidates` égal à 2 et `etape_a.admitted` égal à 0.

Dans l'extrait de campagne fourni, `score[1]` vaut -137 ; il ne représente
pas `held_out_yield`. Le rendement nul doit être contrôlé dans l'adjudication.

Ces valeurs constituent les assertions du test
`tests/test_circuit2_full_descriptive_counts_committed.py`.
Leur validation locale est consignée ci-dessous.
Le contrôle doit échouer si les données manquent, sont ambiguës ou divergent.

## Portée et réorientation

La base observée est e2546a18. Les champs machinery_commit des relevés sont
des références historiques distinctes ; leur provenance n'a pas été vérifiée.

Dans ce périmètre, l'amélioration de l'améliorateur n'est pas montrée dans
le moteur de circuits. Cette hypothèse est fermée ; ce constat motive la
réorientation vers la capacité de programmation de Mira : produire,
modifier et vérifier des programmes. Celle-ci constitue une nouvelle direction,
sans succès expérimental revendiqué ici. Aucun rejeu expérimental, aucune
reprise de #472, aucune modification des résultats, protocoles scientifiques
gelés ou critères associés.

## Validation locale et publication

État consigné le 13 novembre 2026 : une tentative historique de lancement
a été interrompue à la création du conteneur, avec un code de sortie 125.
La date exacte de cette tentative n'est pas fournie dans l'extrait du journal.
Elle n'a pas validé les assertions Python.

Une vérification ultérieure hors réseau de la copie courante est attestée par
la preuve `8812dac5ac86486a9229ec93d588e84a` : sortie 0, classement
`success`, six tests réussis en 0,33 seconde, pour les deux fichiers
`tests/test_circuit2_full_descriptive_counts.py` et
`tests/test_circuit2_full_descriptive_counts_committed.py`.
Cette vérification n'a effectué aucun commit ni publication et précède
la présente correction ; elle ne valide pas cette correction par anticipation.

La PR https://github.com/mjodheim/genesis-rsi/pull/473 est attestée par
la relecture fournie au commit `b2c859be55fbfeb0b22fa70ae195cccb97d5e0ba`.
Cette relecture demande des corrections. Aucun état vert de la CI ni fusion
n'est attesté dans les éléments disponibles.
