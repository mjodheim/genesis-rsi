package be.mjodheim.brewstead.dto.brew;

import be.mjodheim.brewstead.dto.effect.PlayerEffectResponse;

/** Ce qu'on retient d'une gorgée : le nom, la phrase, et ce que ça fait. */
public record TastingResponse(
        String recipeName,
        String flavour,
        PlayerEffectResponse effect
) {
}
