package be.mjodheim.brewstead.enums;

public enum Specialization {
    CULTIVATEUR("Maître des terres", "Récoltes augmentées de 15 %."),
    BRASSEUR("Maître des cuves", "Qualité des brassins augmentée de 5 points."),
    MARCHAND("Voix du comptoir", "Pièces des commandes PNJ augmentées de 10 %.");

    private final String label;
    private final String description;

    Specialization(String label, String description) {
        this.label = label;
        this.description = description;
    }

    public String getLabel() { return label; }
    public String getDescription() { return description; }
}
