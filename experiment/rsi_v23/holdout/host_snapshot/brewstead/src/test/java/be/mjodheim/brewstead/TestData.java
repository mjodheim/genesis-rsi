package be.mjodheim.brewstead;

import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public final class TestData {

    private TestData() {
    }

    public static User user(long id) {
        return User.builder()
                .id(id)
                .username("user" + id)
                .password("encoded")
                .role(UserRole.PLAYER)
                .build();
    }

    public static PlayerProfile player(long id) {
        return PlayerProfile.builder()
                .id(id)
                .user(user(id))
                .level(1)
                .experience(0)
                .coin(500)
                .reputation(0)
                .build();
    }

    public static Ingredient ingredient(long id, IngredientType type) {
        return Ingredient.builder()
                .id(id)
                .name(type.name() + "-" + id)
                .type(type)
                .unit(Unit.values()[0])
                .baseValue(BigDecimal.ONE)
                .build();
    }

    public static Recipe recipe(long id) {
        return Recipe.builder()
                .id(id)
                .name("Recipe " + id)
                .drinkType(DrinkType.values()[0])
                .baseVolume(new BigDecimal("10.00"))
                .fermentationDurationHours(1)
                .fermentationDurationMinutes(60)
                .isPublic(true)
                .effectKind(EffectKind.AUCUN)
                .effectMagnitude(0)
                .effectDurationMinutes(0)
                .rarity(Rarity.COMMUNE)
                .flavour("Test flavour")
                .build();
    }

    public static Batch batch(long id, PlayerProfile player, Recipe recipe) {
        return Batch.builder()
                .id(id)
                .player(player)
                .recipe(recipe)
                .volume(new BigDecimal("10.00"))
                .startedAt(LocalDateTime.now().minusMinutes(30))
                .readyAt(LocalDateTime.now().plusMinutes(30))
                .status(BatchStatus.FERMENTING)
                .build();
    }
}
