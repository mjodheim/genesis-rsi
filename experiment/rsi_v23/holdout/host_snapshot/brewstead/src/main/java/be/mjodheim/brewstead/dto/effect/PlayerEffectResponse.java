package be.mjodheim.brewstead.dto.effect;

import be.mjodheim.brewstead.enums.EffectKind;

import java.time.LocalDateTime;

public record PlayerEffectResponse(
        Long id,
        EffectKind kind,
        String label,
        int magnitude,
        boolean beneficial,
        boolean cosmetic,
        LocalDateTime startedAt,
        LocalDateTime expiresAt,
        String source
) {
}
