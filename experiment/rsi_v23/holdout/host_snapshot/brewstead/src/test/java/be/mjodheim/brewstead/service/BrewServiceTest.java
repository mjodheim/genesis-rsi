package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.brew.StartBatchRequest;
import be.mjodheim.brewstead.dto.brew.TastingResponse;
import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.BatchStatus;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.exception.InsufficientStockException;
import be.mjodheim.brewstead.mapper.BrewMapper;
import be.mjodheim.brewstead.repository.BatchRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.RecipeIngredientRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.access.AccessDeniedException;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class BrewServiceTest {

    @Mock BatchRepository batchRepository;
    @Mock PlayerProfileRepository playerRepository;
    @Mock RecipeIngredientRepository recipeIngredientRepository;
    @Mock RecipeService recipeService;
    @Mock InventoryService inventoryService;
    @Mock BrewMapper mapper;
    @Mock EffectService effectService;
    @Mock ProgressionService progressionService;
    @InjectMocks BrewService service;

    @Test
    void startBatchRejectsInvalidVolume() {
        assertThrows(IllegalArgumentException.class,
                () -> service.startBatch(1L, new StartBatchRequest(1L, 2L, null)));
        assertThrows(IllegalArgumentException.class,
                () -> service.startBatch(1L, new StartBatchRequest(1L, 2L, BigDecimal.ZERO)));
        verifyNoInteractions(playerRepository);
    }

    @Test
    void startBatchRequiresRecipeIngredients() {
        PlayerProfile player = player(1);
        Recipe recipe = recipe(2);
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player));
        when(recipeService.getAccessibleRecipeEntity(1L, 2L)).thenReturn(recipe);
        when(recipeIngredientRepository.findAllByRecipeId(2L)).thenReturn(List.of());

        assertThrows(IllegalStateException.class,
                () -> service.startBatch(1L,
                        new StartBatchRequest(1L, 2L, new BigDecimal("10"))));
    }

    @Test
    void startBatchScalesIngredientsAndFermentationDuration() {
        PlayerProfile player = player(1);
        Recipe recipe = recipe(2);
        recipe.setBaseVolume(new BigDecimal("10.00"));
        recipe.setFermentationDurationMinutes(20);
        Ingredient honey = ingredient(3, IngredientType.HONEY);
        RecipeIngredient line = RecipeIngredient.builder()
                .recipe(recipe).ingredient(honey).quantity(new BigDecimal("2.000")).build();

        when(playerRepository.findById(1L)).thenReturn(Optional.of(player));
        when(recipeService.getAccessibleRecipeEntity(1L, 2L)).thenReturn(recipe);
        when(recipeIngredientRepository.findAllByRecipeId(2L)).thenReturn(List.of(line));
        when(effectService.durationFactor(1L, EffectKind.FEU_SOUS_LA_CUVE)).thenReturn(0.5);
        when(batchRepository.save(any(Batch.class))).thenAnswer(invocation -> invocation.getArgument(0));

        service.startBatch(1L,
                new StartBatchRequest(1L, 2L, new BigDecimal("5.00")));

        verify(inventoryService).removeIngredient(argThat(request ->
                request.playerId().equals(1L)
                        && request.ingredientId().equals(3L)
                        && request.quantity().compareTo(new BigDecimal("1.000")) == 0));

        ArgumentCaptor<Batch> captor = ArgumentCaptor.forClass(Batch.class);
        verify(batchRepository).save(captor.capture());
        Batch saved = captor.getValue();
        assertEquals(BatchStatus.BREWING, saved.getStatus());
        assertEquals(new BigDecimal("5.00"), saved.getVolume());
        assertEquals(10, Duration.between(saved.getStartedAt(), saved.getReadyAt()).toMinutes());
    }

    @Test
    void tasteRequiresOwnedReadyBatch() {
        Batch foreign = batch(4, player(2), recipe(3));
        when(batchRepository.findById(4L)).thenReturn(Optional.of(foreign));
        assertThrows(AccessDeniedException.class, () -> service.taste(1L, 4L));

        Batch brewing = batch(5, player(1), recipe(3));
        brewing.setStatus(BatchStatus.BREWING);
        brewing.setReadyAt(LocalDateTime.now().plusMinutes(2));
        when(batchRepository.findById(5L)).thenReturn(Optional.of(brewing));
        assertThrows(IllegalStateException.class, () -> service.taste(1L, 5L));
    }

    @Test
    void tasteConsumesServingAndGrantsRecipeEffect() {
        Recipe recipe = recipe(3);
        recipe.setFlavour("fumé");
        Batch ready = batch(4, player(1), recipe);
        ready.setStatus(BatchStatus.READY);
        ready.setReadyAt(LocalDateTime.now().minusSeconds(1));
        ready.setVolume(new BigDecimal("2.00"));
        when(batchRepository.findById(4L)).thenReturn(Optional.of(ready));

        TastingResponse result = service.taste(1L, 4L);

        assertEquals(new BigDecimal("1.50"), ready.getVolume());
        assertEquals(BatchStatus.READY, ready.getStatus());
        assertEquals(recipe.getName(), result.recipeName());
        assertEquals("fumé", result.flavour());
        verify(effectService).grant(1L, recipe);
    }

    @Test
    void tastingLastDropsMarksBatchSoldOut() {
        Recipe recipe = recipe(3);
        Batch ready = batch(4, player(1), recipe);
        ready.setStatus(BatchStatus.READY);
        ready.setReadyAt(LocalDateTime.now().minusSeconds(1));
        ready.setVolume(new BigDecimal("0.30"));
        when(batchRepository.findById(4L)).thenReturn(Optional.of(ready));

        service.taste(1L, 4L);

        assertEquals(0, ready.getVolume().compareTo(BigDecimal.ZERO));
        assertEquals(BatchStatus.SOLD_OUT, ready.getStatus());
    }

    @Test
    void refreshMovesBatchThroughLifecycleAndCalculatesQuality() {
        PlayerProfile player = player(1);
        player.setLevel(5);
        Recipe recipe = recipe(3);
        LocalDateTime now = LocalDateTime.now();
        Batch brewing = lifecycleBatch(1, player, recipe, now.minusMinutes(1), now.plusMinutes(9));
        Batch fermenting = lifecycleBatch(2, player, recipe, now.minusMinutes(5), now.plusMinutes(5));
        Batch conditioning = lifecycleBatch(3, player, recipe, now.minusMinutes(9), now.plusMinutes(1));
        Batch ready = lifecycleBatch(4, player, recipe, now.minusMinutes(11), now.minusMinutes(1));
        Map<Long, Batch> batches = Map.of(1L, brewing, 2L, fermenting, 3L, conditioning, 4L, ready);

        when(batchRepository.findById(anyLong()))
                .thenAnswer(invocation -> Optional.of(batches.get(invocation.getArgument(0))));
        when(recipeIngredientRepository.findAllByRecipeId(3L))
                .thenReturn(List.of(new RecipeIngredient(), new RecipeIngredient(), new RecipeIngredient()));
        when(effectService.qualityShift(1L)).thenReturn(5);

        service.updateBatchStatus(1L, 1L);
        service.updateBatchStatus(1L, 2L);
        service.updateBatchStatus(1L, 3L);
        service.updateBatchStatus(1L, 4L);

        assertEquals(BatchStatus.BREWING, brewing.getStatus());
        assertEquals(BatchStatus.FERMENTING, fermenting.getStatus());
        assertEquals(BatchStatus.CONDITIONING, conditioning.getStatus());
        assertEquals(BatchStatus.READY, ready.getStatus());
        assertEquals(82, ready.getQuality());
    }

    @Test
    void soldOutBatchIsNotReopenedByRefresh() {
        Batch soldOut = batch(4, player(1), recipe(3));
        soldOut.setStatus(BatchStatus.SOLD_OUT);
        soldOut.setReadyAt(LocalDateTime.now().minusMinutes(1));
        when(batchRepository.findById(4L)).thenReturn(Optional.of(soldOut));

        service.updateBatchStatus(1L, 4L);

        assertEquals(BatchStatus.SOLD_OUT, soldOut.getStatus());
    }

    @Test
    void consumeReadyProductUsesOldestEligibleBatches() {
        Recipe recipe = recipe(3);
        PlayerProfile player = player(1);
        Batch first = batch(1, player, recipe);
        first.setStatus(BatchStatus.READY);
        first.setVolume(new BigDecimal("1.50"));
        Batch second = batch(2, player, recipe);
        second.setStatus(BatchStatus.READY);
        second.setVolume(new BigDecimal("2.00"));

        when(batchRepository.findAllByPlayerIdOrderByStartedAtDesc(1L)).thenReturn(List.of());
        when(batchRepository.findAllByPlayerIdAndRecipeIdAndStatusAndQualityGreaterThanEqualOrderByReadyAtAsc(
                1L, 3L, BatchStatus.READY, 70)).thenReturn(List.of(first, second));

        service.consumeReadyProduct(1L, 3L, new BigDecimal("2.00"), 70);

        assertEquals(0, first.getVolume().compareTo(BigDecimal.ZERO));
        assertEquals(BatchStatus.SOLD_OUT, first.getStatus());
        assertEquals(0, second.getVolume().compareTo(new BigDecimal("1.50")));
    }

    @Test
    void consumeReadyProductRejectsInvalidOrInsufficientVolume() {
        assertThrows(IllegalArgumentException.class,
                () -> service.consumeReadyProduct(1L, 3L, BigDecimal.ZERO, 0));

        Batch batch = batch(1, player(1), recipe(3));
        batch.setStatus(BatchStatus.READY);
        batch.setVolume(new BigDecimal("0.50"));
        when(batchRepository.findAllByPlayerIdOrderByStartedAtDesc(1L)).thenReturn(List.of());
        when(batchRepository.findAllByPlayerIdAndRecipeIdAndStatusAndQualityGreaterThanEqualOrderByReadyAtAsc(
                1L, 3L, BatchStatus.READY, 0)).thenReturn(List.of(batch));

        assertThrows(InsufficientStockException.class,
                () -> service.consumeReadyProduct(1L, 3L, BigDecimal.ONE, 0));
    }

    private Batch lifecycleBatch(long id, PlayerProfile player, Recipe recipe,
                                 LocalDateTime startedAt, LocalDateTime readyAt) {
        return Batch.builder()
                .id(id).player(player).recipe(recipe)
                .volume(BigDecimal.TEN)
                .startedAt(startedAt).readyAt(readyAt)
                .status(BatchStatus.BREWING)
                .build();
    }
}
