package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.order.NpcOrderResponse;
import be.mjodheim.brewstead.entity.NpcOrder;
import be.mjodheim.brewstead.entity.NpcOrderLine;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.enums.OrderStatus;
import be.mjodheim.brewstead.enums.ProgressAction;
import be.mjodheim.brewstead.mapper.NpcOrderMapper;
import be.mjodheim.brewstead.repository.NpcOrderLineRepository;
import be.mjodheim.brewstead.repository.NpcOrderRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.RecipeRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class NpcOrderService {

    private static final int CONTRATS_MAX = 3;

    private static final List<String> CUSTOMERS = List.of(
            "La troupe de Ragnar",
            "Les pêcheurs du fjord",
            "La garde de Skjold",
            "Les voyageurs de Brume",
            "Le banquet du Jarl"
    );

    private final NpcOrderRepository npcOrderRepository;
    private final NpcOrderLineRepository npcOrderLineRepository;
    private final RecipeRepository recipeRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final BrewService brewService;
    private final PlayerService playerService;
    private final NpcOrderMapper npcOrderMapper;
    private final ProgressionService progressionService;

    /** Un marchand se présente au plus tous les quarts d'heure. */
    private static final Duration ENTRE_DEUX_MARCHANDS = Duration.ofMinutes(15);

    @Transactional
    public List<NpcOrderResponse> findAllOrders(Long playerId) {
        getPlayer(playerId);
        accueillirUnMarchand(playerId);
        return npcOrderRepository.findAllByPlayerIdOrderByCreatedAtDesc(playerId).stream()
                .peek(this::refreshOrderStatus)
                .map(this::toResponse)
                .toList();
    }

    /**
     * Fait venir un marchand de lui-même, s'il y a de la place et que le
     * précédent n'est pas arrivé à l'instant.
     *
     * <p>Le joueur convoquait ses clients en appuyant sur un bouton : un
     * marchand qu'on invoque n'est pas un marchand, c'est un distributeur.
     * Ils passent maintenant au comptoir quand bon leur semble, dans la
     * limite de trois contrats à la fois.
     */
    private void accueillirUnMarchand(Long playerId) {
        List<NpcOrder> tous = npcOrderRepository.findAllByPlayerIdOrderByCreatedAtDesc(playerId);
        LocalDateTime now = LocalDateTime.now();
        long actifs = tous.stream()
                .peek(this::refreshOrderStatus)
                .filter(order -> order.getStatus() == OrderStatus.OPEN || order.getStatus() == OrderStatus.IN_PROGRESS)
                .filter(order -> now.isBefore(order.getExpiresAt()))
                .count();
        if (actifs >= CONTRATS_MAX) return;

        boolean tropTot = tous.stream()
                .map(NpcOrder::getCreatedAt)
                .max(LocalDateTime::compareTo)
                .filter(dernier -> dernier.isAfter(now.minus(ENTRE_DEUX_MARCHANDS)))
                .isPresent();
        if (tropTot) return;

        generateOrder(playerId);
    }

    @Transactional
    public NpcOrderResponse generateOrder(Long playerId) {
        // Invitations from two tabs must share the same three-contract limit.
        PlayerProfile player = playerProfileRepository.findForUpdateById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Player not found"));
        LocalDateTime now = LocalDateTime.now();
        long active = npcOrderRepository.findAllByPlayerIdOrderByCreatedAtDesc(playerId).stream()
                .filter(order -> order.getStatus() == OrderStatus.OPEN || order.getStatus() == OrderStatus.IN_PROGRESS)
                .filter(order -> now.isBefore(order.getExpiresAt()))
                .count();
        if (active >= CONTRATS_MAX) {
            throw new IllegalStateException("Livre tes contrats en cours avant qu’un autre marchand ne se présente (3 maximum).");
        }
        List<Recipe> recipes = recipeRepository.findAllByIsPublicTrue().stream()
                .sorted(Comparator.comparingLong(Recipe::getId))
                .toList();
        if (recipes.isEmpty()) {
            throw new IllegalStateException("No public recipe is available for NPC orders");
        }

        Set<Long> brewed = brewService.findPlayerBatches(playerId).stream()
                .map(batch -> batch.recipeId()).collect(Collectors.toSet());
        List<Recipe> familiar = recipes.stream().filter(recipe -> brewed.contains(recipe.getId())).toList();
        recipes = familiar.isEmpty()
                ? recipes.stream().limit(Math.max(2, (long) player.getLevel() * 2)).toList()
                : familiar;
        // A new domain starts with the introductory recipes, independently of
        // how many contracts the other players have already generated.
        long sequence = npcOrderRepository.countByPlayerId(playerId);
        Recipe recipe = recipes.get((int) (sequence % recipes.size()));
        int quantity = 2 + (int) (sequence % 4);
        int minQuality = 50 + (int) (sequence % 4) * 5;
        int rewardCoins = quantity * 40 + minQuality;
        int rewardReputation = 2 + quantity;

        NpcOrder order = npcOrderRepository.save(
                NpcOrder.builder()
                        .player(player)
                        .customerName(CUSTOMERS.get((int) (sequence % CUSTOMERS.size())))
                        .createdAt(now)
                        .expiresAt(now.plusMinutes(Math.max(90, recipe.getFermentationMinutes() + 30)))
                        .status(OrderStatus.OPEN)
                        .rewardCoins(rewardCoins)
                        .rewardReputation(rewardReputation)
                        .build()
        );

        NpcOrderLine line = npcOrderLineRepository.save(
                NpcOrderLine.builder()
                        .order(order)
                        .recipe(recipe)
                        .quantity(quantity)
                        .minQuality(minQuality)
                        .build()
        );

        return npcOrderMapper.toResponse(order, List.of(line));
    }

    @Transactional
    public NpcOrderResponse acceptOrder(Long playerId, Long orderId) {
        NpcOrder order = getOwnedOrder(playerId, orderId);
        refreshOrderStatus(order);

        if (order.getStatus() != OrderStatus.OPEN) {
            throw new IllegalStateException("Order is not open");
        }
        order.setStatus(OrderStatus.IN_PROGRESS);
        return toResponse(order);
    }

    @Transactional
    public NpcOrderResponse completeOrder(Long playerId, Long orderId) {
        NpcOrder order = getOwnedOrder(playerId, orderId);
        refreshOrderStatus(order);

        if (order.getStatus() != OrderStatus.OPEN && order.getStatus() != OrderStatus.IN_PROGRESS) {
            throw new IllegalStateException("Order cannot be completed");
        }

        List<NpcOrderLine> lines = npcOrderLineRepository.findAllByOrderId(orderId);
        if (lines.isEmpty()) {
            throw new IllegalStateException("Order has no lines");
        }

        for (NpcOrderLine line : lines) {
            brewService.consumeReadyProduct(
                    order.getPlayer().getId(),
                    line.getRecipe().getId(),
                    BigDecimal.valueOf(line.getQuantity()),
                    line.getMinQuality()
            );
        }

        playerService.reward(
                order.getPlayer().getId(),
                progressionService.npcCoinReward(playerId, order.getRewardCoins()),
                order.getRewardReputation(),
                order.getRewardReputation() * 5
        );
        order.setStatus(OrderStatus.COMPLETED);
        progressionService.record(playerId, ProgressAction.COMPLETE_ORDER);

        return npcOrderMapper.toResponse(order, lines);
    }

    private NpcOrderResponse toResponse(NpcOrder order) {
        return npcOrderMapper.toResponse(
                order,
                npcOrderLineRepository.findAllByOrderId(order.getId())
        );
    }

    private NpcOrder getOwnedOrder(Long playerId, Long orderId) {
        NpcOrder order = getOrder(orderId);
        if (!order.getPlayer().getId().equals(playerId)) {
            throw new AccessDeniedException("Cette commande ne t'est pas adressée.");
        }
        return order;
    }

    private NpcOrder getOrder(Long orderId) {
        return npcOrderRepository.findForUpdateById(orderId)
                .orElseThrow(() -> new IllegalArgumentException("NPC order not found"));
    }

    private PlayerProfile getPlayer(Long playerId) {
        return playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Player not found"));
    }

    private void refreshOrderStatus(NpcOrder order) {
        if ((order.getStatus() == OrderStatus.OPEN || order.getStatus() == OrderStatus.IN_PROGRESS)
                && !LocalDateTime.now().isBefore(order.getExpiresAt())) {
            order.setStatus(OrderStatus.EXPIRED);
        }
    }
}
