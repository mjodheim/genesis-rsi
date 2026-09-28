package be.mjodheim.brewstead.dto.tavern;

import be.mjodheim.brewstead.enums.Avatar;

import java.time.LocalDateTime;

public record TavernMessageResponse(
        Long id,
        Long authorId,
        String author,
        Avatar avatar,
        String body,
        LocalDateTime postedAt
) {
}
