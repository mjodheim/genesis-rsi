package be.mjodheim.brewstead.dto.order;

public record NpcOrderLineResponse(
        Long recipeId,
        String recipeName,
        int quantity,
        int minQuality
) {
}
