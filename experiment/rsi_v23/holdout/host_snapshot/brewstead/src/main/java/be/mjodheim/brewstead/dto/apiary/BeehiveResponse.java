package be.mjodheim.brewstead.dto.apiary;

import be.mjodheim.brewstead.enums.BehiveStatus;

import java.time.LocalDateTime;

public record BeehiveResponse(
        Long id,
        int level,
        LocalDateTime startedAt,
        LocalDateTime readyAt,
        BehiveStatus status
) {
}
