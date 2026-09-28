package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.inventory.IngredientRequest;
import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.FieldStatus;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.BehiveStatus;
import be.mjodheim.brewstead.exception.InsufficientCoinsException;
import be.mjodheim.brewstead.mapper.PlayerMapper;
import be.mjodheim.brewstead.repository.*;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

@Service
@RequiredArgsConstructor
public class PlayerService {

    private static final int XP_PER_LEVEL = 1_000;

    private final PlayerProfileRepository playerProfileRepository;
    private final UserRepository userRepository;
    private final PlayerFieldRepository playerFieldRepository;
    private final BeehiveRepository beehiveRepository;
    private final IngredientRepository ingredientRepository;
    private final InventoryService inventoryService;
    private final PlayerMapper playerMapper;
    private final EffectService effectService;

    @Transactional
    public PlayerProfileResponse getPlayer(Long playerId) {
        return playerMapper.toResponse(getPlayerEntity(playerId));
    }

    /**
     * Functional hook for the future registration/security flow.
     * Once a User has been created by the authentication layer, this method creates
     * the corresponding Brewstead and starter resources exactly once.
     */
    @Transactional
    public PlayerProfileResponse initializePlayer(Long userId) {
        return playerProfileRepository.findByUserId(userId)
                .map(playerMapper::toResponse)
                .orElseGet(() -> createStarterBrewstead(userId));
    }

    @Transactional
    public void spendCoins(Long playerId, int amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("Coin amount must be greater than zero");
        }

        PlayerProfile player = getPlayerEntity(playerId);
        if (player.getCoin() < amount) {
            throw new InsufficientCoinsException("Ta bourse ne suit pas.");
        }
        player.setCoin(player.getCoin() - amount);
    }

    @Transactional
    public void refundCoins(Long playerId, int amount) {
        if (amount <= 0) throw new IllegalArgumentException("Refund must be greater than zero");
        PlayerProfile player = getPlayerEntity(playerId);
        // Restituer une mise n'est pas un gain : aucun bonus ne doit s'appliquer.
        player.setCoin(Math.addExact(player.getCoin(), amount));
    }

    @Transactional
    public PlayerProfileResponse reward(Long playerId, int coins, int reputation, int experience) {
        if (coins < 0 || reputation < 0 || experience < 0) {
            throw new IllegalArgumentException("Rewards cannot be negative");
        }

        PlayerProfile player = getPlayerEntity(playerId);
        player.setCoin(player.getCoin() + effectService.boostCoins(playerId, coins));
        player.setReputation(player.getReputation() + effectService.boostReputation(playerId, reputation));
        player.setExperience(player.getExperience() + experience);
        player.setLevel(Math.max(player.getLevel(), 1 + player.getExperience() / XP_PER_LEVEL));

        return playerMapper.toResponse(player);
    }

    @Transactional
    public PlayerProfile getPlayerEntity(Long playerId) {
        return playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Player not found"));
    }

    private PlayerProfileResponse createStarterBrewstead(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        PlayerProfile player = playerProfileRepository.save(
                PlayerProfile.builder()
                        .user(user)
                        .build()
        );

        List<PlayerField> fields = List.of(
                newStarterField(player),
                newStarterField(player),
                newStarterField(player)
        );
        playerFieldRepository.saveAll(fields);

        beehiveRepository.saveAll(List.of(
                newStarterHive(player),
                newStarterHive(player)
        ));

        // De quoi lancer immédiatement un hydromel ET une cervoise : sans levure
        // ni houblon, un nouveau brasseur resterait devant une cuve vide.
        addStarterIngredient(player, "Eau de source", IngredientType.WATER, new BigDecimal("40.000"));
        addStarterIngredient(player, "Miel de trèfle", IngredientType.HONEY, new BigDecimal("9.000"));
        addStarterIngredient(player, "Orge maltée", IngredientType.CEREAL, new BigDecimal("14.000"));
        addStarterIngredient(player, "Houblon du fjord", IngredientType.HOP, new BigDecimal("400.000"));
        addStarterIngredient(player, "Levure de Mjödheim", IngredientType.YEAST, new BigDecimal("60.000"));
        addStarterIngredient(player, "Levure sauvage", IngredientType.YEAST, new BigDecimal("50.000"));
        addStarterIngredient(player, "Levure de cave", IngredientType.YEAST, new BigDecimal("40.000"));
        addStarterIngredient(player, "Pomme à cidre", IngredientType.FRUIT, new BigDecimal("16.000"));
        addStarterIngredient(player, "Bruyère commune", IngredientType.HERB, new BigDecimal("400.000"));

        return playerMapper.toResponse(player);
    }

    private PlayerField newStarterField(PlayerProfile player) {
        return PlayerField.builder()
                .player(player)
                .status(FieldStatus.EMPTY)
                .build();
    }

    private Beehive newStarterHive(PlayerProfile player) {
        return Beehive.builder()
                .player(player)
                .status(BehiveStatus.IDLE)
                .build();
    }

    /** On vise un ingrédient précis, avec repli sur sa famille si le nom bouge. */
    private void addStarterIngredient(PlayerProfile player, String name, IngredientType type, BigDecimal quantity) {
        Ingredient ingredient = ingredientRepository.findByNameIgnoreCase(name)
                .or(() -> ingredientRepository.findFirstByType(type))
                .orElseThrow(() -> new IllegalStateException("Ingrédient de départ absent du catalogue : " + name));

        inventoryService.addIngredient(
                new IngredientRequest(player.getId(), ingredient.getId(), quantity)
        );
    }
}
