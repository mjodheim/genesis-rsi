"""Verdict de faisabilité à l'échelle du circuit 2 (apprentissage).

Objet : consigner, point par point, ce qui a été lu et ce qui reste non
vérifié avant un passage à l'échelle : graines 0 à 4, 6 générations.
État de la copie locale au 2026-11-03.

Ce module ne contient que des données : il n'exécute rien à l'import,
n'écrit aucun fichier et n'appelle pas le réseau. Il ne conclut pas
« prêt à l'échelle ».
"""

VERDICT = [
    {
        "point": 1,
        "constat": (
            "Sceau du lanceur : experiment/engine/CIRCUIT2/LAUNCHER_SEAL.json "
            "est absent de la liste des fichiers suivis."
        ),
        "source": "liste des fichiers suivis de la copie locale",
        "extrait": "experiment/engine/CIRCUIT2/LAUNCHER_SEAL.json : absent",
        "statut": "lu",
    },
    {
        "point": 1,
        "constat": (
            "Message d'échec du lanceur et comportement du refus : non vérifiés, "
            "l'extrait de scripts/run_circuit2_campaign.py reçu au journal 2712 "
            "est tronqué avant ce passage."
        ),
        "source": "scripts/run_circuit2_campaign.py (extrait tronqué, journal 2712)",
        "extrait": "",
        "statut": "non vérifié",
    },
    {
        "point": 1,
        "constat": (
            "Fixture de tests/test_circuit2_campaign.py créant un sceau "
            "temporaire : non vérifiée, ce fichier n'a pas été lu ; seule une "
            "relecture de Codex le suggère."
        ),
        "source": "tests/test_circuit2_campaign.py (non lu)",
        "extrait": "",
        "statut": "non vérifié",
    },
    {
        "point": 2,
        "constat": (
            "inherited_lineage, results/circuit2_campaign_s01_g4.json : valeurs "
            "rapportées dans la demande, library_digest identique sur 4 générations "
            "et score [2,-137] constant. Résultat négatif : aucune amélioration du "
            "premier niveau observée. Lecture non retrouvée au journal fourni."
        ),
        "source": "results/circuit2_campaign_s01_g4.json (lecture absente du contexte fourni)",
        "extrait": "",
        "statut": "non vérifié",
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
            "Docstring du lanceur lue : digest du plan canonique exigé, aucun "
            "repli ; arrêt après une génération épuisée sans adoption."
        ),
        "source": "docstring de scripts/run_circuit2_campaign.py",
        "extrait": "digest du plan canonique exigé, aucun repli ; arrêt après une génération épuisée sans adoption",
        "statut": "lu",
    },
    {
        "point": 5,
        "constat": (
            "Condition bloquante : l'absence du sceau du lanceur est à signaler "
            "à Anthony, hors du périmètre de cette PR. Ce verdict ne conclut "
            "pas à un « prêt à l'échelle »."
        ),
        "source": "liste des fichiers suivis de la copie locale",
        "extrait": "experiment/engine/CIRCUIT2/LAUNCHER_SEAL.json : absent",
        "statut": "lu",
    },
]
