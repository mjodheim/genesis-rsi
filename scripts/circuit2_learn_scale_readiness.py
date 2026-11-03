"""Verdict de faisabilité à l'échelle du circuit 2 (apprentissage).

Objet : consigner, point par point, ce qui a été lu et ce qui reste non
vérifié avant un passage à l'échelle : graines 0 à 4, 6 générations.
État de la copie locale au 2026-11-03.

Ce module ne contient que des données : il n'exécute rien à l'import,
n'écrit aucun fichier et n'appelle pas le réseau. Sa synthèse conclut
à un état non prêt pour ce passage.
"""

VERDICT = [
    {
        "point": 1,
        "constat": (
            "Sceau du lanceur : LAUNCHER_SEAL.json est absent de la liste des "
            "fichiers suivis sous experiment/engine/CIRCUIT2."
        ),
        "source": (
            "liste lue des fichiers suivis sous experiment/engine/CIRCUIT2 "
            "(5 fichiers : DEV_DIAGNOSTIC_2026-10-20.md, EXECUTABLES.json, "
            "PLAN.json, PROCEDURE_PREREG_PLAN.json, RESULT.json)"
        ),
        "extrait": "LAUNCHER_SEAL.json : absent de la liste des 5 fichiers lus",
        "statut": "lu",
    },
    {
        "point": 1,
        "constat": (
            "Le texte lu de scripts/run_circuit2_campaign.py (entier) ne "
            "contient aucune vérification de sceau ni de sa propre identité : "
            "il vérifie seulement le plan. Aucune affirmation n'est faite "
            "que les résultats proviennent d'un lanceur scellé."
        ),
        "source": "scripts/run_circuit2_campaign.py (lu en entier)",
        "extrait": (
            "seul un plan dont le digest est identique à celui du fichier "
            "publié (CANONICAL_PLAN_PATH, relu et vérifié) est exécuté ; "
            "aucun repli."
        ),
        "statut": "lu",
    },
    {
        "point": 1,
        "constat": (
            "Fixture de tests/test_circuit2_campaign.py créant un sceau "
            "temporaire : non vérifiée, seuls les 13333 premiers caractères "
            "du fichier ont été lus, sans fixture de sceau."
        ),
        "source": "tests/test_circuit2_campaign.py (lecture partielle, caractères 0 à 13333)",
        "extrait": "",
        "statut": "non vérifié",
    },
    {
        "point": 2,
        "constat": (
            "inherited_lineage, results/circuit2_campaign_s01_g4.json "
            "(lecture partielle, caractères 0 à 13333) : graines 0 et 1, "
            "4 générations chacune ; library_digest identique à chaque "
            "génération ; score et selection_score constants ; "
            "stopped_early false. Résultat négatif : aucune amélioration "
            "du premier niveau observée sur ces 2 graines à échelle réduite."
        ),
        "source": "results/circuit2_campaign_s01_g4.json (lecture partielle, caractères 0 à 13333)",
        "extrait": (
            "graines 0 et 1 ; 4 générations chacune ; library_digest "
            "03922f7aeef97a5adbbd1c17f1f009cf1342dcb76ffcc04472f71cae0bef05b7 "
            "identique à chaque génération ; score [2,-137] ; "
            "selection_score [2,-137] ; stopped_early false"
        ),
        "statut": "lu",
    },
    {
        "point": 3,
        "constat": (
            "Comportement à 6 générations et sur les graines 2 à 4 : non vérifié, "
            "aucune exécution ni lecture de résultat correspondante dans le contexte fourni."
        ),
        "source": "aucune source lue",
        "extrait": "",
        "statut": "non vérifié",
    },
    {
        "point": 4,
        "constat": (
            "Docstring du lanceur lue : seul un plan au digest identique à "
            "celui du fichier publié est exécuté, sans repli."
        ),
        "source": "docstring de scripts/run_circuit2_campaign.py",
        "extrait": (
            "seul un plan dont le digest est identique à celui du fichier "
            "publié (CANONICAL_PLAN_PATH, relu et vérifié) est exécuté ; "
            "aucun repli."
        ),
        "statut": "lu",
    },
    {
        "point": 4,
        "constat": (
            "Règle d'arrêt lue dans le lanceur : arrêt après une "
            "génération épuisée sans adoption."
        ),
        "source": "docstring de scripts/run_circuit2_campaign.py",
        "extrait": "le plan impose l'arrêt après une génération épuisée sans adoption",
        "statut": "lu",
    },
    {
        "point": 5,
        "constat": (
            "Condition bloquante : l'absence du sceau du lanceur est à signaler "
            "à Anthony, hors du périmètre de cette PR. Ce verdict ne conclut "
            "pas à un passage à l'échelle."
        ),
        "source": "liste lue des fichiers suivis sous experiment/engine/CIRCUIT2",
        "extrait": "LAUNCHER_SEAL.json : absent de la liste des 5 fichiers lus",
        "statut": "lu",
    },
    {
        "point": 6,
        "constat": (
            "Non prêt : sceau du lanceur absent de la liste lue, aucune "
            "amélioration du premier niveau observée sur les graines 0 et 1 "
            "à échelle réduite, comportement à 6 générations et sur les "
            "graines 2 à 4 non vérifié."
        ),
        "source": "entrées précédentes de ce verdict (points 1 à 5)",
        "extrait": (
            "sceau absent ; aucune amélioration du premier niveau observée ; "
            "6 générations et graines 2 à 4 non vérifiés"
        ),
        "statut": "lu",
    },
]
