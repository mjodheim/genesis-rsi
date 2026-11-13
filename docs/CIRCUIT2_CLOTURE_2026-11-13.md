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
Elles ne sont pas présentées ici comme des résultats de tests exécutés.
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

Le journal atteste une tentative de patch conservée sans commit et un
lancement interrompu à la création du conteneur, avec un code de sortie 125.
Les assertions Python n'ont pas été validées par ce lancement.
Aucun refus de chemin n'a été obtenu par exécution.

Le nombre et les chemins des correspondances de l'ancien échec restent
inconnus dans les preuves fournies. Aucun test réussi ni PR produite n'est
actuellement attesté. La vérification restant à effectuer, hors réseau via
le lanceur habituel, se limite à une seule relance des deux fichiers :
`pytest tests/test_circuit2_full_descriptive_counts.py tests/test_circuit2_full_descriptive_counts_committed.py`.
La réussite exige un conteneur démarré, la collecte attestée des deux fichiers,
tous les tests réussis et une sortie 0. Aucun succès actuellement établi.

Aucune relance n'est effectuée dans cette proposition de diff, conformément
à la consigne de ne recourir à aucun outil ni exécution. Cette vérification
reste donc en attente, sans expérience ni modification de Docker.
Si l'erreur Docker revient lors de cette unique relance, conserver les preuves
sans commit ni PR, puis signaler le blocage d'infrastructure à Anthony.
Aucun signalement à Anthony n'est attesté ici.
