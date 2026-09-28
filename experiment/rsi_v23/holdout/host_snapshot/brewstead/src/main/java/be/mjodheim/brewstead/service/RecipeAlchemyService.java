package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.enums.DrinkType;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.Rarity;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;

/**
 * Ce que donne un mélange inventé par un joueur.
 *
 * <p>Le joueur choisit ses ingrédients, jamais l'effet : sinon chacun
 * s'écrirait une recette « +30 % de pièces » le premier jour. L'effet est
 * déduit du mélange, et surtout il est <em>reproductible</em> — deux fois le
 * même dosage donne deux fois le même résultat. C'est ce qui rend la
 * recherche intéressante : on note ce qui marche, on recommence, on partage.
 */
@Service
public class RecipeAlchemyService {

    /** Un mélange banal ne fait rien : il faut chercher pour trouver. */
    private static final int SEUIL_CURIEUSE = 5;
    private static final int SEUIL_RARE = 8;
    private static final int SEUIL_LEGENDAIRE = 12;

    /** Les effets que peut révéler une recherche, et ce qu'ils demandent au mélange. */
    private static final Map<IngredientType, List<EffectKind>> AFFINITES = Map.of(
            IngredientType.HERB, List.of(EffectKind.MAIN_VERTE, EffectKind.BOURDONNEMENT, EffectKind.SOMMEIL_DE_L_OURS),
            IngredientType.SPICE, List.of(EffectKind.FEU_SOUS_LA_CUVE, EffectKind.COURAGE_LIQUIDE, EffectKind.HOQUET_RUNIQUE),
            IngredientType.FRUIT, List.of(EffectKind.LANGUE_DOREE, EffectKind.CHANT_DU_FJORD, EffectKind.VISION_DOUBLE),
            IngredientType.HONEY, List.of(EffectKind.INSPIRATION, EffectKind.BOURSE_PERCEE, EffectKind.LANGUE_DOREE),
            IngredientType.CEREAL, List.of(EffectKind.SOMMEIL_DE_L_OURS, EffectKind.INSPIRATION, EffectKind.MAIN_LOURDE),
            IngredientType.YEAST, List.of(EffectKind.FEU_SOUS_LA_CUVE, EffectKind.VISION_DOUBLE, EffectKind.MAIN_LOURDE),
            IngredientType.HOP, List.of(EffectKind.MAIN_VERTE, EffectKind.CHANT_DU_FJORD, EffectKind.MAIN_LOURDE)
    );

    private static final List<String> TOURNURES = List.of(
            "Ça sent %s de loin, et ça s'assume.",
            "Une gorgée %s, deux gorgées de trop.",
            "%s en tête, le fjord en fond de bouche.",
            "Le genre de breuvage %s qu'on ressert sans prévenir.",
            "%s, du courage, et pas beaucoup de mesure.",
            "On y trouve %s et une idée qu'on regrettera demain."
    );

    /** Ce qu'une recherche a donné : à recopier tel quel dans la recette. */
    public record Resultat(Rarity rarity, EffectKind effectKind, int magnitude, int durationMinutes, String flavour) {
    }

    /**
     * @param drinkType   le type visé par le brasseur
     * @param ingredients les ingrédients du mélange, dans l'ordre de la recette
     * @param quantites   les quantités correspondantes, même taille et même ordre
     */
    public Resultat analyser(DrinkType drinkType, List<Ingredient> ingredients, List<BigDecimal> quantites) {
        long graine = graine(drinkType, ingredients, quantites);
        EnumSet<IngredientType> types = EnumSet.noneOf(IngredientType.class);
        ingredients.forEach(ingredient -> types.add(ingredient.getType()));

        int score = score(types, ingredients.size());
        Rarity rarity = rarete(score);

        if (rarity == Rarity.COMMUNE) {
            return new Resultat(rarity, EffectKind.AUCUN, 0, 0, saveur(graine, ingredients));
        }

        EffectKind effet = effet(graine, types);
        int ampleur = ampleur(rarity, graine);
        int duree = 20 + (int) Math.floorMod(graine >> 7, 70L);
        return new Resultat(rarity, effet, ampleur, duree, saveur(graine, ingredients));
    }

    /** Plus le mélange est varié et audacieux, plus il a de chances de donner quelque chose. */
    private int score(EnumSet<IngredientType> types, int lignes) {
        int score = types.size() * 2;
        if (types.contains(IngredientType.SPICE)) score += 3;
        if (types.contains(IngredientType.HERB)) score += 2;
        if (types.contains(IngredientType.FRUIT)) score += 1;
        if (lignes >= 4) score += 2;
        return score;
    }

    private Rarity rarete(int score) {
        if (score >= SEUIL_LEGENDAIRE) return Rarity.LEGENDAIRE;
        if (score >= SEUIL_RARE) return Rarity.RARE;
        if (score >= SEUIL_CURIEUSE) return Rarity.CURIEUSE;
        return Rarity.COMMUNE;
    }

    /** L'effet suit l'ingrédient le plus marquant du mélange, la graine tranche entre ses trois voies. */
    private EffectKind effet(long graine, EnumSet<IngredientType> types) {
        List<EffectKind> voies = null;
        for (IngredientType type : List.of(IngredientType.SPICE, IngredientType.HERB, IngredientType.FRUIT,
                IngredientType.HONEY, IngredientType.YEAST, IngredientType.HOP, IngredientType.CEREAL)) {
            if (types.contains(type)) {
                voies = AFFINITES.get(type);
                break;
            }
        }
        if (voies == null || voies.isEmpty()) return EffectKind.AUCUN;
        return voies.get((int) Math.floorMod(graine >> 3, voies.size()));
    }

    private int ampleur(Rarity rarity, long graine) {
        int plancher = switch (rarity) {
            case LEGENDAIRE -> 18;
            case RARE -> 10;
            default -> 5;
        };
        int etendue = switch (rarity) {
            case LEGENDAIRE -> 13;
            case RARE -> 11;
            default -> 8;
        };
        return plancher + (int) Math.floorMod(graine >> 11, etendue);
    }

    private String saveur(long graine, List<Ingredient> ingredients) {
        List<Ingredient> tries = new ArrayList<>(ingredients);
        tries.sort(Comparator.comparing(Ingredient::getName));
        String vedette = tries.get((int) Math.floorMod(graine >> 17, tries.size())).getName().toLowerCase();
        String tournure = TOURNURES.get((int) Math.floorMod(graine >> 23, TOURNURES.size()));
        return String.format(tournure, elider(vedette));
    }

    /** « de l'orge », « du miel »… le français ne pardonne pas la concaténation brutale. */
    private String elider(String mot) {
        return "aeiouyéèêëàâîïôûùh".indexOf(mot.charAt(0)) >= 0 ? "d'" + mot : "de " + mot;
    }

    /**
     * Empreinte stable du mélange : mêmes ingrédients, mêmes dosages au dixième
     * près, même résultat — hier, aujourd'hui et sur n'importe quelle machine.
     */
    private long graine(DrinkType drinkType, List<Ingredient> ingredients, List<BigDecimal> quantites) {
        List<long[]> lignes = new ArrayList<>();
        for (int i = 0; i < ingredients.size(); i++) {
            long dose = quantites.get(i).setScale(1, RoundingMode.HALF_UP).unscaledValue().longValue();
            lignes.add(new long[] { ingredients.get(i).getId(), dose });
        }
        lignes.sort((a, b) -> a[0] != b[0] ? Long.compare(a[0], b[0]) : Long.compare(a[1], b[1]));

        long graine = 1469598103934665603L + drinkType.ordinal() * 1099511628211L;
        for (long[] ligne : lignes) {
            graine = (graine ^ ligne[0]) * 1099511628211L;
            graine = (graine ^ ligne[1]) * 1099511628211L;
        }
        return graine == Long.MIN_VALUE ? 0L : Math.abs(graine);
    }
}
