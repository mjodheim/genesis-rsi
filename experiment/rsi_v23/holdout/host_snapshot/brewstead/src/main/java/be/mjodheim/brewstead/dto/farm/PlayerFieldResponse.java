package be.mjodheim.brewstead.dto.farm;

import be.mjodheim.brewstead.enums.FieldStatus;

import java.time.LocalDateTime;

public record PlayerFieldResponse(
        Long id,
        String cropName,
        LocalDateTime plantedAt,
        LocalDateTime readyAt,
        FieldStatus status
) {
}
