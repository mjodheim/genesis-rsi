package be.mjodheim.brewstead.dto.progression;

import jakarta.validation.constraints.NotBlank;

public record ChooseThemeRequest(@NotBlank String theme) { }
