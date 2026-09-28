package be.mjodheim.brewstead.service;

import java.util.List;

/**
 * Le barème de l'agrandissement du domaine.
 *
 * <p>Les pièces entraient par les contrats, l'objectif du jour, les hauts
 * faits et les paliers de saison, et ne ressortaient jamais : les deux seules
 * dépenses du jeu sont des transferts entre joueurs. Une bourse qui ne fait
 * que grossir n'est pas une récompense, c'est un compteur.
 *
 * <p>Chaque palier coûte le double du précédent. C'est ce qui donne au
 * domaine un rythme de fond : le premier agrandissement tombe dans l'heure,
 * le dernier demande de s'être vraiment installé.
 */
public final class EstatePrices {

    /** Un domaine neuf arrive avec trois parcelles et deux ruches. */
    public static final int STARTING_FIELDS = 3;
    public static final int STARTING_HIVES = 2;

    public static final int MAX_FIELDS = 8;
    public static final int MAX_HIVES = 6;
    public static final int MAX_HIVE_LEVEL = 3;

    private static final int[] FIELDS = {400, 800, 1600, 3200, 6400};
    private static final int[] HIVES = {500, 1000, 2000, 4000};
    private static final int[] UPGRADES = {700, 1800};

    private EstatePrices() { }

    /** Prix de la parcelle suivante, ou {@code null} si le domaine est au complet. */
    public static Integer nextField(int owned) {
        return step(FIELDS, owned - STARTING_FIELDS, owned >= MAX_FIELDS);
    }

    /** Prix de la ruche suivante, ou {@code null} si le rucher est au complet. */
    public static Integer nextHive(int owned) {
        return step(HIVES, owned - STARTING_HIVES, owned >= MAX_HIVES);
    }

    /** Prix pour faire passer une ruche au niveau suivant, ou {@code null} au maximum. */
    public static Integer upgrade(int level) {
        return step(UPGRADES, level - 1, level >= MAX_HIVE_LEVEL);
    }

    /** Le barème des améliorations, du niveau 1 vers le 2, puis du 2 vers le 3. */
    public static List<Integer> upgrades() {
        return List.of(UPGRADES[0], UPGRADES[1]);
    }

    private static Integer step(int[] bareme, int rang, boolean complet) {
        if (complet) return null;
        return bareme[Math.min(Math.max(rang, 0), bareme.length - 1)];
    }
}
