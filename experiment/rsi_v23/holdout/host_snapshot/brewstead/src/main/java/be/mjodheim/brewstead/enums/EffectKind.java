package be.mjodheim.brewstead.enums;

/**
 * Effets temporaires accordés par une gorgée de breuvage.
 * L'ampleur est exprimée en pourcentage, sauf mention contraire.
 */
public enum EffectKind {

    /** Rien de particulier : ça se boit, c'est déjà ça. */
    AUCUN("Sans effet notable", false),

    MAIN_VERTE("Les cultures poussent plus vite", true),
    BOURDONNEMENT("Les ruches travaillent plus vite", true),
    FEU_SOUS_LA_CUVE("Les brassins fermentent plus vite", true),
    INSPIRATION("Tes brassins sortent d'une meilleure qualité", true),
    BOURSE_PERCEE("Les récompenses rapportent plus de pièces", true),
    LANGUE_DOREE("Les livraisons rapportent plus de réputation", true),
    MAIN_LOURDE("Tu renverses la moitié : qualité en baisse", false),
    SOMMEIL_DE_L_OURS("Tout traîne un peu, toi le premier", false),
    VISION_DOUBLE("Tu vois deux fois plus de tonneaux qu'il n'y en a", false),
    CHANT_DU_FJORD("Tu chantes. Fort. Les voisins apprécient moyennement.", false),
    COURAGE_LIQUIDE("Tu te crois capable de tout. Tu ne l'es pas.", false),
    HOQUET_RUNIQUE("Chaque hoquet déplace légèrement une voyelle", false);

    private final String label;
    private final boolean beneficial;

    EffectKind(String label, boolean beneficial) {
        this.label = label;
        this.beneficial = beneficial;
    }

    public String getLabel() {
        return label;
    }

    public boolean isBeneficial() {
        return beneficial;
    }

    /** Un effet purement narratif ne touche à aucun calcul du jeu. */
    public boolean isCosmetic() {
        return this == VISION_DOUBLE || this == CHANT_DU_FJORD
                || this == COURAGE_LIQUIDE || this == HOQUET_RUNIQUE;
    }
}
