package be.mjodheim.brewstead.dto.account;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChangePasswordRequest(
        @NotBlank(message = "Indique ton mot de passe actuel.")
        String currentPassword,

        @NotBlank(message = "Choisis un nouveau mot de passe.")
        @Size(min = 8, max = 72, message = "Le mot de passe fait au moins 8 caractères.")
        String newPassword,

        @NotBlank(message = "Confirme le nouveau mot de passe.")
        String confirmation
) {
}
