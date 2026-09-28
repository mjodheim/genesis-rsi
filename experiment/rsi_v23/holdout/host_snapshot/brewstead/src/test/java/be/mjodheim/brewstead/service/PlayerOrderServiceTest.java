package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.order.CreatePlayerOrderRequest;
import be.mjodheim.brewstead.dto.order.PlayerOrderLineRequest;
import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.OrderStatus;
import be.mjodheim.brewstead.mapper.PlayerOrderMapper;
import be.mjodheim.brewstead.repository.IngredientRepository;
import be.mjodheim.brewstead.repository.PlayerOrderLineRepository;
import be.mjodheim.brewstead.repository.PlayerOrderRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.ingredient;
import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class PlayerOrderServiceTest {

    @Mock PlayerOrderRepository orderRepository;
    @Mock PlayerOrderLineRepository lineRepository;
    @Mock PlayerProfileRepository playerRepository;
    @Mock IngredientRepository ingredientRepository;
    @Mock InventoryService inventoryService;
    @Mock PlayerService playerService;
    @Mock PlayerOrderMapper mapper;
    @Mock ProgressionService progressionService;
    @InjectMocks PlayerOrderService service;

    @Test
    void createOrderEscrowsRewardAndPersistsLines() {
        PlayerProfile creator = player(1);
        Ingredient honey = ingredient(5, IngredientType.HONEY);
        CreatePlayerOrderRequest request = new CreatePlayerOrderRequest(
                1L, 100, 60,
                List.of(new PlayerOrderLineRequest(5L, new BigDecimal("2.500"))));
        when(playerRepository.findById(1L)).thenReturn(Optional.of(creator));
        when(orderRepository.save(any(PlayerOrder.class))).thenAnswer(invocation -> {
            PlayerOrder order = invocation.getArgument(0);
            order.setId(10L);
            return order;
        });
        when(ingredientRepository.findById(5L)).thenReturn(Optional.of(honey));

        service.createOrder(request);

        verify(playerService).spendCoins(1L, 100);
        ArgumentCaptor<PlayerOrder> orderCaptor = ArgumentCaptor.forClass(PlayerOrder.class);
        verify(orderRepository).save(orderCaptor.capture());
        assertEquals(OrderStatus.OPEN, orderCaptor.getValue().getStatus());
        assertEquals(100, orderCaptor.getValue().getRewardCoins());
        assertTrue(orderCaptor.getValue().getExpiresAt().isAfter(orderCaptor.getValue().getCreatedAt()));

        verify(lineRepository).saveAll(argThat(lines -> {
            for (PlayerOrderLine line : lines) {
                return line.getOrder().getId().equals(10L)
                        && line.getIngredient().getId() == 5L
                        && line.getQuantity().compareTo(new BigDecimal("2.500")) == 0;
            }
            return false;
        }));
    }

    @Test
    void createOrderValidatesRewardDurationLinesAndDuplicates() {
        assertThrows(IllegalArgumentException.class, () -> service.createOrder(
                new CreatePlayerOrderRequest(null, 100, 60, validLines())));
        assertThrows(IllegalArgumentException.class, () -> service.createOrder(
                new CreatePlayerOrderRequest(1L, 0, 60, validLines())));
        assertThrows(IllegalArgumentException.class, () -> service.createOrder(
                new CreatePlayerOrderRequest(1L, 100, 4, validLines())));
        assertThrows(IllegalArgumentException.class, () -> service.createOrder(
                new CreatePlayerOrderRequest(1L, 100, 10081, validLines())));
        assertThrows(IllegalArgumentException.class, () -> service.createOrder(
                new CreatePlayerOrderRequest(1L, 100, 60, List.of())));
        assertThrows(IllegalArgumentException.class, () -> service.createOrder(
                new CreatePlayerOrderRequest(1L, 100, 60,
                        List.of(new PlayerOrderLineRequest(5L, BigDecimal.ZERO)))));
        assertThrows(IllegalArgumentException.class, () -> service.createOrder(
                new CreatePlayerOrderRequest(1L, 100, 60,
                        List.of(
                                new PlayerOrderLineRequest(5L, BigDecimal.ONE),
                                new PlayerOrderLineRequest(5L, new BigDecimal("2"))
                        ))));
    }

    @Test
    void fulfillOrderTransfersGoodsPaysFulfillerAndCompletes() {
        PlayerProfile creator = player(1);
        PlayerProfile fulfiller = player(2);
        Ingredient honey = ingredient(5, IngredientType.HONEY);
        PlayerOrder order = order(10, creator, OrderStatus.OPEN);
        order.setRewardCoins(125);
        PlayerOrderLine line = PlayerOrderLine.builder()
                .order(order).ingredient(honey).quantity(new BigDecimal("3.000")).build();
        when(orderRepository.findById(10L)).thenReturn(Optional.of(order));
        when(playerRepository.findById(2L)).thenReturn(Optional.of(fulfiller));
        when(lineRepository.findAllByOrderId(10L)).thenReturn(List.of(line));

        service.fulfillOrder(10L, 2L);

        verify(inventoryService).removeIngredient(argThat(r ->
                r.playerId().equals(2L) && r.ingredientId().equals(5L)
                        && r.quantity().compareTo(new BigDecimal("3.000")) == 0));
        verify(inventoryService).addIngredient(argThat(r ->
                r.playerId().equals(1L) && r.ingredientId().equals(5L)
                        && r.quantity().compareTo(new BigDecimal("3.000")) == 0));
        verify(playerService).reward(2L, 125, 0, 5);
        assertSame(fulfiller, order.getFulfilledBy());
        assertEquals(OrderStatus.COMPLETED, order.getStatus());
    }

    @Test
    void fulfillerCannotBeCreatorAndOrderMustHaveLines() {
        PlayerProfile creator = player(1);
        PlayerOrder own = order(10, creator, OrderStatus.OPEN);
        when(orderRepository.findById(10L)).thenReturn(Optional.of(own));
        when(playerRepository.findById(1L)).thenReturn(Optional.of(creator));

        assertThrows(IllegalStateException.class,
                () -> service.fulfillOrder(10L, 1L));

        PlayerOrder empty = order(11, creator, OrderStatus.OPEN);
        when(orderRepository.findById(11L)).thenReturn(Optional.of(empty));
        when(playerRepository.findById(2L)).thenReturn(Optional.of(player(2)));
        when(lineRepository.findAllByOrderId(11L)).thenReturn(List.of());

        assertThrows(IllegalStateException.class,
                () -> service.fulfillOrder(11L, 2L));
    }

    @Test
    void cancelOrderOnlyAllowsCreatorAndRefundsEscrow() {
        PlayerProfile creator = player(1);
        PlayerOrder order = order(10, creator, OrderStatus.OPEN);
        order.setRewardCoins(90);
        when(orderRepository.findById(10L)).thenReturn(Optional.of(order));
        when(lineRepository.findAllByOrderId(10L)).thenReturn(List.of());

        assertThrows(IllegalStateException.class,
                () -> service.cancelOrder(10L, 2L));

        service.cancelOrder(10L, 1L);

        verify(playerService).refundCoins(1L, 90);
        assertEquals(OrderStatus.CANCELED, order.getStatus());
    }

    @Test
    void expiredMarketOrderIsRefundedAndHidden() {
        PlayerOrder expired = order(10, player(1), OrderStatus.OPEN);
        expired.setExpiresAt(LocalDateTime.now().minusSeconds(1));
        expired.setRewardCoins(80);
        when(orderRepository.findAllByStatusOrderByCreatedAtDesc(OrderStatus.OPEN))
                .thenReturn(List.of(expired));

        assertTrue(service.findOpenOrders().isEmpty());

        assertEquals(OrderStatus.EXPIRED, expired.getStatus());
        verify(playerService).refundCoins(1L, 80);
    }

    @Test
    void relayStaleOrdersLetsNpcMerchantFulfillAfterTwoThirds() {
        PlayerProfile creator = player(1);
        Ingredient honey = ingredient(5, IngredientType.HONEY);
        PlayerOrder stale = PlayerOrder.builder()
                .id(10L).creator(creator)
                .createdAt(LocalDateTime.now().minusMinutes(70))
                .expiresAt(LocalDateTime.now().plusMinutes(20))
                .status(OrderStatus.OPEN).rewardCoins(100).build();
        PlayerOrderLine line = PlayerOrderLine.builder()
                .order(stale).ingredient(honey).quantity(new BigDecimal("2.000")).build();
        when(orderRepository.findAllByStatusOrderByCreatedAtDesc(OrderStatus.OPEN))
                .thenReturn(List.of(stale));
        when(lineRepository.findAllByOrderId(10L)).thenReturn(List.of(line));

        assertEquals(1, service.relayStaleOrders());

        verify(inventoryService).addIngredient(argThat(r ->
                r.playerId().equals(1L) && r.ingredientId().equals(5L)
                        && r.quantity().compareTo(new BigDecimal("2.000")) == 0));
        assertTrue(stale.isFulfilledByNpc());
        assertEquals(OrderStatus.COMPLETED, stale.getStatus());
        verify(playerService, never()).reward(anyLong(), anyInt(), anyInt(), anyInt());
    }

    @Test
    void relayLeavesFreshOrdersAlone() {
        PlayerOrder fresh = PlayerOrder.builder()
                .id(10L).creator(player(1))
                .createdAt(LocalDateTime.now().minusMinutes(10))
                .expiresAt(LocalDateTime.now().plusMinutes(80))
                .status(OrderStatus.OPEN).rewardCoins(100).build();
        when(orderRepository.findAllByStatusOrderByCreatedAtDesc(OrderStatus.OPEN))
                .thenReturn(List.of(fresh));

        assertEquals(0, service.relayStaleOrders());
        verifyNoInteractions(lineRepository, inventoryService);
    }

    private List<PlayerOrderLineRequest> validLines() {
        return List.of(new PlayerOrderLineRequest(5L, BigDecimal.ONE));
    }

    private PlayerOrder order(long id, PlayerProfile creator, OrderStatus status) {
        return PlayerOrder.builder()
                .id(id).creator(creator)
                .createdAt(LocalDateTime.now().minusMinutes(1))
                .expiresAt(LocalDateTime.now().plusMinutes(30))
                .status(status).rewardCoins(100)
                .build();
    }
}
