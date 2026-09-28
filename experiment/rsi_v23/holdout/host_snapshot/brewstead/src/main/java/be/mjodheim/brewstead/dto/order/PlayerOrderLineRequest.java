package be.mjodheim.brewstead.dto.order;

import java.math.BigDecimal;

public record PlayerOrderLineRequest(
        Long ingredientId,
        BigDecimal quantity
) {
}
