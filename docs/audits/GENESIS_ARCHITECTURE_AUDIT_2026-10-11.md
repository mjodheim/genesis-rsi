# Audit architectural et scientifique de Genesis RSI

Date : 11 octobre 2026. Diagnostic préparé avec l'assistance d'OpenAI Codex pour examen par Leona (ChatGPT), qui dirige cet audit et assurera les décisions architecturales et scientifiques. Aucune décision d'implémentation ou de campagne n'est prise ici.

## 1. Verdict et décision proposée

**Genesis possède des mécanismes opérationnels de recherche bornée, d'acquisition de règles, de persistance et de validation causale. Les preuves examinées ne démontrent pas une amélioration récursive cumulative générale, ni une amélioration durable du réparateur sur projets réels.** Le principal résultat positif de récursion, G10, concerne exactement un assay synthétique dont les familles de transitions sont écrites par le projet. Les résultats négatifs ultérieurs ne l'annulent pas ; ils en exposent la faible validité externe.

**Recommandation : conserver le socle de preuve et d'exécution, simplifier fortement le périmètre actif, et envisager une reconstruction ciblée du cœur de recherche seulement après décision de Leona.** Déplacer les fichiers dans sept répertoires ne résoudrait pas le manque de transformations pertinentes, le faible transfert des apprentissages, ni les problèmes de mesure. Une réécriture totale détruirait inutilement des garanties utiles ; garder toutes les couches comme cœur actif conserverait une complexité sans bénéfice démontré.

Le projet n'est pas « incapable d'apprendre ». Il apprend notamment des templates et des bibliothèques de composants. Ce qui manque est une preuve que cet apprentissage améliore régulièrement la production des apprentissages suivants, sur des tâches suffisamment différentes et à coût total comparable.

## 2. Périmètre, méthode et limites

### 2.1 Snapshot et contraintes respectées

- Branche de travail : `audit/genesis-architecture`, propre au début de l'audit.
- HEAD examiné : `72af3e9a3eddcdbdbce1059572d9aa257a45234b`.
- Consultation supplémentaire, **en lecture seule dans Git**, de CIRCUIT2 sur `research/learning-to-improve` : code/protocole à `f6c24fee4b81612018ad47b2419a5c5d2f59a6d7`, résultat à `e72d1aa108b168c085696da377413dda7f520be0`, commentaire corrigé à `1c2bfdfa8fcb0f99f7ed71c8c9a37d747fcd5bb9`. Ces éléments ne sont pas présents dans l'arbre de la branche d'audit et n'ont pas été intégrés.
- Aucun appel réseau, OpenRouter, Codex imbriqué ou autre service ; aucune installation, construction d'image, campagne, nouveau benchmark ou exécution de candidat.
- Aucun code de production, protocole gelé, résultat historique, service ou donnée modifié. Seul ce rapport est ajouté ; aucune fusion, aucun changement de branche, aucun commit ou push réalisé par l'audit.

Les règles de publication, le registre IP, la stratégie de double licence et les documents de provenance/contribution ont été consultés. La cible proposée reste un découpage architectural de mécanismes déjà publics, sans nouvelle implémentation habilitante. Les résultats M085 ne sont pas remplacés par cet audit ; M086-A reste disqualifié. Les origines assistées ne deviennent pas des inventions endogènes par simple rétention.

### 2.2 Niveau de vérification

L'audit croise inventaire statique, fonctions déterminantes, appels et imports, protocoles, JSON de résultats et histoire Git. Il couvre les principales lignées et leurs frontières, **pas une lecture ligne par ligne de tout le dépôt**, ni une certification de sécurité, de licences transitives ou de reproductibilité intégrale.

Les labels employés sont :

- **[V] Vérifié** : constat directement lisible dans le code ou recalculé sur les artefacts disponibles.
- **[R] Résultat archivé** : mesure enregistrée, examinée mais non reproduite par de nouvelles exécutions.
- **[H] Hypothèse** : explication plausible ou effet attendu d'une recommandation.
- **[ND] Non démontré** : conclusion plus large que les preuves disponibles.

La vérification locale a recalculé, avec `json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=False)` et SHA-256, **21 empreintes de documents** : résultats G5–G9, chaîne G10 et ses trois étapes, plans SELF1/SELF2, six générations SELF, plan/résultat CIRCUIT1, plan/résultat CIRCUIT2 lu dans Git. Les 21 correspondent. Ce contrôle établit la cohérence du contenu avec son empreinte, **pas l'authenticité de l'auteur, la réalité de chaque mesure, ni l'indépendance scientifique**.

Pas de suite pytest générale : plusieurs tests historiques peuvent recalculer des expériences ; elle n'est pas nécessaire pour un ajout documentaire. Aucun checker expérimental n'a été exécuté. Aucun secret, fichier d'environnement privé ou contenu de réserve scellée n'a été lu. Les suites externes, journaux complets et bases SQLite de campagne ne sont pas tous présents dans le dépôt ; leur disponibilité et leur replay restent à vérifier séparément, sans campagne nouvelle.

## 3. Architecture réellement présente

### 3.1 Plusieurs systèmes sous un même nom

**[V]** L'inventaire statique de `genesis/**/*.py` donne **167 fichiers Python, 41 828 lignes**, dont **123 fichiers directement sous `genesis/`**. Les 123 modules/33 560 lignes cités dans `docs/GENESIS_REORIENTATION_2026-10-11.md` ne sont donc pas un inventaire récursif équivalent du package actuel. Le nombre de lignes n'est pas une mesure de capacité.

| Ensemble | Points d'entrée et fonctions examinés | Fonction réelle et limite |
|---|---|---|
| Runtime historique de lignée | `genesis/loop.py`: `Genesis`, `ablation_supports_causal_dependency`; `controller.py`: `World`, `run`; `state.py`: `decode_state`, `extend_components`, `extend_vocabulary` | Exécuter des corps/propositions et adopter des états sous contrat. Les mondes, corps et opérations disponibles sont fournis ; ce n'est pas un agent général autonome. |
| Gouvernance et preuve | `trust_root.py`: `Budget`, `evaluation_contract`, `decide`, `verify_verdict`; `journal.py`: `Journal`, `verify`; `evolution/lineage_promotion.py`: `ComponentLineageStore` | Comparaison, identités, persistance et adoption. L'indépendance dépend du déploiement et du caller autorisé, pas du seul digest. |
| Fondation G1–G10 | `languages/substrate.py`, `operators/universal.py`, `core/self_model.py`, `evolution/experiment_design.py`, `component_evolution.py`, `successor_generation.py`, `recursive_chain.py` | Suite de mécanismes composables mais fortement spécialisés par leurs protocoles. Les profils G9/G10 s'exécutent via des executors dédiés. |
| Réparateur sans modèle | `repair_strategist.py`: `generate`, `_family_candidates`, `_compose_plans`; `repair_ir.py`: `RepairPlan`, `compose`, `render_candidate` | Agrégation de mutations Java/scalaires, classement et compositions bornées ; vocabulaire majoritairement écrit à la main. |
| Validation de vrais projets | `repair_bench.py`: `build_split`, `Candidate`; `defects4j_sandbox.py`: `Defects4JSandbox`; `real_project.py`: `validate_manifest`, `run_gate` | Exécution et verdict sur checkout/test réels. Un passage de suite prouve la plausibilité selon cette suite, pas l'équivalence au correctif humain. |
| Réparation assistée et mémoire | `repair_proposers.py`: `model_proposer`, `strategist_proposer`; `openrouter_repair.py`: `openrouter_proposer`; `adaptive_repair.py`: `RepairExperience`, `EconomicRouter`, `solve_development` | Modèle externe pour les idées de réparation ; réutilisation, routage et validation locaux. Le modèle n'est pas entraîné par ces couches. |
| Apprentissages de réparation | `learning/self_extension.py`, `g12_operator_lab.py`, `g12_training_bank.py`, `repair_*_learning.py` | Plusieurs formats de règles, recettes et politiques, avec des usages et critères distincts ; aucune preuve qu'ils forment une boucle cumulative unique. |
| V2/V2.1 de réparation | `v2/discovery.py`: `evolve_in_training`, `retrospective_study`; `v2/genome.py`: `neighborhood`; `v2/semantic_dsl.py`: `propose`, `compile_hypothesis` | Mutation de poids de classement ; hypothèses Java dans une grammaire étroite. « V2 » désigne ici une autre surface que la fondation G1–G10. |
| SELF | `improver_seed.py`: `improve`; `improver_runtime.py`: `evaluated`; `improver_lineage.py`: `run_improver`, `score`, `compared`, `promoted` | Réécriture de procédures qui appellent un modèle fixe ; évaluation imbriquée coûteuse. Aucun descendant promu dans SELF1/SELF2. |
| CIRCUIT | `circuit_engine.py`: `solve`, `proposals`, `refitted`, `improved`; `circuit_tasks.py`; `scripts/run_circuit_lineage.py`: `one`, `summarised` | Synthèse NAND et apprentissage de macros sans modèle ; progression limitée par recherche et distribution. CIRCUIT2 ajoute ailleurs un ranker linéaire appris. |

**[V]** Les sept packages de `ARCHITECTURE.md` ne contiennent pas sept systèmes cognitifs aboutis : `core/__init__.py` expose surtout `self_model`, `memory/__init__.py` expose `strategy`. Les fichiers plats `failure_driven_self_extension.py`, `structural_operators.py`, `candidate_scheduler.py`, `native_diagnosis.py`, `language_toolchains.py` sont des alias par `sys.modules` vers des modules canoniques. Ce sont des doublons de surface, **pas cinq implémentations indépendantes à supprimer**.

**[V]** Le couplage est concentré autour du socle : 117 occurrences d'import explicite de `genesis.trust_root` dans l'analyse AST, 13 de `repair_bench`, 12 de `sandbox`, 12 de `artifacts`, 11 de `loop`. Ce sont des occurrences syntaxiques, pas un graphe transitive complet : les imports relatifs, dynamiques et `from genesis import ...` demandent une résolution supplémentaire. Le code historique `metamorphosis/` et `mira_core/` reste distribué par setuptools ; son ancienneté n'établit pas son inutilité.

### 3.2 Représentation et compréhension

**[V]** `languages/substrate.inspect_source` utilise l'AST Python pour Python, mais une structure lexicale heuristique pour les autres familles de base. `languages/understanding.py` distingue explicitement cette fidélité d'un `JavaCompilerModule` optionnel, qui expose syntaxe, types, symboles, appels et accès via le JDK, avec une qualité sémantique partielle et parfois des erreurs de compilation. Six familles reconnues ne signifient donc pas six frontends sémantiques équivalents.

**[V]** `operators/universal.py` matérialise des opérations sur tokens et rôles structuraux. Le G6 modifie `_anchor_matches` ; il ne remplace pas le substrat par une analyse interprocédurale. `operators/structural.synthesize_operator` apprend des hunks et captures depuis un couple avant/après, puis impose le replay exact. C'est utile, mais les préconditions comportementales ne sont pas apprises par ce replay.

**[H]** L'absence d'une représentation commune suffisamment riche des effets, états, contrats et dépendances explique une partie du transfert faible. **[ND]** Ajouter un AST ou un graphe de types suffirait à découvrir les correctifs : les données V2.1 et l'intervention de localisation ne le montrent pas.

### 3.3 Le self-model n'est pas une théorie causale apprise

**[V]** `core/self_model.py` part de `_COMPONENT_SPECS`, un catalogue écrit à la main de rôles, entrées/sorties, classes de défaillance et mutabilité. Il lie ces descriptions aux octets du code. `learning/failure_model.diagnose` utilise des scores heuristiques et sait répondre `underdetermined`. `evolution/experiment_design.design_experiment` croise des composants candidats et interventions disponibles ; evaluator, identifiant de nouvelles tâches et budget sont fournis par l'appelant.

Ces mécanismes automatisent de la sélection et de la documentation sous vocabulaire donné. **[ND]** Ils découvriraient seuls les bons objets à modifier ou concevraient une expérience entièrement nouvelle sans définition humaine du problème et du juge. Le diagnostic interventionnel du 10 octobre est particulièrement important : des taux observationnels avaient nommé le localizer, puis la comparaison contrôlée n'a pas confirmé cette attribution.

## 4. Registre des preuves G5 à G12

Les termes « indépendant », « frais » et « externe » sont distingués : un évaluateur séparé du candidat peut rester contrôlé par le projet ; une nouvelle fixture peut rester issue du même générateur ; Defects4J est un projet externe mais n'exclut pas une exposition dans l'entraînement d'un modèle.

| Étape | [R] Résultat archivé | [V] Ce que le code automatise | Conclusion autorisée ; frontière |
|---|---|---|---|
| G5 | C# scellé : meilleur mécanisme 5/6 ; parent 0/6 ; ablation 0/6 ; zéro appel modèle | `design_experiment` produit un plan à partir du diagnostic/self-model et d'interventions disponibles | Un choix d'expérience interne est utile sur ce petit holdout. Pas une découverte scientifique ouverte ni un réparateur C# général. |
| G6 | Parent 2/8, descendant 8/8 ; réversion 2/8 ; succès parent conservés | `_candidate_functions` fournit trois corps de matcher ; `generate_descendants` remplace `_anchor_matches`; `evolve_component` sélectionne sur preuves antérieures | Modification réelle de source et causalité locale. Les trois alternatives, dont le gagnant `structural_delimiter_anchors`, sont préécrites. |
| G7 | 17 prédicats satisfaits ; rejet sans changement d'état ; rollback exact ; promotion après reprise ; quatre sondes de falsification | Store adressé par contenu, décisions et journal, pointeur actif | Bonne capacité de gouvernance et reprise. Aucune nouvelle capacité de réparation ou autorité indépendante humaine créée par le store. |
| G8 | Cinq traces antérieures → six règles ; holdout : spécialiste 8/8 sans modèle, baseline Claude 7/8 avec huit appels et coût historique 0,2300264 USD ; ablation 0/8 | `distill_local_specialist`, `generate` compilent/réutilisent les templates | Distillation opérationnelle et économie à l'inférence sur familles apparentées. Coût d'acquisition initial non nul ; aucune preuve d'apprentissage de poids ou de généralité. |
| G9 | Parent 4/12, successeur 12/12 ; sans G6 8/12, sans G8 8/12 ; zéro appel modèle | Profils et overrides G6/G8 assemblés par `successor_generation`, exécutés par `profile_executor` | Assemblage causal de deux gains compatibles dans l'assay. Un successeur ne démontre pas une récursion ouverte. |
| G10 | Trois étapes : 2/6→6/6, 4/8→8/8, 6/10→10/10. Découverte suivante : G1/G0 4/4 vs 0/4 en 4 vs 16 exécutions ; G2/G1 4/4 vs 0/4 en 8 vs 20 | `induce_successor` active composition de paires, liaison de portée, puis itération de portées ; executor dédié | Gain de production des successeurs dans l'assay gelé : preuve positive bornée. Familles de mécanismes host-authored, pas invention ouverte ; code plafonné à trois générations. |
| G11 | Codec-15 et Compress-6 initiaux : aucun correctif valide dans top-8. Trois lots prospectifs de trois bugs : 0/9. Compress-6, Math-53, Csv-16 : succès de développement posthoc distincts | Génération Java, focus, composition, classement, préflight et extensions optionnelles | Les succès connus ne compensent pas les échecs frais. La sélection de fichiers et la validité de compilation ne sont pas une capacité de réparation démontrée. |
| G12 | Deux projets déjà exposés : Compress-6 et Math-53 passent les suites, chacun donne un template retenu ; aucun nouveau succès holdout | `freeze_training_search`, `validate_and_learn`, banque contrôlée, replay et réservation de slots | Induction automatique de règles depuis des correctifs validés, avec ordre de preuve. Les idées sémantiques génératrices étaient ajoutées par assistance après examen des bugs. |

Sources primaires : `experiment/g5_qualification/RESULT.json` à `g9_qualification/RESULT.json`, `experiment/g10_qualification/CHAIN_RESULT.json` et `stage*/{RESULT,DISCOVERY_RESULT,SUCCESSOR,PREREGISTRATION}.json`. Explications : `docs/G5_QUALIFICATION_2026-10-07.md` à `docs/G10_QUALIFICATION_2026-10-07.md`. G11 : `G11_CODEC15_RESULTS_20261008.json`, `G11_COMPRESS6_RESULTS_20261008.json`, `G11_3REPO_RESULTS_20261008.json`, `G11_SECOND_BATCH_RESULTS_20261008.json`, `G11_THIRD_BATCH_RESULTS_20261008.json` dans `experiment/g11/`. G12 : `experiment/g12/G12_DEVELOPMENT_REPORT_20261008.md`, les deux manifests/résultats et `G12_TRAINING_OPERATOR_BANK_20261008.json`.

### 4.1 Pourquoi G10 ne constitue pas un moteur général de récursion

**[V]** `evolution/recursive_chain.validate_profile` n'accepte que les niveaux 0, 1, 2, 3. `induce_successor` appelle successivement `_level0_to_level1`, `_level1_to_level2`, `_level2_to_level3`, puis lève une erreur de plafond. Les preuves sélectionnent/instancient ces transitions ; elles ne synthétisent pas leurs algorithmes.

**[V]** `runtime/recursive_chain_executor.py` contient les routes `_global_pair_candidates`, `_scope_pair_candidates`, `_iterated_scope_candidates`, puis `generate_candidates`. La lignée hérite de flags et de templates adressés, tandis que l'hôte possède le code qui sait exécuter chaque nouvelle étape. C'est un apprentissage réel dans une métagrammaire finie, pas une extension autonome de cette métagrammaire.

**[H]** L'alignement entre blocs de tâches et capacités disponibles rend les ablations particulièrement lisibles, mais rend aussi le résultat plus facile à obtenir qu'un gain sur une population ouverte de bugs. **[ND]** Cela invaliderait G10 : non. La conclusion correcte est la conclusion bornée du protocole, en préservant le résultat positif.

### 4.2 Ce que G11/V2.1 révèle de l'espace de recherche

**[R]** `experiment/g12/REPAIR_SEARCH_SPACE_DIAGNOSIS_20261008.md` et son JSON d'audit recensent 14 cas déjà ouverts, dont trois avec opérateurs ajoutés posthoc. Sur les 11 autres : 9 239 candidats générés, fichier corrigé dans le focus de 10/11 cas, candidat touchant les lignes du correctif dans seulement 1/11, aucun correctif humain exact. 97 % des 1 873 mutations atomiques proviennent de `scalar`, `java_structural`, `java_symbol`.

**Prudence essentielle :** l'absence du correctif humain exact n'est pas une preuve qu'aucun correctif équivalent n'existe ; l'absence d'édition sur les mêmes lignes n'est pas une preuve d'impossibilité sémantique. Ce recensement est borné par les familles, caps, focus et compositions de l'outil. Il étaye un déficit de couverture, **pas une démonstration exhaustive d'insolubilité**, ni un plafond universel de 1 %.

**[V]** `repair_strategist.generate` associe limites par famille, poids manuels et composition bornée. Les familles centrales ne construisent pas un programme arbitraire depuis le test échoué. La politique atomique optionnelle peut faire remonter un patch existant, mais ne crée pas une transformation absente.

**[R]** V2 apprend cinq poids bornés (`atomic`, `source_evidence`, `non_modifier`, `rare_source`, `semantic_operator`) par mutations ±1. Le développement améliore la compilation 16/24→21/24, répare zéro défaut et régresse sur un projet ; `v2/gates.assess_development` interdit la promotion. V2.1 propose avant validation des gardes Java dans une grammaire donnée ; son Math-53 positif est exposé. Sur Chart-23, JacksonXml-4, Mockito-22 frais : 0/3 ; après correction transparente du validateur Mockito, 23/24 compilent dans chaque bras, index candidats identiques et zéro hypothèse sémantique nouvelle. Sources : `experiment/v2/README.md`, `V21_FRESH_3PROJECT_RECONCILED_AUDIT_20261008.json` et rapport associé.

**Conclusion :** la capacité de reclasser est opérationnelle ; la capacité à fournir des hypothèses pertinentes sur ces nouvelles formes de bug ne l'est pas de manière démontrée. Augmenter seulement le budget ou la compilation ne ferme pas cette différence.

## 5. SELF1 et SELF2 : l'objet peut changer, le signal manque

**[V]** Le seed `improver_seed.improve(task, lm, budget)` propose avec un modèle, évalue et garde seulement un meilleur score. Son propre source peut être la cible. Le modèle écrit les descendants ; le host borne les appels et recalcule la qualité en conteneur distinct. La capacité modifiable est la procédure d'usage du modèle, pas ses poids.

| SELF1, génération | [R] Moyenne parent | Moyenne candidat | Victoires / pertes | p, test des signes gelé | Promotion |
|---|---:|---:|---:|---:|---|
| 1 | 0,594378 | 0,588814 | 5 / 6 | 0,725586 | non |
| 2 | 0,597498 | 0,673900 | 4 / 7 | 0,886719 | non |
| 3 | 0,623080 | 0,650926 | 3 / 3 | 0,656250 | non |
| 4 | 0,619028 | 0,657967 | 7 / 5 | 0,387207 | non |
| 5 | 0,654390 | 0,617316 | 2 / 6 | 0,964844 | non |

**[V/R]** Les cinq `GENERATION_*.json` de SELF1 gardent `current_after: g0`, le même hash parent, et aucune promotion. Ce sont cinq essais issus du même seed, **pas cinq descendants adoptés cumulativement**. Le coût historique enregistré atteint 4,7131 USD ; l'audit n'a rien dépensé.

**[V/R]** SELF2 génération 1 : hash candidat identique au parent, 149 requêtes enregistrées, six évaluations internes, `comparison: null`, rejet « the candidate is the parent ». `STOPPED.md` arrête la suite après lecture de SELF1. C'est une lignée inachevée, pas une reproduction négative de cinq générations.

**[R]** L'analyse par famille de `docs/SELF_IMPROVER_LINEAGES_2026-10-11.md` montre saturation ou faible discrimination, et une limite wall-clock TSP qui produit 16 zéros parmi 50 scores. Régression : 13 paires perdues contre deux gagnées. La hausse de moyenne en génération 2 ne démontre donc pas un meilleur improver. La sélection interne des rewrites, sur quatre tâches et deux instances par tâche, coûte jusqu'à 24 requêtes par évaluation : signal étroit, bruit et coût imbriqués.

**Nuance d'audit :** « chaque improver a exactement le même score sur trois familles » est trop littéral : les JSON montrent de petites différences. La lecture justifiée est une **faible capacité de discrimination** selon les seuils utilisés, pas une identité numérique universelle. L'attribution de toutes les différences TSP à la charge est une interprétation du rapport, non une causalité reproduite ici.

**[V] Dérive de version à respecter :** le tag `provenance/self-improver-plan-20261011` contient `promoted(..., margin, level)` avec test des signes. Le HEAD courant utilise un test signed-rank et le runtime a une minuterie CPU `ITIMER_PROF` au lieu de la limite historique wall-clock. Rejouer SELF1 avec le HEAD ne reproduirait pas son instrument. Les premières familles portent désormais `retired` ; ce retrait n'efface pas leurs résultats gelés.

**[R]** Les pilotes du second banc donnent, sur modèle fort, une requête 0,921 et seed à trois requêtes 0,920 ; sur gpt-oss-20b, 0,600→0,707, p=0,009. Ce sont des pilotes de développement, pas une lignée ni un échec universel des scaffolds. **[ND]** Aucun improver ne pourrait être distingué à plus grande échelle, ou aucun meilleur scaffold ne pourrait exister.

## 6. CIRCUIT1 et CIRCUIT2 : apprentissage réel, récursion durable absente

### 6.1 CIRCUIT1 : ce qui se transmet

**[V]** `circuit_engine.solve` énumère des signaux par coût croissant, déduplique par table de vérité, et utilise la cible pour reconnaître le succès. `Component.apply` interprète des étapes NAND : il n'exécute pas du Python généré. `proposals` extrait de petits sous-circuits de solutions réussies ; `refitted` ajuste poids/ordre selon l'usage et peut retirer les composants inutilisés ; `improved` essaie six propositions au plus et sélectionne par nombre de tâches puis applications consommées.

La capacité possédée par la lignée est la bibliothèque et ses poids ; le solveur, l'extracteur, le critère et la sélection des variantes restent écrits par le projet. Les composants dérivés peuvent incorporer des composants antérieurs puis être développés en NAND : une accumulation constructive est possible, sans nouvelle primitive logique fondamentale.

| [R] Bras, tâches retenues sur 41 | Budget 30 000, cinq seeds | Moyenne | Budget 5 000, cinq seeds | Moyenne |
|---|---|---:|---|---:|
| Figé | 11, 11, 11, 11, 11 | 11,0 | 8, 8, 8, 8, 8 | 8,0 |
| Lignée | 11, 17, 14, 11, 11 | 12,8 | 8, 11, 8, 8, 16 | 10,2 |
| Ajout en une étape | 11, 12, 12, 11, 11 | 11,4 | 8, 9, 9, 9, 7 | 8,4 |
| Propositions au hasard | 11, 11, 14, 14, 11 | 12,2 | 9, 16, 8, 8, 16 | 11,4 |

**[R]** Moteur figé avec dix fois le budget : 18 et 14 ; cent fois : 18 et 18. Sélection de procédure sur groupes A/B : meilleur A 5,0 contre seed 4,2 ; B 3,0 pour les deux ; corrélation des rangs 0,096. Aucun gain transférable de la procédure de deuxième ordre n'est établi.

**[V]** Les 24 variantes modifient ranking, arité, poids maximal et suppression de composants. Elles ne réécrivent pas la recherche. Le changement de ranking peut ne rien changer lorsque presque toutes les propositions entrent dans les six essais. Le décompte de cinq seeds ne constitue pas cinq populations indépendantes de tâches : les 41 mêmes fonctions retenues sont réutilisées.

**[V]** `improved` améliore un total, sans contrainte de préserver chaque tâche réussie individuellement. Un composant peut déplacer le coût de recherche et faire perdre des tâches tout en améliorant l'agrégat. La conservation observée sur certains bras n'est donc pas un invariant du moteur.

**[H]** La recherche aveugle combinatoire, l'extraction limitée aux solutions déjà trouvées, le seuil de progrès immédiat et la compétition globale entre composants expliquent le plateau. **[ND]** La recherche est mathématiquement le seul obstacle possible, ou une guidance apprise résoudrait ce plateau : ce sont des hypothèses à conserver comme telles.

### 6.2 CIRCUIT2 : provenance distincte et résultat négatif

Sources hors HEAD : `f6c24fee:experiment/engine/CIRCUIT2/PLAN.json`, `e72d1aa1:experiment/engine/CIRCUIT2/RESULT.json`, `f6c24fee:scripts/run_circuit_meta.py`, `f6c24fee:genesis/circuit_engine.py`; commentaire à `1c2bfdfa:docs/GENESIS_ZERO_BUDGET_2026-10-11.md`. Les empreintes du plan et du résultat ont été recalculées avec succès. Aucun fichier ni contenu de branche n'a été importé dans la branche d'audit.

**[V]** H1 ouvre les coupes à trois couches et quatre entrées, support minimal 1. H2 apprend un score ridge sur 13 caractéristiques écrites à la main via `trials_of`, `fitted`, `auc` et `features`, puis le passe à `improved(..., ranker=...)`. Les cibles sont les gains de tâches des essais sur d'autres groupes de familles. C'est **un véritable apprentissage numérique de poids**, contrairement à une simple liste de règles ; ni poids de LLM ni réécriture autonome du learner.

- **[R] H1 :** 24–32 propositions par étape, mais scores retenus 11, 11, 11, 11, 11, contre 11, 17, 14, 11, 11 de CIRCUIT1 ; zéro ou un composant retenu par seed. L'ouverture choisie n'apporte pas le gain requis.
- **[R] H2 :** gain moyen sur apprentissage : random 3,667 ; support 3,267 ; appris sur un groupe 3,767 ; sur deux 3,633. Deux groupes contre random : sept victoires, 13 pertes, p=0,9423. Contre un groupe : quatre victoires, cinq pertes ; le gain moyen baisse de 0,133.
- **[R] Holdout H2 :** 10,1 contre 9,4 en faveur du classement appris sur deux groupes ; 12 victoires, sept pertes, p=0,1796. Signal descriptif, pas succès confirmé.
- **[R] AUC des six rankers :** 0,429 ; 0,167 ; 0,586 ; 0,601 ; 0,056 ; 0,575. Les relations utiles changent fortement entre groupes.

**Conclusion :** les hypothèses gelées ne sont pas satisfaites par ces variantes. **[ND]** « Rien de général sur les bonnes améliorations n'existe » ou « plus aucune marge en sélection n'existe » : le commentaire de CIRCUIT2 dépasse ici les données. Un ridge sur 13 features globales, trois groupes et peu de trajectoires ne prouve ni l'impossibilité d'un modèle conditionnel aux tâches, ni l'épuisement de toutes les méthodes de sélection. Ne pas remplacer un résultat négatif local par un théorème d'impossibilité.

**[V]** CIRCUIT2 reprend les tâches/familles retenues de CIRCUIT1 après connaissance de son résultat. Les étapes d'apprentissage n'en lisent pas les scores, mais ce n'est pas une nouvelle validation entièrement aveugle au niveau de la recherche humaine. Les trois groupes réutilisent également les seeds ; traiter les 30 paires comme observations indépendantes exige une justification.

### 6.3 Mesure des ressources et artefacts manquants

**[V]** `scripts/run_circuit_lineage.one` mesure `time.monotonic()`, et les summaries additionnent `seconds` des runs ; CIRCUIT2 fait de même. Les 4 813,1 s et 653,2 s archivées sont donc des **sommes de durées wall-clock de workers**, pas une mesure instrumentée du temps CPU. Les appellations « 80/11 minutes de processeur » dans les commentaires ne sont pas prouvées par ces compteurs. La détermination du résultat par budget d'applications reste distincte et réelle.

**[V]** Une application de macro peut exécuter plusieurs NAND ; une application n'est pas une quantité constante d'instructions CPU. Le classement « plus efficace » doit préciser l'unité. Comparer budget d'inférence égal sans inclure essais de composants, refits et collecte des traces ne démontre pas un meilleur coût total. Le figé ×10 bat la moyenne des lignées dans CIRCUIT1, sans suffire à établir le meilleur choix pour une réutilisation infinie : l'amortissement dépend du nombre futur de tâches.

**[V]** Les scripts stockent les trajectoires en SQLite dans le workspace fourni ; les fichiers suivis de CIRCUIT1 sont plan/résultat, et ceux de CIRCUIT2 consultés ici aussi. Les commentaires sur 3 057 essais, 932 étapes, 260 lignées d'amélioration viennent d'une analyse de base externe ; **[R]**, pas recomputation des données brutes par cet audit. Le plan CIRCUIT1 couvre 280 runs, dont les contrôles figés/one-shot : ne pas confondre ces dénominateurs. CIRCUIT2 annonce 125 lignées dans le commentaire corrigé.

## 7. Ce que Genesis sait faire de manière autonome

| Capacité | État établi | Ce qui doit être fourni de l'extérieur |
|---|---|---|
| Générer, ordonner et tester des mutations locales | [V/R] Oui, sans modèle, dans ses familles disponibles | Projet, outil de compilation/tests, scope et budget |
| Abstraire et rejouer un correctif validé | [V/R] Oui, captures structurelles/lexicales ; transfert sur formes apparentées | Correctif initial et validation fiable ; souvent origine assistée |
| Remplacer du raisonnement répété par un spécialiste | [R] Oui dans G8 | Traces validées et distribution apparentée |
| Faire évoluer un composant source | [R] Oui dans G6, choix parmi trois versions | Famille de mutations déjà codée |
| Comparer et adopter/rejeter sous règle gelée, reprendre et rollback | [V/R] Oui dans les stores et expériences dédiés | Autorité et évaluateur réellement séparés |
| Produire une chaîne où un acquis aide le suivant | [R] Oui dans G10 et accumulation modeste CIRCUIT1 | Grammaire de progrès, tâches et critères écrits par le projet |
| Apprendre une heuristique numérique | [V/R] Oui, rankers CIRCUIT2 sur branche distincte | Features, learner ridge et données définis par l'hôte ; utilité transférée non établie |
| Réparer des projets externes avec modèle | [R] Oui, par exemple seed 21/40 dans L1 | LLM fixe et service payant historiquement utilisé ; suite imparfaite |
| S'améliorer durablement sur vrais projets sans modèle | [ND] Non établi | Manquent couverture et transfert prospectif démontré |
| Inventer de nouvelles familles de mécanismes, améliorer le learner de façon transférable, s'étendre à des tâches ouvertes | [ND] Non établi | Aucun enchaînement de preuves suffisant |

L'autonomie d'exécution d'un protocole ne doit pas être confondue avec l'autonomie de conception du protocole, du vocabulaire et du juge.

## 8. Pourquoi les réussites ne se généralisent pas

### 8.1 Le support des tâches change davantage que les mécanismes

**[V/R]** G5–G10 utilisent des familles contrôlées qui exposent les invariants visés. Les bugs Defects4J demandent notamment insertions, nouveau flux de contrôle, états hérités, APIs, effets et coordinations. Un template transférable au renommage ne couvre pas automatiquement un nouveau principe sémantique. L'apprentissage ne peut pas inventer une correction hors de sa grammaire simplement en augmentant sa mémoire.

### 8.2 Les succès de développement ajoutent souvent la sémantique de l'extérieur

**[V/R]** Les opérateurs d'état hérité, garde de méthode sœur et iterator ont été ajoutés après exposition. G12 apprend ensuite leur forme depuis le patch. La séquence réelle est « assistance ajoute une idée → générateur trouve un patch → validateur accepte → Genesis abstrait ». La remplacer dans le récit par « Genesis découvre la nouvelle idée » serait une erreur d'attribution.

### 8.3 Le succès assisté dépend fortement du modèle, sans prouver que tout scaffold est inutile

**[R]** `docs/REPAIR_LINEAGE_2026-10-09.md` : LINEAGE1 passe de 4/20 à 8/20 au développement, puis L1 donne seed 21/40 contre descendant 19/40, p=0,94. LINEAGE2, instrument corrigé : seed 43/60, descendants 39, 37, 38, 37 ; aucune promotion. Les défauts d'environnement Lang/JacksonDatabind affectent les niveaux et peuvent polluer les leçons retenues ; ils n'autorisent pas à réécrire L1.

**[R]** `docs/REPAIR_INTERVENTIONS_2026-10-10.md` : outils, arrêt, split, double budget, localisation oracle produisent 10–14/32 contre rerun 12/32. Sonnet contre Haiku : 11/16 contre 6/16, cinq gains sans perte, p=0,031 **sans correction des six comparaisons**. Les cas sont des échecs de développement sélectionnés, une exécution par bras.

**Conclusion calibrée :** changer le modèle a le signal le plus clair dans cette étude ; les variantes testées du scaffold n'ont pas montré de gain. **[ND]** La localisation ou le budget ne pourraient jamais aider, ou la capacité du système serait entièrement celle du modèle. La stochasticité du rerun, la petite taille et le test multiple limitent cette généralisation.

### 8.4 Plusieurs mémoires persistent sans effet mesuré sur le comportement futur

**[V]** `operator_outcome_memory.OperatorOutcomeMemory.record` stocke des issues training-only, sans changer automatiquement les priorités. `memory/strategy.rank_candidates` favorise les identités d'opérateurs déjà gagnants, sans créer d'opérateurs. `repair_quality_learning` réordonne selon risques, succès et histoire ; `repair_contract_learning` attend des contrats explicites. Aucun de ces mécanismes n'est une induction générale de contrats.

**[R]** `docs/REPAIR_TRANSFORMATION_LEARNING_2026-10-09.md` : règles provenant de trois générations d'acquisition, mais zéro candidat appris applicable sur Jsoup-59, Math-41, Compress-44 ; parent/child 0/3, 34 échecs compilation sur 48 validations, pas de promotion. Le mémoire croît 124→173 événements, sans gain de réparation. C'est une distinction concrète entre accumulation d'archives et accumulation de capacités.

**[V]** G12 réserve zéro slot par défaut. `repair_strategist.generate` peut majorer les règles retenues de 250 points et réserver jusqu'à quatre slots si explicitement activé. Le commentaire explique qu'une déduplication par contenu pouvait autrement préserver la provenance de la famille écrite à la main et effacer celle de l'apprenant. Une mémoire valide mais non appelée, non applicable ou éliminée avant top-K ne participe pas causalement au résultat.

### 8.5 Mesurer la mauvaise variable produit de fausses directions

**[V/R]** Compilation, couverture des sites humains, score agrégé wall-clock et nombre d'événements sont des proxys. Les améliorations correspondantes n'ont pas établi le gain final recherché. `repair_causal_evidence.check` vérifie des citations de source et leur cohérence locale ; le mot « causal » ne prouve pas que l'explication fournie cause le correctif. Les ablations et interventions sont plus fortes que ces étiquettes.

## 9. Mécanismes d'apprentissage : inventaire opérationnel

| Mécanisme et fonctions | Ce qui est appris/modifié | Limite constatée et réutilisation possible |
|---|---|---|
| `memory/strategy.learn_from_result`, `rank_candidates` | Prior d'opérateur à partir d'un résultat gagnant | Classement seulement ; garder comme baseline simple, pas cerveau central |
| `learning/self_extension.retain_gap`, `acquire_from_passing_candidate`, `generate_candidates` | Événement pré-solution et templates structurels adressés | API basse couche exige un digest de résultat, pas une preuve externe complète ; intégrer via un validateur qui possède les reçus |
| `g12_operator_lab.validate_and_learn` | Acquisition après compilation et full suite explicitement acceptées | Fonction callback et rôle `released_training` fournis par caller ; séparation à imposer à l'exécution, pas par chaînes déclaratives seules |
| `learning/distillation.distill_local_specialist` | Bibliothèque compacte de templates validés | Très réutilisable pour économiser l'inférence lorsque domaine d'application reconnu |
| `repair_self_improvement.propose_descendant`, `decide_promotion` | Paramètres d'offset subscript issus d'exemplars | Vocabulaire étroit ; démonstrations de développement et permutations proches |
| `repair_search_adaptation.derive_search_descendant` | Choix `retained_first` / `observed_first` | Deux ordres écrits à la main ; pas d'algorithme de recherche inventé |
| `repair_transformation_learning.acquire`, `generate`, `feedback_order`, `search` | Templates Java et réordonnancement par feedback | Lexical ; absence d'applicabilité dans le transfert réel étudié |
| `repair_quality_learning.operator_policy`, `rank`, `refine` | Risques par opérateur et projections d'expressions | Préconditions syntaxiques et validation, pas compréhension sémantique générale |
| `repair_contract_learning.acquire`, `generate` | Insertion non-null abstraite sous contrat fourni | Le contrat doit venir de l'extérieur ; le système n'en déduit pas la nécessité générale |
| `v2/discovery.evolve_in_training` | Cinq poids de sélection | Gain de compilation seulement, production interdite par gate |
| `v2/semantic_dsl.propose` | Hypothèses instanciées depuis méthodes sœurs | Nouvelle proposition avant solution, mais grammaire humaine étroite ; aucune nouvelle hypothèse sur les trois cas frais |
| `repair_lineage`, `improver_seed` | Texte/configuration ou source généré par modèle fixe | Coût d'évaluation imbriqué ; aucun gain cumulatif externe montré dans les lignées examinées |
| `circuit_engine.proposals`, `refitted`, `improved` | Macros, poids et ordre de bibliothèque | Gain fini sur certaines seeds, procédure non améliorée de façon transférable |
| CIRCUIT2 `fitted`, `features` | Poids ridge de gain attendu | Apprentissage réel, transfert non validé ; utile comme contrôle négatif |

**[ND]** Entraînement des poids d'un LLM ou d'un moteur neuronal local actif dans les campagnes examinées. Les propositions GPU/QLoRA et CIRCUIT3 des documents de réorientation restent des propositions ; elles ne sont ni preuve, ni autorisation de les exécuter. Aucun téléchargement ni entraînement réalisé pour cet audit.

## 10. Obstacles à la récursion cumulative

| Obstacle | Preuve principale | Conséquence | Solidité |
|---|---|---|---|
| Vocabulaire modifiable fini et décidé par l'hôte | G6 trois fonctions ; G10 trois transitions ; V2 cinq features ; deux ordres de recherche | Le système peut sélectionner son plafond mais ne possède pas le mécanisme général pour le déplacer | [V], direct |
| Goulot principal pas toujours dans l'objet mutable | Interventions modèle/scaffold ; CIRCUIT modifie la bibliothèque avec solveur fixe | Les modifications n'atteignent pas la ressource limitante | [R] local ; [H] global |
| Faible applicabilité de mémoire | Transfert Java 0 candidat appris ; G12 off par défaut | La connaissance retenue n'entre pas dans les candidats futurs | [V/R] |
| Objectifs intermédiaires confondus avec succès | V2 compilation, localizer couverture, SELF moyenne | Sélection peut apprendre à optimiser le proxy | [V/R] ; effet exact à quantifier |
| Coût d'amélioration absent des comparaisons d'inférence | SELF évaluations imbriquées ; CIRCUIT essais/refits | Gain d'un solveur ne démontre pas gain de rendement de la recherche | [V] |
| Sélection gloutonne à horizon court | CIRCUIT `improved`, arrêt première étape sans adoption | Changements complémentaires ou différés éliminés ; minima locaux possibles | [V] règle ; [H] effet |
| Régressions et compétition entre acquis | Ranking/caps, déduplication, retrait composants, V2 projet régressé | Un acquis peut évincer un autre au lieu d'étendre la frontière | [V/R] |
| États et contrats multiples | Profils G10, mémoire A6c/G12, recettes, genomes, Engine | Pas de lignée universelle démontrée traversant toutes ces surfaces | [V] structures ; [ND] boucle unifiée |
| Sélection et interprétation réutilisent des distributions exposées | Développement G12/V2 ; CIRCUIT2 mêmes familles retenues ; SELF arrêt post résultat | Surestimation possible du transfert ; coût scientifique des nouvelles expositions | [V/R] |
| Autorité et mesures tributaires du caller | Callbacks G12, decisions adressées, sandbox variable | Intégrité syntaxique ne garantit pas indépendance ni vrai verdict | [V] frontière, pas exploit démontré |

La récursion exige plus que « un enfant meilleur ». Il faut que l'acquis aide à proposer/sélectionner un prochain acquis utile, sans intervention humaine qui ajoute la nouvelle idée entre étapes, avec transfert et coût comparables. G10 satisfait une version bornée par construction et mesures ; SELF et CIRCUIT ne fournissent pas le prolongement général recherché.

## 11. Dépendances et infrastructure : ce qui pose problème

| Dépendance | Constat | Risque architectural/scientifique | Orientation proposée |
|---|---|---|---|
| Python ≥3.11, setuptools ≥68, NumPy non pinné | `pyproject.toml`; dev pytest/xdist non pinnés | Installation non identique dans le temps ; surface package mélange actif/historique | Conserver, définir plus tard des manifests de reproduction par résultat ; ne pas modifier rétroactivement les freezes |
| pytest optionnel mais appelé dans un module du package | `improvement_harness.main`, mode `pytest` | L'installation runtime seule ne couvre pas cet outillage expérimental | Classer explicitement hors runtime minimal ; pas un import global cassé établi |
| OpenRouter via urllib | `openrouter_repair.py`, `repair_lineage.py`, `improver_lineage.Model` | Coût, modèle/route variables, génération stochastique, capacité externe | Adaptateur explicitement optionnel et désactivé pour le périmètre sans dépense ; aucun appel pendant cet audit |
| Codex CLI | `improver_codex.CodexModel`, `_run`, `command` | Une subscription reste une dépendance externe et une consommation ; paramètres moins contrôlés | Conserver l'historique ; ne pas traiter ce canal comme calcul local gratuit |
| Docker et image Defects4J/JDK | `defects4j_sandbox.py`, `deploy/defects4j/Dockerfile` | Fixtures externes, dépendances projet, commandes coûteuses, tests sensibles à environnement | Réutiliser le validateur et préserver les images/identités qualifiées ; aucune construction ici |
| Image d'amélioration de programmes | `deploy/program-improvement/Dockerfile`: base par digest, pytest 8.3.3, apt valgrind/gcc | Base pinnée mais résolution apt non figée ; mesure d'instructions et environnement distincts | Outillage de labo, pas dépendance centrale de tout solveur |
| PostgreSQL/psycopg OE1 | `deploy/oe1/requirements.txt`: `psycopg[binary]>=3.2,<4`; compose | Prérequis expérimental, pas dépendance Python runtime déclarée | Garder adapter/corpus OE1 séparés du cœur ; aucun service touché |
| Toolchains multiples et Node 20 CI | `languages/toolchains.py`, `.github/workflows/ci.yml` | Disponibilité locale et fidélité inégales ; CI ne valide pas toutes les suites réelles | Déclarer les capacités réellement disponibles pour chaque exécution |
| `metamorphosis`, `mira_core` distribués | Package discovery et bridges `m107_bridge`, `m108_bridge` | Chaînes historiques nécessaires à certains consommateurs ; coût de maintenance | Classer par consommateur, conserver les références gelées et compatibilités |
| Datasets, mémoires et bases hors dépôt | V2 README, scripts CIRCUIT, workspaces de réparation | Reproduction publique incomplète depuis le seul checkout | Catalogue des identités/emplacements autorisés ; aucune copie de contenu privé ou réservé |

`docs/THIRD_PARTY_DEPENDENCIES.md` est un snapshot d'août : utile, mais son passage « services AI seulement outils de développement » ne décrit plus toute la dépendance opérationnelle d'octobre. NumPy est la seule dépendance de distribution déclarée ; cela ne décrit pas Docker, JDK, tests projet, CLI et services nécessaires aux différentes expériences.

**Frontière d'isolation [V] :** `sandbox.py` documente une isolation Python à audit hooks ; ce n'est pas la même garantie que Docker sans réseau. `component_evolution._load_module` et `runtime/profile_executor._load_module` chargent du source avec `exec` dans le processus appelant. Leur usage borné avec source autorisé ne démontre pas une faille ; ils ne sont pas un exécuteur général de code non fiable. Ne pas étendre leur usage en confondant identité de source et confinement.

**[V]** Les décisions de `lineage_promotion` lient hashes d'autorité/règle/évaluateur et mesures. Ces hashes ne sont pas des signatures cryptographiques d'une autorité externe. `OperatorOutcomeMemory.record` explicite lui-même que les outcomes sont des claims du caller. Une reconstruction du cœur doit préserver et rendre concrète la frontière de confiance ; ajouter des champs `independent: true` ne la crée pas.

## 12. Garder, simplifier, retirer du périmètre actif

« Retirer du périmètre actif » signifie ne plus en dépendre pour la prochaine architecture ; **aucune suppression de fichier, donnée, service ou preuve n'est proposée dans cet audit comme action immédiate**.

| Classe | Composants | Recommandation et justification |
|---|---|---|
| Indispensables au programme scientifique | Contrats, budgets, preuves, journal, contenu adressé, garde des corpus, décisions et rollback | Conserver les invariants de `trust_root`, `journal`, `state`, `lineage_promotion`, `repair_bench`. Ne pas les rendre mutables par le candidat. |
| Réutilisables sans conserver tous leurs callers | `Defects4JSandbox`, validation manifestes, `RepairPlan`, feedback typé, modules JDK, spécialistes et opérateurs acquis | Interfaces utiles ; réemploi à démontrer sur un chemin actif explicite. La réutilisabilité n'est pas une validation de leur efficacité générale. |
| Baselines utiles et bornées | Mutations scalaires/Java, ranking de stratégies, G6 et G10, CIRCUIT, V2/V2.1 | Conserver comme contrôles ou mécanismes de domaine ; ne pas les annoncer comme cœur général. |
| Surfaces à simplifier | Plusieurs memories/recipes/policies et plusieurs moteurs de promotion ; flags du strategist ; appellations V2 concurrentes | Unifier les contrats actifs et les identités, sans migrer de force les schémas gelés ni effacer les provenances. |
| Compatibilités non problématiques en elles-mêmes | Alias plats vers `learning`, `operators`, `runtime`, `languages` | Garder tant qu'utilisés par artefacts/tests ; faible coût, suppression peu rentable. |
| Historiquement obsolètes comme direction active | Banc SELF1 retiré, SELF2 arrêté, anciennes stratégies à vocabulaire trop étroit, lignes anciennes de controllers/policies | Préserver et classer « historique/labo ». Aucun bénéfice démontré à faire passer chaque tâche future par ces couches. |
| À ne pas déclarer morts sur leur nom seul | `metamorphosis/`, `mira_core/`, bridges et anciens modules cognitifs | Une analyse des consommateurs et références gelées est nécessaire avant toute exclusion du packaging. L'audit ne prouve pas que chacun est inutile. |
| Options non actives | Pilot GPU, learner de guidance CIRCUIT3, refonte auto-proposée | Pas d'autorisation ni d'implémentation ; restent hors du travail actuel. |

## 13. Architecture cible proposée pour décision

### 13.1 Principe : un petit noyau de contrôle, des moteurs de domaine isolés

**[H, proposition]** Séparer trois choses aujourd'hui fréquemment confondues : le contrôle de l'expérience, le moteur qui propose des solutions, et la politique qui propose des modifications de ce moteur. La séparation n'est utile que si elle est exécutée et mesurée ; une simple nouvelle arborescence serait insuffisante.

```text
Leona / direction scientifique
       | objectif, périmètre, règle, budget autorisés
       v
Contrôle de confiance immuable --------> corpus / rôles / registre d'exposition
       |                                       |
       | évaluation indépendante               | accès filtrés
       v                                       v
Exécuteur isolé <---- artefact candidat ---- Moteur de domaine
       |                                    (réparation OU circuit)
       v                                       ^
Reçus typés et coûts                            |
       |                                Mémoire de capacités
       v                                et propositions training-only
Décision externe : rejeter / promouvoir         ^
       |                                       |
       v                               Politique d'amélioration
Pointeur de lignée + rollback ---------> parent exact, état et preuves
```

Le « noyau » ci-dessus garde budgets, identités, exécution, séparation de rôles et transitions autorisées. Il ne prétend pas posséder un solveur général. Le réparateur et le synthétiseur de circuits partagent des contrats de preuve, **pas une représentation forcée commune des solutions**.

### 13.2 Contrats minimaux à viser, sans les implémenter maintenant

| Contrat | Contenu nécessaire | Origine réutilisable |
|---|---|---|
| Tâche | Identité, domaine, source, rôle training/selection/holdout, versions, unités de budget | `repair_bench`, manifestes `real_project`, plans gelés |
| Proposition | Parent exact, mécanisme modifié, différence, hypothèse, provenance humaine/modèle/locale | `component_evolution`, profils de successeurs, `repair_ir` |
| Exécution | Image/runner et dépendances identifiés, résultats bruts, statut infrastructure distinct, coût | Sandboxes, feedback typé, harnesses existants |
| Capacité retenue | Définition exécutable, domaine d'applicabilité, reçus, coûts d'acquisition, dépendances | G12, templates, spécialistes, composants CIRCUIT |
| Décision | Règle gelée, autorité effective, parent/child, gains/pertes par tâche, coûts et ablations | G7/store et trust root |
| Lignée | Pointeur actif, historique de transitions, migrations explicites, rollback, absence de mélange d'évidence | `state`, `journal`, G7 |

La mémoire devrait distinguer **épisode**, **hypothèse non validée**, **capacité validée dans un domaine**, **politique effectivement promue**. Elle devrait garder les origines multiples lorsqu'un même candidat est produit par plusieurs générateurs. Le volume retenu ne serait jamais présenté comme score d'apprentissage.

### 13.3 Ce que le cœur de recherche devra changer, si reconstruction décidée

1. **Posséder une partie de la capacité limitante.** En réparation, retenir davantage que des préférences de prompt ; en CIRCUIT, ne pas confondre bibliothèque et algorithme. Le choix de l'objet mutable doit venir d'une preuve interventionnelle, avec possibilité de rester indéterminé.
2. **Rendre l'espace des propositions explicite.** Distinguer nouveau paramètre, nouveau template, nouvelle composition et nouvelle famille d'algorithmes. Un système peut rester borné et utile, mais ne doit pas présenter une activation d'option comme invention.
3. **Brancher les acquis sur la recherche future.** Mesurer applicabilité, propositions émises, rangs, validations et succès. Une capacité jamais utilisée ne peut expliquer le gain.
4. **Évaluer une frontière de compromis.** Qualité finale, régressions, robustesse et coût total ; les nombres de candidats seuls ne suffisent pas lorsque le coût d'un candidat varie.
5. **Séparer amélioration du solveur et amélioration de l'improver.** La seconde exige des descendants produits mieux, sur sélection distincte, puis transfert ; aucun score de compilation seul ne l'établit.

Ces exigences ne sont pas une promesse que le noyau cible donnera une RSI. Elles rendent le diagnostic futur moins ambigu et les composants utiles plus faciles à réutiliser.

### 13.4 Arbitrage conserver / simplifier / reconstruire

| Option | Bénéfice probable [H] | Risque | Avis |
|---|---|---|---|
| Garder tout et ajouter des flags | Préserve compatibilité immédiate | Complexité et plafonds persistants ; résultat difficile à attribuer | Déconseillé comme direction principale |
| Simplifier uniquement les noms/répertoires | Lecture plus facile | Aucun gain d'expressivité ou transfert ; risque sur chemins gelés | Insuffisant scientifiquement |
| Petit socle commun, moteurs séparés, reconstruction ciblée de la recherche | Garde les garanties, rend les causes et coûts observables | Migration/contrats ; gain de capacité à démontrer | **Option recommandée à soumettre à Leona** |
| Réécriture intégrale | Liberté de conception | Perte d'invariants, nouvelle surface de bugs, aucune preuve que le problème disparaît | Déconseillé sans justification supplémentaire |
| Basculer maintenant vers entraînement de modèle/GPU | Modifie une capacité différente | Dépense interdite, infrastructure et nouvelle recherche | Hors périmètre et non autorisé |

## 14. Recommandations classées par impact et risque

Aucune ligne de cette table n'autorise une action après remise du rapport. L'impact est un jugement architectural, pas un effet expérimental mesuré.

| Priorité | Recommandation | Impact attendu | Risque | Fichiers/composants concernés |
|---|---|---|---|---|
| P0 | Fixer une carte des claims : assay synthétique, développement exposé, transfert frais, indépendance de validation/reproduction | Très élevé sur la qualité des décisions | Faible ; rédaction mal faite pourrait déformer le gel | README, PROJECT_STATE, rapports G/SELF/CIRCUIT ; ne pas modifier leurs résultats |
| P0 | Définir un seul chemin actif et sa lignée exacte, options et mémoires comprises | Très élevé sur lisibilité et causalité | Moyen : dépendances historiques cachées | `repair_strategist`, `loop`, `controller`, executors, mémoire |
| P0 | Conserver l'autorité de verdict hors du descendant et préserver invariants de persistance/rollback | Critique pour toute future auto-modification | Moyen à élevé si redéploiement | `trust_root`, `sandbox`, `lineage_promotion`, sandboxes Docker |
| P1 | Simplifier autour des contrats de tâche, proposition, reçu, capacité et décision | Élevé pour maintenance et audit | Moyen à élevé : migration et provenance | Schémas G12/A6c, recettes, profils G10, genomes, `RepairPlan` |
| P1 | Décider d'une reconstruction ciblée du moteur de recherche plutôt que d'un nouveau contrôleur de classement | Potentiellement élevé sur capacité | Élevé : gain non démontré | Générateurs de réparation ou `circuit_engine.solve`, selon domaine choisi par Leona |
| P1 | Faire apparaître les coûts d'acquisition et l'amortissement, pas seulement zéro appel à l'inférence | Élevé sur choix de direction | Faible à moyen ; données anciennes parfois absentes | Ledgers, plans/results, mesures CIRCUIT, G8/G12 |
| P1 | Mesurer le parcours des acquis et préserver toutes les provenances de candidats dédupliqués | Élevé pour attribuer le transfert | Moyen : changement de politique et rétrocompatibilité | `repair_strategist.generate`, memories, adapters |
| P1 | Garder défaut d'infrastructure, erreur compilation et échec sémantique comme états différents | Élevé sur apprentissage fiable | Moyen : impact sur anciennes métriques | `repair_bench`, `real_project`, feedback, outcomes |
| P2 | Maintenir anciennes familles et controllers comme archives/labo avec alias stables | Moyen sur charge cognitive | Faible si aucune suppression ; moyen si packaging ensuite | Flat modules, `metamorphosis`, `mira_core`, expériences |
| P2 | Préparer un inventaire de reproductibilité par résultat, versions de runner et accès aux archives autorisées | Moyen à élevé | Faible si identités seules ; risque de confidentialité si contenus copiés | SQLite CIRCUIT, candidate records V2, images, manifests |
| P2 | Réconcilier docs de dépendances avec usages runtime des modèles et unités réelles de temps | Moyen | Faible | `THIRD_PARTY_DEPENDENCIES`, rapports CIRCUIT, canaux CLI/API |
| P3 | Choisir ultérieurement si guidance apprise, synthèse sémantique ou entraînement local mérite une recherche | Inconnu | Élevé, coût et surapprentissage | Propositions de réorientation, hors mission actuelle |

## 15. Hypothèses et questions encore ouvertes pour Leona

| Question | Ce que les preuves disent aujourd'hui | Ce qui manque ; vérification future seulement sur décision |
|---|---|---|
| Quel mécanisme est réellement actif dans le service courant ? | Defaults et options lisibles ; certains rapports disent services arrêtés | État déployé, configs et mémoire réellement chargée. Aucun service inspecté/modifié ici ; ne pas confondre doc et état live. |
| Un acquis G12 ou Java peut-il généraliser au-delà de motifs proches ? | Replay et transfert synthétique ; zéro émission dans le transfert Java étudié | Applicabilité indépendante, puis effet causal ; aucun nouveau holdout consommé ici |
| La syntaxe/type est-elle le principal verrou de réparation ? | Frontends inégaux ; V2.1 compile sans réparer les cas frais | Interventions isolant représentation, propositions et sélection ; pas une conclusion acquise |
| La guidance conditionnée à la tâche peut-elle dépasser ridge global et macros ? | CIRCUIT2 n'évalue qu'un ridge de features limitées | Effet inconnu ; CIRCUIT3 proposé dans une autre branche n'est ni exécuté ni autorisé par cet audit |
| Le contrôle one-shot CIRCUIT est-il parfaitement apparié ? | Même objectif de nombre de composants, mais dépend des propositions disponibles et du refit | Relecture des traces brutes et compte effectif, pas uniquement intitulé du bras |
| Les avantages restent-ils après coût total égal ? | Baselines budget augmenté, appels et essais documentés en partie | CPU réel, mémoire, temps global, coût d'acquisition et horizon d'amortissement |
| Les trajectoires démontrent-elles des dépendances de composants ultérieurs ? | G10 a des comparaisons causales ; CIRCUIT permet composition d'acquis | Ablations exactes des composants sur trajectoires CIRCUIT archivées ; pas de nouveau run ici |
| Les 21 empreintes suffisent-elles à une reproduction indépendante ? | Non, uniquement intégrité des documents sélectionnés | Identités transitives, logs, bases, images et autorité ; contrôles séparés sans réécriture historique |
| La reconstruction cible améliorera-t-elle la capacité ? | Non mesuré, proposition issue du diagnostic | À établir après décision, jamais à présumer à partir du découpage |

## 16. Historique et précautions d'interprétation

Le programme a déjà rencontré le même problème sous d'autres formes : `docs/GENESIS_PRIMITIVE_AUDIT.md` distingue la lignée des fichiers M107–M112 d'une lignée persistante d'état, et montre de nouvelles classes de composants ajoutées par l'hôte dans des tuples. `loop.py` apporte ensuite persistance, ablations et attribution de self-report, mais son existence ne prouve pas que toutes les campagnes passent par ce chemin.

L9 OE1-v3 (`docs/L9_OE1_V3_QUALIFICATION_2026-10-06.md`) conserve une preuve finie importante : 16/16 prédicats, 576/576 tâches codées et audit archivé de 33 215 reçus sans mismatch. **[R]**, sans replay ici ; tâches et critères restent écrits par le projet. Ce résultat ne clôt pas la généralité externe.

A6b (`docs/A6B_CAMPAIGN_2026-10-06.md`) reste **DEVELOPMENT FAIL** : 3/12 autonomes, neuf appels fallback, 9/12 pipeline, zéro réutilisation d'un acquis d'une tâche antérieure de la même campagne. Ses traces peuvent alimenter G8 sans rendre la campagne positive rétroactivement.

Le rôle des personnes et outils est maintenu : Anthony Mets est le directeur et seul développeur humain au snapshot de provenance ; Codex/Claude/ChatGPT sont des assistances. Un juge de code indépendant du candidat n'est pas un mainteneur humain indépendant. Les résultats Track A sans modèle ne doivent pas absorber le crédit des idées initialement apportées par modèle ou assistance Track B.

Le rapport s'arrête au diagnostic et à cette proposition. **Décisions, priorités de reconstruction et éventuels travaux suivants reviennent à Leona et à la direction du projet. Aucune nouvelle campagne, fonctionnalité ou refonte n'est lancée.**
