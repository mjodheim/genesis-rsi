package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.brew.BatchResponse;
import be.mjodheim.brewstead.dto.brew.TastingResponse;
import be.mjodheim.brewstead.dto.effect.PlayerEffectResponse;
import be.mjodheim.brewstead.dto.brew.StartBatchRequest;
import be.mjodheim.brewstead.dto.inventory.IngredientRequest;
import be.mjodheim.brewstead.entity.Batch;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.RecipeIngredient;
import be.mjodheim.brewstead.enums.BatchStatus;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.ProgressAction;
import be.mjodheim.brewstead.exception.InsufficientStockException;
import be.mjodheim.brewstead.mapper.BrewMapper;
import be.mjodheim.brewstead.repository.BatchRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.RecipeIngredientRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class BrewService {

    private final BatchRepository batchRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final RecipeIngredientRepository recipeIngredientRepository;
    private final RecipeService recipeService;
    private final InventoryService inventoryService;
    private final BrewMapper brewMapper;
    private final EffectService effectService;
    private final ProgressionService progressionService;

    @Transactional
    public List<BatchResponse> findPlayerBatches(Long playerId) {
        getPlayer(playerId);
        List<Batch> batches = batchRepository.findAllByPlayerIdOrderByStartedAtDesc(playerId);
        batches.forEach(this::refreshBatchStatus);
        return brewMapper.toResponseList(batches);
    }

    @Transactional
    public BatchResponse startBatch(Long playerId, StartBatchRequest request) {
        if (request.volume() == null || request.volume().compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Batch volume must be greater than zero");
        }

        PlayerProfile player = getPlayer(playerId);
        Recipe recipe = recipeService.getAccessibleRecipeEntity(playerId, request.recipeId());
        List<RecipeIngredient> ingredients = recipeIngredientRepository.findAllByRecipeId(recipe.getId());
        if (ingredients.isEmpty()) {
            throw new IllegalStateException("Recipe has no ingredients");
        }

        BigDecimal ratio = request.volume().divide(recipe.getBaseVolume(), 6, RoundingMode.HALF_UP);
        for (RecipeIngredient line : ingredients) {
            BigDecimal requiredQuantity = line.getQuantity().multiply(ratio).stripTrailingZeros();
            if (requiredQuantity.compareTo(BigDecimal.ZERO) <= 0) {
                throw new IllegalArgumentException("Batch volume is too small for this recipe");
            }
            inventoryService.removeIngredient(
                    new IngredientRequest(player.getId(), line.getIngredient().getId(), requiredQuantity)
            );
        }

        LocalDateTime now = LocalDateTime.now();
        double factor = effectService.durationFactor(player.getId(), EffectKind.FEU_SOUS_LA_CUVE);
        long fermentationMinutes = Math.max(1,
                Math.round(recipe.getFermentationMinutes() * factor));

        Batch batch = batchRepository.save(
                Batch.builder()
                        .player(player)
                        .recipe(recipe)
                        .volume(request.volume())
                        .startedAt(now)
                        .readyAt(now.plusMinutes(fermentationMinutes))
                        .status(BatchStatus.BREWING)
                        .quality(null)
                        .build()
        );

        progressionService.record(playerId, ProgressAction.START_BATCH);

        return brewMapper.toResponse(batch);
    }

    /** Une gorgée : le fût baisse un peu, l'effet de la recette s'installe. */
    @Transactional
    public TastingResponse taste(Long playerId, Long batchId) {
        Batch batch = getOwnedBatch(playerId, batchId);
        refreshBatchStatus(batch);
        if (batch.getStatus() != BatchStatus.READY) {
            throw new IllegalStateException("Ce brassin n'est pas encore prêt à boire.");
        }

        BigDecimal sip = new BigDecimal("0.50").min(batch.getVolume());
        batch.setVolume(batch.getVolume().subtract(sip));
        if (batch.getVolume().compareTo(BigDecimal.ZERO) <= 0) {
            batch.setStatus(BatchStatus.SOLD_OUT);
        }

        PlayerEffectResponse effect = effectService.grant(playerId, batch.getRecipe());
        return new TastingResponse(batch.getRecipe().getName(), batch.getRecipe().getFlavour(), effect);
    }

    @Transactional
    public BatchResponse updateBatchStatus(Long playerId, Long batchId) {
        Batch batch = getOwnedBatch(playerId, batchId);
        refreshBatchStatus(batch);
        return brewMapper.toResponse(batch);
    }

    @Transactional
    public void refreshPlayerBatches(Long playerId) {
        batchRepository.findAllByPlayerIdOrderByStartedAtDesc(playerId)
                .forEach(this::refreshBatchStatus);
    }

    @Transactional
    public void consumeReadyProduct(Long playerId, Long recipeId, BigDecimal requiredVolume, int minQuality) {
        if (requiredVolume == null || requiredVolume.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Requested product volume must be greater than zero");
        }

        refreshPlayerBatches(playerId);
        List<Batch> batches = batchRepository
                .findAllByPlayerIdAndRecipeIdAndStatusAndQualityGreaterThanEqualOrderByReadyAtAsc(
                        playerId,
                        recipeId,
                        BatchStatus.READY,
                        minQuality
                );

        BigDecimal remaining = requiredVolume;
        for (Batch batch : batches) {
            if (remaining.compareTo(BigDecimal.ZERO) <= 0) {
                break;
            }

            BigDecimal taken = batch.getVolume().min(remaining);
            batch.setVolume(batch.getVolume().subtract(taken));
            remaining = remaining.subtract(taken);

            if (batch.getVolume().compareTo(BigDecimal.ZERO) == 0) {
                batch.setStatus(BatchStatus.SOLD_OUT);
            }
        }

        if (remaining.compareTo(BigDecimal.ZERO) > 0) {
            throw new InsufficientStockException("Not enough finished product for this order");
        }
    }

    private PlayerProfile getPlayer(Long playerId) {
        return playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Player not found"));
    }

    private Batch getOwnedBatch(Long playerId, Long batchId) {
        Batch batch = batchRepository.findById(batchId)
                .orElseThrow(() -> new IllegalArgumentException("Brassin introuvable."));
        if (!batch.getPlayer().getId().equals(playerId)) {
            throw new AccessDeniedException("Ce brassin n'est pas le tien.");
        }
        return batch;
    }

    private void refreshBatchStatus(Batch batch) {
        if (batch.getStatus() == BatchStatus.SOLD_OUT || batch.getStatus() == BatchStatus.CANCELLED) {
            return;
        }

        LocalDateTime now = LocalDateTime.now();
        if (!now.isBefore(batch.getReadyAt())) {
            batch.setStatus(BatchStatus.READY);
            if (batch.getQuality() == null) {
                batch.setQuality(calculateQuality(batch));
            }
            return;
        }

        long totalMillis = Math.max(1, Duration.between(batch.getStartedAt(), batch.getReadyAt()).toMillis());
        long elapsedMillis = Math.max(0, Duration.between(batch.getStartedAt(), now).toMillis());
        double progress = Math.min(1.0, (double) elapsedMillis / totalMillis);

        if (progress < 0.20) {
            batch.setStatus(BatchStatus.BREWING);
        } else if (progress < 0.85) {
            batch.setStatus(BatchStatus.FERMENTING);
        } else {
            batch.setStatus(BatchStatus.CONDITIONING);
        }
    }

    private int calculateQuality(Batch batch) {
        int ingredientVariety = recipeIngredientRepository.findAllByRecipeId(batch.getRecipe().getId()).size();
        int quality = 55
                + Math.min(25, batch.getPlayer().getLevel() * 2)
                + Math.min(20, ingredientVariety * 4)
                + effectService.qualityShift(batch.getPlayer().getId())
                + progressionService.brewingQualityBonus(batch.getPlayer().getId());
        return Math.max(1, Math.min(100, quality));
    }
}
