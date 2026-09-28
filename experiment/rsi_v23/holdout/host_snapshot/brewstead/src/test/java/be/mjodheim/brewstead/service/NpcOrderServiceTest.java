package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.OrderStatus;
import be.mjodheim.brewstead.mapper.NpcOrderMapper;
import be.mjodheim.brewstead.repository.NpcOrderLineRepository;
import be.mjodheim.brewstead.repository.NpcOrderRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.RecipeRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.access.AccessDeniedException;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.player;
import static be.mjodheim.brewstead.TestData.recipe;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class NpcOrderServiceTest {

    @Mock NpcOrderRepository orderRepository;
    @Mock NpcOrderLineRepository lineRepository;
    @Mock RecipeRepository recipeRepository;
    @Mock PlayerProfileRepository playerRepository;
    @Mock BrewService brewService;
    @Mock PlayerService playerService;
    @Mock NpcOrderMapper mapper;
    @Mock ProgressionService progressionService;
    @InjectMocks NpcOrderService service;

    @Test
    void findAllOrdersExpiresStaleOrders() {
        PlayerProfile player = player(1);
        NpcOrder order = order(10, player, OrderStatus.OPEN);
        order.setExpiresAt(LocalDateTime.now().minusSeconds(1));
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player));
        when(orderRepository.findAllByPlayerIdOrderByCreatedAtDesc(1L)).thenReturn(List.of(order));
        when(lineRepository.findAllByOrderId(10L)).thenReturn(List.of());

        service.findAllOrders(1L);

        assertEquals(OrderStatus.EXPIRED, order.getStatus());
    }

    @Test
    void generateOrderRequiresPublicRecipe() {
        when(playerRepository.findForUpdateById(1L)).thenReturn(Optional.of(player(1)));
        when(recipeRepository.findAllByIsPublicTrue()).thenReturn(List.of());

        assertThrows(IllegalStateException.class,
                () -> service.generateOrder(1L));
    }

    @Test
    void generatingAnotherContractRequiresAnAvailableSlot() {
        PlayerProfile player = player(1);
        when(playerRepository.findForUpdateById(1L)).thenReturn(Optional.of(player));
        when(orderRepository.findAllByPlayerIdOrderByCreatedAtDesc(1L)).thenReturn(List.of(
                order(1, player, OrderStatus.OPEN), order(2, player, OrderStatus.IN_PROGRESS),
                order(3, player, OrderStatus.OPEN)));
        assertThrows(IllegalStateException.class, () -> service.generateOrder(1L));
        verify(orderRepository, never()).save(any());
    }

    @Test
    void generateOrderUsesDeterministicSequence() {
        PlayerProfile player = player(1);
        Recipe first = recipe(10);
        Recipe second = recipe(20);
        when(playerRepository.findForUpdateById(1L)).thenReturn(Optional.of(player));
        when(recipeRepository.findAllByIsPublicTrue()).thenReturn(List.of(second, first));
        when(orderRepository.countByPlayerId(1L)).thenReturn(5L);
        when(orderRepository.save(any(NpcOrder.class))).thenAnswer(invocation -> {
            NpcOrder saved = invocation.getArgument(0);
            saved.setId(99L);
            return saved;
        });
        when(lineRepository.save(any(NpcOrderLine.class))).thenAnswer(invocation -> invocation.getArgument(0));

        service.generateOrder(1L);

        ArgumentCaptor<NpcOrder> orderCaptor = ArgumentCaptor.forClass(NpcOrder.class);
        verify(orderRepository).save(orderCaptor.capture());
        NpcOrder saved = orderCaptor.getValue();
        assertEquals("La troupe de Ragnar", saved.getCustomerName());
        assertEquals(175, saved.getRewardCoins());
        assertEquals(5, saved.getRewardReputation());
        assertEquals(OrderStatus.OPEN, saved.getStatus());

        ArgumentCaptor<NpcOrderLine> lineCaptor = ArgumentCaptor.forClass(NpcOrderLine.class);
        verify(lineRepository).save(lineCaptor.capture());
        assertEquals(20L, lineCaptor.getValue().getRecipe().getId());
        assertEquals(3, lineCaptor.getValue().getQuantity());
        assertEquals(55, lineCaptor.getValue().getMinQuality());
    }

    @Test
    void acceptOrderRequiresOwnerAndOpenStatus() {
        NpcOrder foreign = order(10, player(2), OrderStatus.OPEN);
        when(orderRepository.findForUpdateById(10L)).thenReturn(Optional.of(foreign));
        assertThrows(AccessDeniedException.class,
                () -> service.acceptOrder(1L, 10L));

        NpcOrder completed = order(11, player(1), OrderStatus.COMPLETED);
        when(orderRepository.findForUpdateById(11L)).thenReturn(Optional.of(completed));
        assertThrows(IllegalStateException.class,
                () -> service.acceptOrder(1L, 11L));
    }

    @Test
    void acceptOrderMovesOpenOrderInProgress() {
        NpcOrder order = order(10, player(1), OrderStatus.OPEN);
        when(orderRepository.findForUpdateById(10L)).thenReturn(Optional.of(order));
        when(lineRepository.findAllByOrderId(10L)).thenReturn(List.of());

        service.acceptOrder(1L, 10L);

        assertEquals(OrderStatus.IN_PROGRESS, order.getStatus());
    }

    @Test
    void completeOrderConsumesProductRewardsPlayerAndCompletes() {
        PlayerProfile player = player(1);
        Recipe recipe = recipe(20);
        NpcOrder order = order(10, player, OrderStatus.IN_PROGRESS);
        order.setRewardCoins(120);
        order.setRewardReputation(6);
        NpcOrderLine line = NpcOrderLine.builder()
                .order(order).recipe(recipe).quantity(3).minQuality(70).build();
        when(orderRepository.findForUpdateById(10L)).thenReturn(Optional.of(order));
        when(lineRepository.findAllByOrderId(10L)).thenReturn(List.of(line));

        when(progressionService.npcCoinReward(1L, 120)).thenReturn(120);
        service.completeOrder(1L, 10L);

        verify(brewService).consumeReadyProduct(1L, 20L, BigDecimal.valueOf(3), 70);
        verify(playerService).reward(1L, 120, 6, 30);
        assertEquals(OrderStatus.COMPLETED, order.getStatus());
    }

    @Test
    void completeOrderRequiresLines() {
        NpcOrder order = order(10, player(1), OrderStatus.OPEN);
        when(orderRepository.findForUpdateById(10L)).thenReturn(Optional.of(order));
        when(lineRepository.findAllByOrderId(10L)).thenReturn(List.of());

        assertThrows(IllegalStateException.class,
                () -> service.completeOrder(1L, 10L));
        verifyNoInteractions(brewService, playerService);
    }

    private NpcOrder order(long id, PlayerProfile player, OrderStatus status) {
        return NpcOrder.builder()
                .id(id).player(player).customerName("Client")
                .createdAt(LocalDateTime.now().minusMinutes(1))
                .expiresAt(LocalDateTime.now().plusMinutes(30))
                .status(status).rewardCoins(100).rewardReputation(5)
                .build();
    }
}
