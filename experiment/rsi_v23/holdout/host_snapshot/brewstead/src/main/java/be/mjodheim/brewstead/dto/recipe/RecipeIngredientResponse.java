package be.mjodheim.brewstead.dto.recipe;

import be.mjodheim.brewstead.enums.Unit;

import java.math.BigDecimal;

public record RecipeIngredientResponse(
        Long ingredientId,
        String ingredientName,
        Unit unit,
        BigDecimal quantity
) {
}
