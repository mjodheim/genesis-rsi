package be.mjodheim.brewstead.dto.recipe;

import be.mjodheim.brewstead.enums.DrinkType;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.Rarity;

import java.math.BigDecimal;
import java.util.List;

public record RecipeResponse(
        Long id,
        Long ownerId,
        String ownerUsername,
        String name,
        DrinkType drinkType,
        BigDecimal baseVolume,
        int fermentationDurationHours,
        int fermentationDurationMinutes,
        Rarity rarity,
        EffectKind effectKind,
        String effectLabel,
        int effectMagnitude,
        int effectDurationMinutes,
        String flavour,
        boolean isPublic,
        List<RecipeIngredientResponse> ingredients
) {
}
