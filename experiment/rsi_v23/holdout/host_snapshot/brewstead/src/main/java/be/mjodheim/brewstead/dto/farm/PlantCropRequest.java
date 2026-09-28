package be.mjodheim.brewstead.dto.farm;

public record PlantCropRequest(
        Long fieldId,
        Long cropId
) {
}
