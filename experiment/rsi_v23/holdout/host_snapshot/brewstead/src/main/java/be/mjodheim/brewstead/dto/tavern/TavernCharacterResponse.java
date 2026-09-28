package be.mjodheim.brewstead.dto.tavern;

import be.mjodheim.brewstead.enums.Avatar;

public record TavernCharacterResponse(
        Avatar avatar,
        String body,
        String hair,
        String outfit,
        String palette,
        String accessory
) {
}
