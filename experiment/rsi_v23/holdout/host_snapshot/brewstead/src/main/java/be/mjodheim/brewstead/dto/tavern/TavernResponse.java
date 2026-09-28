package be.mjodheim.brewstead.dto.tavern;

import java.util.List;

public record TavernResponse(
        List<TavernPlayerResponse> notablePlayers,
        long openPlayerOrders
) {
}
