package be.mjodheim.brewstead.dto.tavern;

import java.util.List;

public record TavernRoomSnapshot(
        Long id,
        String code,
        String name,
        String type,
        int capacity,
        List<String> seats,
        List<TavernPresenceResponse> players,
        List<TavernMessageResponse> messages,
        List<TastingOfferResponse> offers
) {
}
