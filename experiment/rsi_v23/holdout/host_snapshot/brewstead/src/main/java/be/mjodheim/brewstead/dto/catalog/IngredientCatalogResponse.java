package be.mjodheim.brewstead.dto.catalog;

import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.Unit;

import java.math.BigDecimal;

public record IngredientCatalogResponse(
        Long id,
        String name,
        IngredientType type,
        Unit unit,
        BigDecimal baseValue
) {
}
