package be.mjodheim.brewstead.dto.brew;

import be.mjodheim.brewstead.enums.BatchStatus;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record BatchResponse(
        Long id,
        Long recipeId,
        String recipeName,
        BigDecimal volume,
        LocalDateTime startedAt,
        LocalDateTime readyAt,
        BatchStatus status,
        Integer quality
) {
}
