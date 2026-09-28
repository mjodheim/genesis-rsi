package be.mjodheim.brewstead.dto.tavern;

import java.util.List;

public record TavernLobbyResponse(List<TavernRoomSummaryResponse> rooms, Long currentRoomId) {
}
