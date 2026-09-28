package be.mjodheim.brewstead.dto.tavern;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

public record OpenOfferRequest(
        Long batchId,

        @Min(value = 1, message = "Il faut proposer au moins un service.")
        @Max(value = 40, message = "Quarante services, c'est déjà une fête.")
        int servings,

        @Min(value = 0, message = "Un prix ne peut pas être négatif.")
        @Max(value = 5000, message = "Personne ne paiera ça.")
        int price,

        @Size(max = 140, message = "140 caractères pour vanter ta production.")
        String note
) {
}
