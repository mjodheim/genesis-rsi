package be.mjodheim.brewstead.dto.recipe;

import java.math.BigDecimal;

public record RecipeIngredientRequest(
        Long ingredientId,
        BigDecimal quantity
) {
}
