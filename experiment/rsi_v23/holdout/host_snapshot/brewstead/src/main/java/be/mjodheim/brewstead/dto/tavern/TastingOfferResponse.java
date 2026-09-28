package be.mjodheim.brewstead.dto.tavern;

import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.Rarity;

import java.time.LocalDateTime;

public record TastingOfferResponse(
        Long id,
        Long sellerId,
        String seller,
        String recipeName,
        Rarity rarity,
        Integer quality,
        EffectKind effectKind,
        String effectLabel,
        String flavour,
        int servings,
        int price,
        String note,
        boolean mine,
        LocalDateTime openedAt
) {
}
