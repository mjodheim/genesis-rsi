package be.mjodheim.brewstead.dto.tavern;

import jakarta.validation.constraints.Size;

public record CreateTavernRoomRequest(
        @Size(max = 40, message = "40 caractères au maximum.")
        String name
) {
}
