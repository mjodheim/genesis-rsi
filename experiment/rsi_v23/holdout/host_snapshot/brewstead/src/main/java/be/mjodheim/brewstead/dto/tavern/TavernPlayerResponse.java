package be.mjodheim.brewstead.dto.tavern;

public record TavernPlayerResponse(
        Long playerId,
        String username,
        int level,
        int reputation
) {
}
