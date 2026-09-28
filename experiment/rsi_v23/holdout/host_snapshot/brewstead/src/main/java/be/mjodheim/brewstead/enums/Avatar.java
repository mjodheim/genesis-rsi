package be.mjodheim.brewstead.enums;

/**
 * Emblèmes disponibles pour la vignette du joueur.
 * Le nom sert de clé côté interface pour retrouver le pictogramme correspondant.
 */
public enum Avatar {
    CERF,
    CORBEAU,
    OURS,
    LOUP,
    ABEILLE,
    ORGE,
    TONNEAU,
    MARTEAU;

    public static final Avatar DEFAULT = CERF;

    public static Avatar fromNullable(String value) {
        if (value == null || value.isBlank()) {
            return DEFAULT;
        }
        try {
            return valueOf(value.trim().toUpperCase());
        } catch (IllegalArgumentException unknown) {
            throw new IllegalArgumentException("Emblème inconnu : " + value);
        }
    }
}
