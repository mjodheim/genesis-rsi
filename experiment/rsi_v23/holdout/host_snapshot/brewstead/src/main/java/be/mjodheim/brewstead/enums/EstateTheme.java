package be.mjodheim.brewstead.enums;

public enum EstateTheme {
    NORDIQUE("Nordique"),
    AUTOMNE("Automne"),
    HIVER("Hiver"),
    SOLSTICE("Solstice");

    private final String label;

    EstateTheme(String label) { this.label = label; }
    public String getLabel() { return label; }
}
