package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.apiary.BeehiveResponse;
import be.mjodheim.brewstead.dto.brew.BatchResponse;
import be.mjodheim.brewstead.dto.farm.PlayerFieldResponse;
import be.mjodheim.brewstead.dto.game.GameStateResponse;
import be.mjodheim.brewstead.dto.inventory.PlayerInventoryResponse;
import be.mjodheim.brewstead.dto.order.NpcOrderResponse;
import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.dto.recipe.RecipeResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class GameStateServiceTest {

    @Mock PlayerService playerService;
    @Mock FarmService farmService;
    @Mock ApiaryService apiaryService;
    @Mock InventoryService inventoryService;
    @Mock RecipeService recipeService;
    @Mock BrewService brewService;
    @Mock NpcOrderService npcOrderService;
    @InjectMocks GameStateService service;

    @Test
    void aggregatesCompletePlayerState() {
        PlayerProfileResponse player = mock(PlayerProfileResponse.class);
        List<PlayerFieldResponse> fields = List.of(mock(PlayerFieldResponse.class));
        List<BeehiveResponse> hives = List.of(mock(BeehiveResponse.class));
        List<PlayerInventoryResponse> inventory = List.of(mock(PlayerInventoryResponse.class));
        List<RecipeResponse> recipes = List.of(mock(RecipeResponse.class));
        List<BatchResponse> batches = List.of(mock(BatchResponse.class));
        List<NpcOrderResponse> orders = List.of(mock(NpcOrderResponse.class));

        when(playerService.getPlayer(7L)).thenReturn(player);
        when(farmService.findAllFields(7L)).thenReturn(fields);
        when(apiaryService.findAllHives(7L)).thenReturn(hives);
        when(inventoryService.getPlayerInventory(7L)).thenReturn(inventory);
        when(recipeService.findAvailableRecipes(7L)).thenReturn(recipes);
        when(brewService.findPlayerBatches(7L)).thenReturn(batches);
        when(npcOrderService.findAllOrders(7L)).thenReturn(orders);

        GameStateResponse state = service.getState(7L);

        assertSame(player, state.player());
        assertSame(fields, state.fields());
        assertSame(hives, state.hives());
        assertSame(inventory, state.inventory());
        assertSame(recipes, state.recipes());
        assertSame(batches, state.batches());
        assertSame(orders, state.npcOrders());
    }
}
