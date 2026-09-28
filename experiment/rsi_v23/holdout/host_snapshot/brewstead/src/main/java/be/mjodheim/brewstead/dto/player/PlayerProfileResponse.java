package be.mjodheim.brewstead.dto.player;

import be.mjodheim.brewstead.enums.Avatar;

public record PlayerProfileResponse(
        Long id,
        String username,
        String displayName,
        Avatar avatar,
        int level,
        int experience,
        int coins,
        int reputation
) {
}
