package be.mjodheim.brewstead.dto.tavern;

public record TavernRoomSummaryResponse(
        Long id, String code, String name, String type,
        int occupancy, int capacity, boolean current
) {
}
