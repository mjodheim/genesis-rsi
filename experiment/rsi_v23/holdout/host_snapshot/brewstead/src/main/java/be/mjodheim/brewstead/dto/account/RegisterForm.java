package be.mjodheim.brewstead.dto.account;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * Formulaire d'inscription. Classe et non record : Thymeleaf lit des getters.
 */
@Getter
@Setter
@NoArgsConstructor
public class RegisterForm {

    @NotBlank(message = "Choisis un nom de brasseur.")
    @Size(min = 3, max = 20, message = "Le nom de brasseur fait entre 3 et 20 caractères.")
    @Pattern(regexp = "[A-Za-z0-9_-]*", message = "Lettres, chiffres, tiret et tiret bas uniquement.")
    private String username;

    @NotBlank(message = "Choisis un mot de passe.")
    @Size(min = 8, max = 72, message = "Le mot de passe fait au moins 8 caractères.")
    private String password;

    @NotBlank(message = "Confirme ton mot de passe.")
    private String confirmation;
}
