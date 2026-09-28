package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.recipe.CreateRecipeRequest;
import be.mjodheim.brewstead.dto.recipe.RecipeIngredientRequest;
import be.mjodheim.brewstead.enums.DrinkType;
import be.mjodheim.brewstead.service.CurrentPlayerService;
import be.mjodheim.brewstead.service.RecipeService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.security.Principal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class RecipeControllerTest {

    @Mock RecipeService recipeService;
    @Mock CurrentPlayerService currentPlayer;
    @InjectMocks RecipeController controller;

    private final Principal principal = () -> "eirik";

    @Test
    void listingRecipesRequiresClaimedPlayerToMatchSession() {
        when(currentPlayer.requireSelf(principal, 7L)).thenReturn(7L);

        controller.recipes(principal, 7L);

        verify(currentPlayer).requireSelf(principal, 7L);
        verify(recipeService).findAvailableRecipes(7L);
    }

    @Test
    void readingRecipeRequiresClaimedPlayerToMatchSession() {
        when(currentPlayer.requireSelf(principal, 7L)).thenReturn(7L);

        controller.recipe(principal, 20L, 7L);

        verify(currentPlayer).requireSelf(principal, 7L);
        verify(recipeService).findRecipe(7L, 20L);
    }

    @Test
    void creatingRecipeRequiresOwnerToMatchSession() {
        CreateRecipeRequest request = new CreateRecipeRequest(
                7L, "Hydromel", DrinkType.values()[0], BigDecimal.TEN, 1, null,
                List.of(new RecipeIngredientRequest(1L, BigDecimal.ONE)));
        when(currentPlayer.requireSelf(principal, 7L)).thenReturn(7L);

        controller.create(principal, request);

        verify(currentPlayer).requireSelf(principal, 7L);
        verify(recipeService).createRecipe(request);
    }

    /** Le client n'a pas à répéter son identité : la session fait foi. */
    @Test
    void creatingRecipeFillsTheOwnerFromTheSession() {
        CreateRecipeRequest anonymous = new CreateRecipeRequest(
                null, "Hydromel", DrinkType.values()[0], BigDecimal.TEN, null, 45,
                List.of(new RecipeIngredientRequest(1L, BigDecimal.ONE)));
        when(currentPlayer.requireSelf(principal, null)).thenReturn(7L);

        controller.create(principal, anonymous);

        ArgumentCaptor<CreateRecipeRequest> sent = ArgumentCaptor.forClass(CreateRecipeRequest.class);
        verify(recipeService).createRecipe(sent.capture());
        assertEquals(7L, sent.getValue().ownerId());
        assertEquals(45, sent.getValue().minutes());
    }
}
