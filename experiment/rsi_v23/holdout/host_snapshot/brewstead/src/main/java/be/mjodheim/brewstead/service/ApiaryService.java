package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.apiary.BeehiveResponse;
import be.mjodheim.brewstead.dto.inventory.IngredientRequest;
import be.mjodheim.brewstead.entity.Beehive;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.enums.BehiveStatus;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.ProgressAction;
import be.mjodheim.brewstead.mapper.ApiaryMapper;
import be.mjodheim.brewstead.repository.BeehiveRepository;
import be.mjodheim.brewstead.repository.IngredientRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ApiaryService {

    private static final int BASE_PRODUCTION_MINUTES = 10;
    private static final BigDecimal BASE_HONEY_YIELD = new BigDecimal("1.000");

    private final BeehiveRepository beehiveRepository;
    private final IngredientRepository ingredientRepository;
    private final InventoryService inventoryService;
    private final ApiaryMapper apiaryMapper;
    private final EffectService effectService;
    private final ProgressionService progressionService;
    private final PlayerService playerService;

    /**
     * Installe une ruche de plus, contre des pièces.
     *
     * <p>Elle se met à produire tout de suite : on l'a payée, elle travaille.
     */
    @Transactional
    public List<BeehiveResponse> installNewHive(Long playerId) {
        List<Beehive> hives = beehiveRepository.findAllByPlayerId(playerId);
        Integer price = EstatePrices.nextHive(hives.size());
        if (price == null) {
            throw new IllegalStateException("Le coteau ne peut pas porter une ruche de plus.");
        }
        playerService.spendCoins(playerId, price);
        Beehive hive = Beehive.builder()
                .player(playerService.getPlayerEntity(playerId))
                .level(1)
                .status(BehiveStatus.IDLE)
                .build();
        relancer(hive);
        beehiveRepository.save(hive);
        return findAllHives(playerId);
    }

    /**
     * Fait passer une ruche au niveau suivant, contre des pièces.
     *
     * <p>Le niveau était écrit dans le modèle depuis le début : la durée du
     * cycle et le rendement en dépendent déjà. Rien ne l'augmentait jamais,
     * si bien que tout un axe de progression dormait dans la base.
     *
     * <p>Le cycle en cours n'est pas relancé : les abeilles finissent ce
     * qu'elles ont commencé, et c'est la prochaine tournée qui profite de
     * l'agrandissement.
     */
    @Transactional
    public BeehiveResponse upgradeHive(Long playerId, Long hiveId) {
        Beehive hive = getOwnedHive(playerId, hiveId);
        Integer price = EstatePrices.upgrade(hive.getLevel());
        if (price == null) {
            throw new IllegalStateException("Cette ruche est déjà au mieux de sa forme.");
        }
        playerService.spendCoins(playerId, price);
        hive.setLevel(hive.getLevel() + 1);
        return apiaryMapper.toResponse(hive);
    }

    @Transactional
    public List<BeehiveResponse> findAllHives(Long playerId) {
        List<Beehive> hives = beehiveRepository.findAllByPlayerId(playerId);
        hives.forEach(this::refreshHiveStatus);
        return apiaryMapper.toResponseList(hives);
    }

    /**
     * Les abeilles n'attendent pas qu'on le leur demande.
     *
     * <p>Une ruche vide se remet à produire d'elle-même : réveiller chaque
     * ruche à la main après chaque récolte n'était pas une décision de jeu,
     * juste un clic de plus. Le joueur choisit quand récolter, pas quand les
     * abeilles travaillent.
     */
    private void relancer(Beehive hive) {
        LocalDateTime now = LocalDateTime.now();
        double factor = effectService.durationFactor(hive.getPlayer().getId(), EffectKind.BOURDONNEMENT);
        long durationMinutes = Math.max(1,
                Math.round(Math.max(2, BASE_PRODUCTION_MINUTES - (hive.getLevel() - 1)) * factor));
        hive.setStartedAt(now);
        hive.setReadyAt(now.plusMinutes(durationMinutes));
        hive.setStatus(BehiveStatus.PRODUCING);
    }

    @Transactional
    public BeehiveResponse startProduction(Long playerId, Long hiveId) {
        Beehive hive = getOwnedHive(playerId, hiveId);
        // Pas de rafraîchissement ici : il réveillerait la ruche avant le
        // contrôle, et le contrat de cette opération resterait inapplicable.
        if (hive.getStatus() != BehiveStatus.IDLE) {
            throw new IllegalStateException("Beehive is not idle");
        }

        relancer(hive);
        return apiaryMapper.toResponse(hive);
    }

    @Transactional
    public BeehiveResponse updateHiveStatus(Long playerId, Long hiveId) {
        Beehive hive = getOwnedHive(playerId, hiveId);
        refreshHiveStatus(hive);
        return apiaryMapper.toResponse(hive);
    }

    @Transactional
    public BeehiveResponse harvest(Long playerId, Long hiveId) {
        Beehive hive = getOwnedHive(playerId, hiveId);
        refreshHiveStatus(hive);

        if (hive.getStatus() != BehiveStatus.READY) {
            throw new IllegalStateException("Beehive is not ready");
        }

        Ingredient honey = ingredientRepository.findFirstByType(IngredientType.HONEY)
                .orElseThrow(() -> new IllegalStateException("Honey ingredient is not configured"));

        BigDecimal quantity = progressionService.harvestYield(playerId,
                BASE_HONEY_YIELD.multiply(BigDecimal.valueOf(Math.max(1, hive.getLevel()))));
        inventoryService.addIngredient(
                new IngredientRequest(hive.getPlayer().getId(), honey.getId(), quantity)
        );

        relancer(hive);

        progressionService.record(playerId, ProgressAction.HARVEST_HIVE);

        return apiaryMapper.toResponse(hive);
    }

    /**
     * Vide toutes les ruches prêtes d'un seul geste.
     *
     * @return le nombre de ruches effectivement récoltées
     */
    @Transactional
    public int harvestAll(Long playerId) {
        List<Beehive> hives = beehiveRepository.findAllByPlayerId(playerId);
        hives.forEach(this::refreshHiveStatus);

        int harvested = 0;
        for (Beehive hive : hives) {
            if (hive.getStatus() == BehiveStatus.READY) {
                harvest(playerId, hive.getId());
                harvested++;
            }
        }
        return harvested;
    }

    private Beehive getOwnedHive(Long playerId, Long hiveId) {
        Beehive hive = beehiveRepository.findById(hiveId)
                .orElseThrow(() -> new IllegalArgumentException("Ruche introuvable."));
        if (!hive.getPlayer().getId().equals(playerId)) {
            throw new AccessDeniedException("Cette ruche n'est pas la tienne.");
        }
        return hive;
    }

    private void refreshHiveStatus(Beehive hive) {
        if (hive.getStatus() == BehiveStatus.IDLE) {
            relancer(hive);
            return;
        }
        if (hive.getStatus() == BehiveStatus.PRODUCING
                && hive.getReadyAt() != null
                && !LocalDateTime.now().isBefore(hive.getReadyAt())) {
            hive.setStatus(BehiveStatus.READY);
        }
    }
}
