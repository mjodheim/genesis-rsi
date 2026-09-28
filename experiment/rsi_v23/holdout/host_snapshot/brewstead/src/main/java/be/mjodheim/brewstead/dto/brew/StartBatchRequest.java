package be.mjodheim.brewstead.dto.brew;

import java.math.BigDecimal;

public record StartBatchRequest(
        Long playerId,
        Long recipeId,
        BigDecimal volume
) {
}
