package be.mjodheim.brewstead.dto.recipe;

import be.mjodheim.brewstead.enums.DrinkType;

import java.math.BigDecimal;
import java.util.List;

/**
 * Une recette inventée au laboratoire.
 *
 * <p>Ni rareté ni effet : ils se déduisent du mélange, le brasseur ne les
 * décide pas. La durée se donne en minutes ; les heures restent acceptées
 * pour les appels plus anciens.
 */
public record CreateRecipeRequest(
        Long ownerId,
        String name,
        DrinkType drinkType,
        BigDecimal baseVolume,
        Integer fermentationDurationHours,
        Integer fermentationDurationMinutes,
        List<RecipeIngredientRequest> ingredients
) {

    /** La durée voulue, en minutes, quelle que soit l'unité reçue. */
    public int minutes() {
        if (fermentationDurationMinutes != null && fermentationDurationMinutes > 0) {
            return fermentationDurationMinutes;
        }
        return fermentationDurationHours == null ? 0 : fermentationDurationHours * 60;
    }
}
