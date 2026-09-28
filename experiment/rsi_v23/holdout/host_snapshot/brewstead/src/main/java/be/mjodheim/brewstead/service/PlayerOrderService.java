package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.inventory.IngredientRequest;
import be.mjodheim.brewstead.dto.order.CreatePlayerOrderRequest;
import be.mjodheim.brewstead.dto.order.PlayerOrderLineRequest;
import be.mjodheim.brewstead.dto.order.PlayerOrderResponse;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerOrder;
import be.mjodheim.brewstead.entity.PlayerOrderLine;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.enums.OrderStatus;
import be.mjodheim.brewstead.enums.ProgressAction;
import be.mjodheim.brewstead.mapper.PlayerOrderMapper;
import be.mjodheim.brewstead.repository.IngredientRepository;
import be.mjodheim.brewstead.repository.PlayerOrderLineRepository;
import be.mjodheim.brewstead.repository.PlayerOrderRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class PlayerOrderService {

    private final PlayerOrderRepository playerOrderRepository;
    private final PlayerOrderLineRepository playerOrderLineRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final IngredientRepository ingredientRepository;
    private final InventoryService inventoryService;
    private final PlayerService playerService;
    private final PlayerOrderMapper playerOrderMapper;
    private final ProgressionService progressionService;

    @Transactional
    public List<PlayerOrderResponse> findOpenOrders() {
        return playerOrderRepository.findAllByStatusOrderByCreatedAtDesc(OrderStatus.OPEN).stream()
                .peek(this::refreshOrderStatus)
                .filter(order -> order.getStatus() == OrderStatus.OPEN)
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public List<PlayerOrderResponse> findPlayerOrders(Long playerId) {
        getPlayer(playerId);
        return playerOrderRepository.findAllByCreatorIdOrderByCreatedAtDesc(playerId).stream()
                .peek(this::refreshOrderStatus)
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public PlayerOrderResponse createOrder(CreatePlayerOrderRequest request) {
        validateCreateRequest(request);
        PlayerProfile creator = getPlayer(request.creatorId());

        // Escrow: the reward leaves the creator immediately and is either paid to
        // the fulfiller or refunded on cancellation/expiration.
        playerService.spendCoins(creator.getId(), request.rewardCoins());

        LocalDateTime now = LocalDateTime.now();
        PlayerOrder order = playerOrderRepository.save(
                PlayerOrder.builder()
                        .creator(creator)
                        .createdAt(now)
                        .expiresAt(now.plusMinutes(request.expiresInMinutes()))
                        .status(OrderStatus.OPEN)
                        .rewardCoins(request.rewardCoins())
                        .build()
        );

        List<PlayerOrderLine> lines = request.lines().stream()
                .map(line -> toEntity(order, line))
                .toList();
        playerOrderLineRepository.saveAll(lines);

        return playerOrderMapper.toResponse(order, lines);
    }

    @Transactional
    public PlayerOrderResponse fulfillOrder(Long orderId, Long fulfillerId) {
        PlayerOrder order = getOrder(orderId);
        refreshOrderStatus(order);

        if (order.getStatus() != OrderStatus.OPEN && order.getStatus() != OrderStatus.IN_PROGRESS) {
            throw new IllegalStateException("Player order cannot be fulfilled");
        }

        PlayerProfile fulfiller = getPlayer(fulfillerId);
        if (order.getCreator().getId().equals(fulfillerId)) {
            throw new IllegalStateException("A player cannot fulfil their own order");
        }

        List<PlayerOrderLine> lines = playerOrderLineRepository.findAllByOrderId(orderId);
        if (lines.isEmpty()) {
            throw new IllegalStateException("Player order has no lines");
        }

        for (PlayerOrderLine line : lines) {
            inventoryService.removeIngredient(
                    new IngredientRequest(fulfillerId, line.getIngredient().getId(), line.getQuantity())
            );
            inventoryService.addIngredient(
                    new IngredientRequest(order.getCreator().getId(), line.getIngredient().getId(), line.getQuantity())
            );
        }

        playerService.reward(fulfillerId, order.getRewardCoins(), 0, Math.max(1, order.getRewardCoins() / 25));
        order.setFulfilledBy(fulfiller);
        order.setStatus(OrderStatus.COMPLETED);
        progressionService.record(fulfillerId, ProgressAction.PLAYER_TRADE);

        return playerOrderMapper.toResponse(order, lines);
    }

    @Transactional
    public PlayerOrderResponse cancelOrder(Long orderId, Long creatorId) {
        PlayerOrder order = getOrder(orderId);
        refreshOrderStatus(order);

        if (!order.getCreator().getId().equals(creatorId)) {
            throw new IllegalStateException("Only the creator can cancel this order");
        }
        if (order.getStatus() != OrderStatus.OPEN && order.getStatus() != OrderStatus.IN_PROGRESS) {
            throw new IllegalStateException("Player order cannot be cancelled");
        }

        playerService.refundCoins(creatorId, order.getRewardCoins());
        order.setStatus(OrderStatus.CANCELED);
        return toResponse(order);
    }

    private PlayerOrderResponse toResponse(PlayerOrder order) {
        return playerOrderMapper.toResponse(
                order,
                playerOrderLineRepository.findAllByOrderId(order.getId())
        );
    }

    private PlayerOrderLine toEntity(PlayerOrder order, PlayerOrderLineRequest line) {
        Ingredient ingredient = ingredientRepository.findById(line.ingredientId())
                .orElseThrow(() -> new IllegalArgumentException("Ingredient not found"));

        return PlayerOrderLine.builder()
                .order(order)
                .ingredient(ingredient)
                .quantity(line.quantity())
                .build();
    }

    private void validateCreateRequest(CreatePlayerOrderRequest request) {
        if (request.creatorId() == null) {
            throw new IllegalArgumentException("Order creator is required");
        }
        if (request.rewardCoins() <= 0) {
            throw new IllegalArgumentException("Order reward must be greater than zero");
        }
        if (request.expiresInMinutes() < 5 || request.expiresInMinutes() > 10_080) {
            throw new IllegalArgumentException("Order duration must be between 5 minutes and 7 days");
        }
        if (request.lines() == null || request.lines().isEmpty()) {
            throw new IllegalArgumentException("Player order must contain at least one line");
        }

        Set<Long> ingredientIds = new HashSet<>();
        for (PlayerOrderLineRequest line : request.lines()) {
            if (line.ingredientId() == null || line.quantity() == null
                    || line.quantity().compareTo(BigDecimal.ZERO) <= 0) {
                throw new IllegalArgumentException("Order quantities must be greater than zero");
            }
            if (!ingredientIds.add(line.ingredientId())) {
                throw new IllegalArgumentException("An ingredient can only appear once in a player order");
            }
        }
    }

    private PlayerOrder getOrder(Long orderId) {
        return playerOrderRepository.findById(orderId)
                .orElseThrow(() -> new IllegalArgumentException("Player order not found"));
    }

    private PlayerProfile getPlayer(Long playerId) {
        return playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Player not found"));
    }

    /**
     * Personne n'a répondu : un marchand de passage s'en charge. Le
     * commanditaire reçoit sa marchandise, les pièces déjà mises de côté
     * partent avec le marchand — c'est le prix de l'impatience.
     */
    @Transactional
    public int relayStaleOrders() {
        LocalDateTime now = LocalDateTime.now();
        int relayed = 0;

        for (PlayerOrder order : playerOrderRepository.findAllByStatusOrderByCreatedAtDesc(OrderStatus.OPEN)) {
            refreshOrderStatus(order);
            if (order.getStatus() != OrderStatus.OPEN || !isRelayDue(order, now)) {
                continue;
            }

            List<PlayerOrderLine> lines = playerOrderLineRepository.findAllByOrderId(order.getId());
            if (lines.isEmpty()) {
                continue;
            }

            for (PlayerOrderLine line : lines) {
                inventoryService.addIngredient(new IngredientRequest(
                        order.getCreator().getId(), line.getIngredient().getId(), line.getQuantity()));
            }

            order.setFulfilledByNpc(true);
            order.setStatus(OrderStatus.COMPLETED);
            relayed++;
        }
        return relayed;
    }

    /** Le marchand n'intervient qu'aux deux tiers du temps imparti. */
    private boolean isRelayDue(PlayerOrder order, LocalDateTime now) {
        long total = java.time.Duration.between(order.getCreatedAt(), order.getExpiresAt()).toSeconds();
        long elapsed = java.time.Duration.between(order.getCreatedAt(), now).toSeconds();
        return total > 0 && elapsed >= total * 2 / 3;
    }

    private void refreshOrderStatus(PlayerOrder order) {
        if ((order.getStatus() == OrderStatus.OPEN || order.getStatus() == OrderStatus.IN_PROGRESS)
                && !LocalDateTime.now().isBefore(order.getExpiresAt())) {
            order.setStatus(OrderStatus.EXPIRED);
            playerService.refundCoins(order.getCreator().getId(), order.getRewardCoins());
        }
    }
}
