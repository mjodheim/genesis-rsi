package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.brew.StartBatchRequest;
import be.mjodheim.brewstead.dto.farm.PlantCropRequest;
import be.mjodheim.brewstead.dto.game.HarvestAllResponse;
import be.mjodheim.brewstead.dto.order.CreatePlayerOrderRequest;
import be.mjodheim.brewstead.dto.order.PlayerOrderLineRequest;
import be.mjodheim.brewstead.dto.tavern.OpenOfferRequest;
import be.mjodheim.brewstead.dto.tavern.PostMessageRequest;
import be.mjodheim.brewstead.service.*;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.security.Principal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

class OwnedResourceControllersTest {

    private final Principal principal = () -> "eirik";

    @Test
    void apiaryControllerAlwaysResolvesSessionPlayer() {
        ApiaryService service = mock(ApiaryService.class);
        CurrentPlayerService current = mock(CurrentPlayerService.class);
        ApiaryController controller = new ApiaryController(service, current);
        when(current.requireSelf(principal, 7L)).thenReturn(7L);
        when(current.id(principal)).thenReturn(7L);

        controller.hives(principal, 7L);
        controller.start(principal, 1L);
        controller.refresh(principal, 2L);
        controller.harvest(principal, 3L);

        verify(service).findAllHives(7L);
        verify(service).startProduction(7L, 1L);
        verify(service).updateHiveStatus(7L, 2L);
        verify(service).harvest(7L, 3L);
    }

    @Test
    void farmControllerAlwaysResolvesSessionPlayer() {
        FarmService service = mock(FarmService.class);
        CurrentPlayerService current = mock(CurrentPlayerService.class);
        FarmController controller = new FarmController(service, current);
        when(current.requireSelf(principal, 7L)).thenReturn(7L);
        when(current.id(principal)).thenReturn(7L);
        PlantCropRequest request = new PlantCropRequest(2L, 3L);

        controller.fields(principal, 7L);
        controller.plant(principal, request);
        controller.refresh(principal, 2L);
        controller.harvest(principal, 2L);

        verify(service).findAllFields(7L);
        verify(service).plant(7L, request);
        verify(service).updateFieldStatus(7L, 2L);
        verify(service).harvest(7L, 2L);
    }

    @Test
    void breweryControllerNeverTrustsRequestPlayerId() {
        BrewService service = mock(BrewService.class);
        CurrentPlayerService current = mock(CurrentPlayerService.class);
        AccountService account = mock(AccountService.class);
        BrewController controller = new BrewController(service, current, account);
        StartBatchRequest request = new StartBatchRequest(7L, 3L, BigDecimal.TEN);
        when(current.requireSelf(principal, 7L)).thenReturn(7L);
        when(current.id(principal)).thenReturn(7L);

        controller.batches(principal, 7L);
        controller.start(principal, request);
        controller.taste(principal, 4L);
        controller.refresh(principal, 4L);

        verify(service).findPlayerBatches(7L);
        verify(service).startBatch(7L, request);
        verify(service).taste(7L, 4L);
        verify(service).updateBatchStatus(7L, 4L);
    }

    @Test
    void inventoryPlayerAndStateControllersRequireSelf() {
        CurrentPlayerService current = mock(CurrentPlayerService.class);
        when(current.requireSelf(principal, 7L)).thenReturn(7L);

        InventoryService inventory = mock(InventoryService.class);
        new InventoryController(inventory, current).inventory(principal, 7L);
        verify(inventory).getPlayerInventory(7L);

        PlayerService players = mock(PlayerService.class);
        new PlayerController(players, current).getPlayer(principal, 7L);
        verify(players).getPlayer(7L);

        GameStateService state = mock(GameStateService.class);
        FarmService farm = mock(FarmService.class);
        ApiaryService apiary = mock(ApiaryService.class);
        GameStateController stateController = new GameStateController(state, farm, apiary, current);
        stateController.getState(principal, 7L);
        verify(state).getState(7L);

        // La tournée de récolte passe par la même vérification de session.
        when(farm.harvestAll(7L)).thenReturn(2);
        when(apiary.harvestAll(7L)).thenReturn(1);
        HarvestAllResponse report = stateController.harvestAll(principal, 7L);
        assertEquals(2, report.fields());
        assertEquals(1, report.hives());
        assertEquals(3, report.total());
    }

    @Test
    void npcOrderControllerResolvesPlayerForEveryOwnedAction() {
        NpcOrderService service = mock(NpcOrderService.class);
        CurrentPlayerService current = mock(CurrentPlayerService.class);
        NpcOrderController controller = new NpcOrderController(service, current);
        when(current.requireSelf(principal, 7L)).thenReturn(7L);
        when(current.id(principal)).thenReturn(7L);

        controller.orders(principal, 7L);
        controller.generate(principal, 7L);
        controller.accept(principal, 10L);
        controller.complete(principal, 10L);

        verify(service).findAllOrders(7L);
        verify(service).generateOrder(7L);
        verify(service).acceptOrder(7L, 10L);
        verify(service).completeOrder(7L, 10L);
    }

    @Test
    void playerOrderControllerGuardsCreatorFulfillerAndCanceller() {
        PlayerOrderService service = mock(PlayerOrderService.class);
        CurrentPlayerService current = mock(CurrentPlayerService.class);
        PlayerOrderController controller = new PlayerOrderController(service, current);
        CreatePlayerOrderRequest request = new CreatePlayerOrderRequest(
                7L, 100, 60,
                List.of(new PlayerOrderLineRequest(1L, BigDecimal.ONE)));
        when(current.requireSelf(principal, 7L)).thenReturn(7L);
        when(current.id(principal)).thenReturn(7L);

        controller.playerOrders(principal, 7L);
        controller.create(principal, request);
        controller.fulfill(principal, 20L);
        controller.cancel(principal, 20L);

        verify(service).findPlayerOrders(7L);
        verify(current, times(2)).requireSelf(principal, 7L);
        verify(service).createOrder(request);
        verify(service).fulfillOrder(20L, 7L);
        verify(service).cancelOrder(20L, 7L);
    }

    @Test
    void tastingAndChatUseOnlySessionPlayer() {
        CurrentPlayerService current = mock(CurrentPlayerService.class);
        when(current.id(principal)).thenReturn(7L);

        TastingCounterService counter = mock(TastingCounterService.class);
        TastingCounterController counterController = new TastingCounterController(counter, current);
        OpenOfferRequest offer = new OpenOfferRequest(2L, 2, 10, "goûte");
        counterController.counter(principal);
        counterController.open(principal, offer);
        counterController.serve(principal, 3L);
        verify(counter).counter(7L);
        verify(counter).open(7L, offer);
        verify(counter).serve(7L, 3L);

        TavernChatService chat = mock(TavernChatService.class);
        TavernChatController chatController = new TavernChatController(chat, current);
        PostMessageRequest message = new PostMessageRequest("Skål");
        chatController.post(principal, message);
        verify(chat).post(7L, message);
    }
}
