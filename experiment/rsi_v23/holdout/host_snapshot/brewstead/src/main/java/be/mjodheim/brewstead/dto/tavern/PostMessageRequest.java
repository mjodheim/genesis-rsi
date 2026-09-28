package be.mjodheim.brewstead.dto.tavern;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record PostMessageRequest(
        @NotBlank(message = "Dis quelque chose.")
        @Size(max = 280, message = "280 caractères, pas un de plus.")
        String body
) {
}
