package be.mjodheim.brewstead.dto.inventory;

import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerProfile;

import java.math.BigDecimal;

public record IngredientRequest(
        Long playerId,
        Long ingredientId,
        BigDecimal quantity
) {
}
