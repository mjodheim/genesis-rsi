package be.mjodheim.brewstead.dto.tavern;

import java.time.LocalDateTime;

public record TavernPresenceResponse(
        Long playerId,
        String name,
        int level,
        int reputation,
        String seatKey,
        boolean self,
        TavernCharacterResponse character,
        String emote,
        LocalDateTime emoteAt
) {
}
