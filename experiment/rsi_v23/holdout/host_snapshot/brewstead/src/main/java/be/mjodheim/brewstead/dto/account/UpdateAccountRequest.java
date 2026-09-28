package be.mjodheim.brewstead.dto.account;

import jakarta.validation.constraints.Size;

public record UpdateAccountRequest(
        @Size(max = 30, message = "Le nom affiché ne peut pas dépasser 30 caractères.")
        String displayName,
        String avatar
) {
}
