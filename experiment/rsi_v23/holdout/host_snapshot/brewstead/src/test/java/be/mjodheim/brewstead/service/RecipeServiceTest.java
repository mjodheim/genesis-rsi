package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.recipe.CreateRecipeRequest;
import be.mjodheim.brewstead.dto.recipe.RecipeIngredientRequest;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.RecipeIngredient;
import be.mjodheim.brewstead.enums.DrinkType;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.Rarity;
import be.mjodheim.brewstead.mapper.RecipeMapper;
import be.mjodheim.brewstead.repository.IngredientRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.RecipeIngredientRepository;
import be.mjodheim.brewstead.repository.RecipeRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.ingredient;
import static be.mjodheim.brewstead.TestData.player;
import static be.mjodheim.brewstead.TestData.recipe;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class RecipeServiceTest {

    @Mock RecipeRepository recipeRepository;
    @Mock RecipeIngredientRepository recipeIngredientRepository;
    @Mock IngredientRepository ingredientRepository;
    @Mock PlayerProfileRepository playerRepository;
    @Mock RecipeMapper mapper;
    @Spy RecipeAlchemyService alchemy = new RecipeAlchemyService();
    @InjectMocks RecipeService service;

    @Test
    void accessibleRecipeAllowsPublicAndOwnerButRejectsPrivateForeignRecipe() {
        Recipe publicRecipe = recipe(1);
        publicRecipe.setPublic(true);
        when(recipeRepository.findById(1L)).thenReturn(Optional.of(publicRecipe));
        assertSame(publicRecipe, service.getAccessibleRecipeEntity(10L, 1L));

        Recipe owned = recipe(2);
        owned.setPublic(false);
        owned.setOwner(player(10));
        when(recipeRepository.findById(2L)).thenReturn(Optional.of(owned));
        assertSame(owned, service.getAccessibleRecipeEntity(10L, 2L));

        Recipe foreign = recipe(3);
        foreign.setPublic(false);
        foreign.setOwner(player(11));
        when(recipeRepository.findById(3L)).thenReturn(Optional.of(foreign));
        assertThrows(IllegalStateException.class,
                () -> service.getAccessibleRecipeEntity(10L, 3L));
    }

    @Test
    void findAvailableRecipesRequiresExistingPlayer() {
        when(playerRepository.findById(7L)).thenReturn(Optional.empty());

        assertThrows(IllegalArgumentException.class,
                () -> service.findAvailableRecipes(7L));
        verifyNoInteractions(recipeRepository);
    }

    @Test
    void findAvailableRecipesReadsTheWholeGrimoireInTwoQueries() {
        when(playerRepository.findById(7L)).thenReturn(Optional.of(player(7)));
        Recipe first = recipe(1);
        Recipe second = recipe(2);
        Recipe bare = recipe(3);
        when(recipeRepository.findAvailableWithOwner(7L)).thenReturn(List.of(first, second, bare));

        Ingredient barley = ingredient(1, IngredientType.CEREAL);
        Ingredient honey = ingredient(2, IngredientType.HONEY);
        RecipeIngredient a = RecipeIngredient.builder().id(10L).recipe(first).ingredient(barley).quantity(BigDecimal.ONE).build();
        RecipeIngredient b = RecipeIngredient.builder().id(11L).recipe(second).ingredient(honey).quantity(BigDecimal.TEN).build();
        RecipeIngredient c = RecipeIngredient.builder().id(12L).recipe(first).ingredient(honey).quantity(BigDecimal.ONE).build();
        when(recipeIngredientRepository.findAllWithIngredientByRecipeIdIn(List.of(1L, 2L, 3L)))
                .thenReturn(List.of(a, b, c));

        service.findAvailableRecipes(7L);

        // Chaque recette reçoit ses propres lignes, dans l'ordre ; une recette
        // sans ligne reçoit une liste vide, pas celle de sa voisine.
        verify(mapper).toResponse(first, List.of(a, c));
        verify(mapper).toResponse(second, List.of(b));
        verify(mapper).toResponse(bare, List.of());
        // Plus de lecture recette par recette.
        verify(recipeIngredientRepository, never()).findAllByRecipeId(any());
    }

    @Test
    void findAvailableRecipesWithAnEmptyGrimoireAsksNothingMore() {
        when(playerRepository.findById(7L)).thenReturn(Optional.of(player(7)));
        when(recipeRepository.findAvailableWithOwner(7L)).thenReturn(List.of());

        assertTrue(service.findAvailableRecipes(7L).isEmpty());
        verifyNoInteractions(recipeIngredientRepository);
    }

    @Test
    void createRecipePersistsTrimmedRecipeAndIngredients() {
        PlayerProfile owner = player(7);
        Ingredient honey = ingredient(1, IngredientType.HONEY);
        Ingredient water = ingredient(2, IngredientType.WATER);
        CreateRecipeRequest request = new CreateRecipeRequest(
                7L, "  Mon Hydromel  ", DrinkType.values()[0],
                new BigDecimal("10.00"), 12, null,
                List.of(
                        new RecipeIngredientRequest(1L, new BigDecimal("2.000")),
                        new RecipeIngredientRequest(2L, new BigDecimal("8.000"))
                ));
        when(playerRepository.findById(7L)).thenReturn(Optional.of(owner));
        when(recipeRepository.save(any(Recipe.class))).thenAnswer(invocation -> {
            Recipe saved = invocation.getArgument(0);
            saved.setId(20L);
            return saved;
        });
        when(ingredientRepository.findById(1L)).thenReturn(Optional.of(honey));
        when(ingredientRepository.findById(2L)).thenReturn(Optional.of(water));

        service.createRecipe(request);

        ArgumentCaptor<Recipe> recipeCaptor = ArgumentCaptor.forClass(Recipe.class);
        verify(recipeRepository).save(recipeCaptor.capture());
        assertEquals("Mon Hydromel", recipeCaptor.getValue().getName());
        assertFalse(recipeCaptor.getValue().isPublic());
        assertSame(owner, recipeCaptor.getValue().getOwner());

        verify(recipeIngredientRepository).saveAll(argThat(lines -> {
            int count = 0;
            for (RecipeIngredient line : lines) {
                count++;
                if (line.getRecipe().getId() != 20L || line.getQuantity().signum() <= 0) return false;
            }
            return count == 2;
        }));
    }

    @Test
    void createRecipeValidatesRequiredFieldsAndQuantities() {
        CreateRecipeRequest valid = validRequest();

        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(null, valid.name(), valid.drinkType(), valid.baseVolume(),
                        valid.fermentationDurationHours(), null, valid.ingredients())));
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, " ", valid.drinkType(), valid.baseVolume(),
                        valid.fermentationDurationHours(), null, valid.ingredients())));
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", null, valid.baseVolume(),
                        valid.fermentationDurationHours(), null, valid.ingredients())));
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), BigDecimal.ZERO,
                        valid.fermentationDurationHours(), null, valid.ingredients())));
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), valid.baseVolume(),
                        0, null, valid.ingredients())));
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), valid.baseVolume(),
                        1, null, List.of())));
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), valid.baseVolume(),
                        1, null, List.of(new RecipeIngredientRequest(1L, BigDecimal.ZERO)))));
    }

    /** Un laboratoire n'est pas une porte ouverte sur la base de données. */
    @Test
    void createRecipeRefusesOversizedRequests() {
        CreateRecipeRequest valid = validRequest();
        List<RecipeIngredientRequest> nine = java.util.stream.IntStream.rangeClosed(1, 9)
                .mapToObj(i -> new RecipeIngredientRequest((long) i, BigDecimal.ONE))
                .toList();

        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X".repeat(61), valid.drinkType(), valid.baseVolume(),
                        1, null, valid.ingredients())), "nom trop long");
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), new BigDecimal("201"),
                        1, null, valid.ingredients())), "cuve trop grande");
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), valid.baseVolume(),
                        null, 4, valid.ingredients())), "fermentation trop courte");
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), valid.baseVolume(),
                        null, 10081, valid.ingredients())), "fermentation trop longue");
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), valid.baseVolume(),
                        1, null, nine)), "trop d'ingrédients");
        assertThrows(IllegalArgumentException.class, () -> service.createRecipe(
                new CreateRecipeRequest(1L, "X", valid.drinkType(), valid.baseVolume(),
                        1, null, List.of(new RecipeIngredientRequest(1L, new BigDecimal("501"))))),
                "dose démesurée");
    }

    @Test
    void createRecipeRefusesAFullGrimoireOrADuplicateName() {
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player(1)));
        when(recipeRepository.countByOwnerId(1L)).thenReturn(60L);
        assertThrows(IllegalStateException.class, () -> service.createRecipe(validRequest()));

        reset(recipeRepository);
        when(recipeRepository.countByOwnerId(1L)).thenReturn(3L);
        when(recipeRepository.existsByOwnerIdAndNameIgnoreCase(1L, "Test")).thenReturn(true);
        assertThrows(IllegalStateException.class, () -> service.createRecipe(validRequest()));
    }

    /**
     * Le mélange décide : un ajout d'épice révèle un effet, et deux fois le
     * même dosage donne deux fois le même breuvage.
     */
    @Test
    void createRecipeDerivesRarityAndEffectFromTheMix() {
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player(1)));
        when(recipeRepository.save(any(Recipe.class))).thenAnswer(invocation -> {
            Recipe saved = invocation.getArgument(0);
            saved.setId(42L);
            return saved;
        });
        when(ingredientRepository.findById(1L)).thenReturn(Optional.of(ingredient(1, IngredientType.HONEY)));
        when(ingredientRepository.findById(2L)).thenReturn(Optional.of(ingredient(2, IngredientType.WATER)));
        when(ingredientRepository.findById(3L)).thenReturn(Optional.of(ingredient(3, IngredientType.SPICE)));
        when(ingredientRepository.findById(4L)).thenReturn(Optional.of(ingredient(4, IngredientType.HERB)));

        Recipe plain = saveAndCapture(mix(1L, 2L));
        assertEquals(Rarity.COMMUNE, plain.getRarity());
        assertEquals(EffectKind.AUCUN, plain.getEffectKind());
        assertNotNull(plain.getFlavour(), "même sans effet, la fiche se lit");

        Recipe spiced = saveAndCapture(mix(1L, 2L, 3L, 4L));
        assertNotEquals(Rarity.COMMUNE, spiced.getRarity());
        assertNotEquals(EffectKind.AUCUN, spiced.getEffectKind());
        assertTrue(spiced.getEffectMagnitude() > 0 && spiced.getEffectMagnitude() <= 50);
        assertTrue(spiced.getEffectDurationMinutes() > 0);

        Recipe again = saveAndCapture(mix(1L, 2L, 3L, 4L));
        assertEquals(spiced.getEffectKind(), again.getEffectKind(), "la recherche est reproductible");
        assertEquals(spiced.getEffectMagnitude(), again.getEffectMagnitude());
        assertEquals(spiced.getFlavour(), again.getFlavour());
    }

    /** La durée fine prime sur les heures, et l'entière reste cohérente. */
    @Test
    void createRecipeKeepsMinutesAndRoundsHoursUp() {
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player(1)));
        when(recipeRepository.save(any(Recipe.class))).thenAnswer(i -> i.getArgument(0));
        when(ingredientRepository.findById(1L)).thenReturn(Optional.of(ingredient(1, IngredientType.HONEY)));

        Recipe saved = saveAndCapture(new CreateRecipeRequest(
                1L, "Vite fait", DrinkType.values()[0], BigDecimal.TEN, null, 25,
                List.of(new RecipeIngredientRequest(1L, BigDecimal.ONE))));

        assertEquals(25, saved.getFermentationMinutes());
        assertEquals(1, saved.getFermentationDurationHours());
    }

    private CreateRecipeRequest mix(Long... ingredientIds) {
        return new CreateRecipeRequest(
                1L, "Essai " + List.of(ingredientIds), DrinkType.values()[0], BigDecimal.TEN, null, 60,
                java.util.Arrays.stream(ingredientIds)
                        .map(id -> new RecipeIngredientRequest(id, new BigDecimal("2.0")))
                        .toList());
    }

    private Recipe saveAndCapture(CreateRecipeRequest request) {
        service.createRecipe(request);
        ArgumentCaptor<Recipe> captor = ArgumentCaptor.forClass(Recipe.class);
        verify(recipeRepository, atLeastOnce()).save(captor.capture());
        return captor.getValue();
    }

    @Test
    void createRecipeRejectsDuplicateIngredient() {
        CreateRecipeRequest request = new CreateRecipeRequest(
                1L, "X", DrinkType.values()[0], BigDecimal.TEN, 1, null,
                List.of(
                        new RecipeIngredientRequest(1L, BigDecimal.ONE),
                        new RecipeIngredientRequest(1L, new BigDecimal("2"))
                ));

        assertThrows(IllegalArgumentException.class,
                () -> service.createRecipe(request));
    }

    @Test
    void createRecipeRejectsMissingIngredientEntity() {
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player(1)));
        when(ingredientRepository.findById(1L)).thenReturn(Optional.empty());

        assertThrows(IllegalArgumentException.class,
                () -> service.createRecipe(validRequest()));
    }

    private CreateRecipeRequest validRequest() {
        return new CreateRecipeRequest(
                1L, "Test", DrinkType.values()[0], BigDecimal.TEN, 1, null,
                List.of(new RecipeIngredientRequest(1L, BigDecimal.ONE)));
    }
}
