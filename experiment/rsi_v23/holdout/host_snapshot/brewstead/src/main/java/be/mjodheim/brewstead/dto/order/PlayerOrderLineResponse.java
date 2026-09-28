package be.mjodheim.brewstead.dto.order;

import be.mjodheim.brewstead.enums.Unit;

import java.math.BigDecimal;

public record PlayerOrderLineResponse(
        Long ingredientId,
        String ingredientName,
        Unit unit,
        BigDecimal quantity
) {
}
