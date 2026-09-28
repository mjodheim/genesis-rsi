package be.mjodheim.brewstead.dto.catalog;

import java.math.BigDecimal;

public record CropResponse(
        Long id,
        String name,
        Long ingredientId,
        String ingredientName,
        int growDurationMinutes,
        BigDecimal yieldQuantity
) {
}
