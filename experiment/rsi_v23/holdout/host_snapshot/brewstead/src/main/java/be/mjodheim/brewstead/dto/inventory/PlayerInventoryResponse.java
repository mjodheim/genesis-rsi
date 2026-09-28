package be.mjodheim.brewstead.dto.inventory;

import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.Unit;

import java.math.BigDecimal;

public record PlayerInventoryResponse(
        Long id,
        Long ingredientId,
        String ingredientName,
        IngredientType type,
        Unit unit,
        BigDecimal quantity
) {
}
