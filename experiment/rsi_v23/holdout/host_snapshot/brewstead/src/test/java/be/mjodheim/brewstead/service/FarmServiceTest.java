package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.farm.PlantCropRequest;
import be.mjodheim.brewstead.entity.Crop;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerField;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.FieldStatus;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.mapper.FarmMapper;
import be.mjodheim.brewstead.repository.CropRepository;
import be.mjodheim.brewstead.repository.PlayerFieldRepository;
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
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.ingredient;
import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class FarmServiceTest {

    @Mock PlayerFieldRepository fieldRepository;
    @Mock InventoryService inventoryService;
    @Mock CropRepository cropRepository;
    @Mock FarmMapper mapper;
    @Mock EffectService effectService;
    @Mock ProgressionService progressionService;
    @Mock PlayerService playerService;
    @InjectMocks FarmService service;

    @Test
    void clearingAFieldCostsCoinsAndAddsAnEmptyOne() {
        PlayerProfile owner = player(1);
        when(fieldRepository.findAllByPlayerId(1L))
                .thenReturn(List.of(fieldOf(owner), fieldOf(owner), fieldOf(owner)))  // les trois du départ
                .thenReturn(List.of());
        when(playerService.getPlayerEntity(1L)).thenReturn(owner);
        when(mapper.toResponseList(anyList())).thenReturn(List.of());

        service.clearNewField(1L);

        verify(playerService).spendCoins(1L, 400);
        ArgumentCaptor<PlayerField> defrichee = ArgumentCaptor.forClass(PlayerField.class);
        verify(fieldRepository).save(defrichee.capture());
        assertEquals(FieldStatus.EMPTY, defrichee.getValue().getStatus());
    }

    @Test
    void eachNewFieldCostsTwiceThePrevious() {
        PlayerProfile owner = player(1);
        when(playerService.getPlayerEntity(1L)).thenReturn(owner);
        when(mapper.toResponseList(anyList())).thenReturn(List.of());

        for (int possedees = 3; possedees < 8; possedees++) {
            when(fieldRepository.findAllByPlayerId(1L)).thenReturn(champs(owner, possedees));
            service.clearNewField(1L);
        }

        verify(playerService).spendCoins(1L, 400);
        verify(playerService).spendCoins(1L, 800);
        verify(playerService).spendCoins(1L, 1600);
        verify(playerService).spendCoins(1L, 3200);
        verify(playerService).spendCoins(1L, 6400);
    }

    @Test
    void theEstateStopsAtEightFields() {
        when(fieldRepository.findAllByPlayerId(1L)).thenReturn(champs(player(1), 8));

        assertThrows(IllegalStateException.class, () -> service.clearNewField(1L));
        verify(playerService, never()).spendCoins(anyLong(), anyInt());
        verify(fieldRepository, never()).save(any());
    }

    private static List<PlayerField> champs(PlayerProfile owner, int combien) {
        List<PlayerField> parcelles = new ArrayList<>();
        for (int i = 0; i < combien; i++) parcelles.add(fieldOf(owner));
        return parcelles;
    }

    private static PlayerField fieldOf(PlayerProfile owner) {
        return PlayerField.builder().player(owner).status(FieldStatus.EMPTY).build();
    }

    @Test
    void findAllFieldsRefreshesReadyCropsBeforeMapping() {
        PlayerField field = PlayerField.builder()
                .player(player(1))
                .status(FieldStatus.GROWING)
                .readyAt(LocalDateTime.now().minusSeconds(1))
                .build();
        List<PlayerField> fields = List.of(field);
        when(fieldRepository.findAllByPlayerId(1L)).thenReturn(fields);
        when(mapper.toResponseList(fields)).thenReturn(List.of());

        service.findAllFields(1L);

        assertEquals(FieldStatus.READY, field.getStatus());
        verify(mapper).toResponseList(fields);
    }

    @Test
    void plantStartsGrowthUsingActiveDurationFactor() {
        PlayerProfile owner = player(1);
        Ingredient harvest = ingredient(8, IngredientType.CEREAL);
        Crop crop = Crop.builder()
                .id(3L)
                .name("Orge")
                .ingredient(harvest)
                .growDurationMinutes(10)
                .yieldQuantity(new BigDecimal("4.000"))
                .build();
        PlayerField field = PlayerField.builder()
                .id(5L).player(owner).status(FieldStatus.EMPTY).build();
        when(cropRepository.findById(3L)).thenReturn(Optional.of(crop));
        when(fieldRepository.findById(5L)).thenReturn(Optional.of(field));
        when(effectService.durationFactor(1L, EffectKind.MAIN_VERTE)).thenReturn(0.5);

        service.plant(1L, new PlantCropRequest(5L, 3L));

        assertEquals(FieldStatus.GROWING, field.getStatus());
        assertSame(crop, field.getCrop());
        assertNotNull(field.getPlantedAt());
        assertNotNull(field.getReadyAt());
        assertEquals(5, Duration.between(field.getPlantedAt(), field.getReadyAt()).toMinutes());
    }

    @Test
    void plantRejectsOccupiedField() {
        PlayerProfile owner = player(1);
        Crop crop = Crop.builder().id(3L).growDurationMinutes(10).build();
        PlayerField field = PlayerField.builder()
                .id(5L).player(owner).status(FieldStatus.GROWING).build();
        when(cropRepository.findById(3L)).thenReturn(Optional.of(crop));
        when(fieldRepository.findById(5L)).thenReturn(Optional.of(field));

        assertThrows(IllegalStateException.class,
                () -> service.plant(1L, new PlantCropRequest(5L, 3L)));
        verifyNoInteractions(effectService);
    }

    @Test
    void operationsRejectForeignField() {
        PlayerField field = PlayerField.builder()
                .id(5L).player(player(2)).status(FieldStatus.EMPTY).build();
        when(fieldRepository.findById(5L)).thenReturn(Optional.of(field));

        assertThrows(AccessDeniedException.class,
                () -> service.updateFieldStatus(1L, 5L));
    }

    @Test
    void missingFieldIsRejected() {
        when(fieldRepository.findById(99L)).thenReturn(Optional.empty());

        assertThrows(IllegalArgumentException.class,
                () -> service.updateFieldStatus(1L, 99L));
    }

    @Test
    void harvestRequiresReadyField() {
        PlayerField field = PlayerField.builder()
                .id(5L).player(player(1)).status(FieldStatus.GROWING)
                .readyAt(LocalDateTime.now().plusMinutes(2)).build();
        when(fieldRepository.findById(5L)).thenReturn(Optional.of(field));

        assertThrows(IllegalStateException.class, () -> service.harvest(1L, 5L));
        verifyNoInteractions(inventoryService);
    }

    @Test
    void harvestAddsYieldAndResetsField() {
        PlayerProfile owner = player(1);
        Ingredient ingredient = ingredient(8, IngredientType.CEREAL);
        Crop crop = Crop.builder()
                .id(3L).ingredient(ingredient)
                .yieldQuantity(new BigDecimal("4.000")).build();
        PlayerField field = PlayerField.builder()
                .id(5L).player(owner).crop(crop)
                .status(FieldStatus.GROWING)
                .plantedAt(LocalDateTime.now().minusMinutes(5))
                .readyAt(LocalDateTime.now().minusSeconds(1))
                .build();
        when(fieldRepository.findById(5L)).thenReturn(Optional.of(field));

        when(progressionService.harvestYield(eq(1L), any(BigDecimal.class)))
                .thenAnswer(call -> call.getArgument(1));
        service.harvest(1L, 5L);

        verify(inventoryService).addIngredient(argThat(request ->
                request.playerId().equals(1L)
                        && request.ingredientId().equals(8L)
                        && request.quantity().compareTo(new BigDecimal("4.000")) == 0));
        assertEquals(FieldStatus.EMPTY, field.getStatus());
        assertNull(field.getCrop());
        assertNull(field.getPlantedAt());
        assertNull(field.getReadyAt());
    }

    /**
     * La tournée ne ramasse que ce qui est mûr, laisse pousser le reste et
     * compte ce qu'elle a pris — le client n'a pas à recompter.
     */
    @Test
    void harvestAllTakesOnlyTheRipeFieldsAndCountsThem() {
        PlayerProfile owner = player(1);
        Crop crop = Crop.builder()
                .id(3L).ingredient(ingredient(8, IngredientType.CEREAL))
                .yieldQuantity(new BigDecimal("4.000")).build();

        PlayerField ripe = PlayerField.builder()
                .id(5L).player(owner).crop(crop).status(FieldStatus.GROWING)
                .plantedAt(LocalDateTime.now().minusMinutes(9))
                .readyAt(LocalDateTime.now().minusSeconds(1)).build();
        PlayerField alsoRipe = PlayerField.builder()
                .id(6L).player(owner).crop(crop).status(FieldStatus.READY)
                .plantedAt(LocalDateTime.now().minusMinutes(9))
                .readyAt(LocalDateTime.now().minusMinutes(1)).build();
        PlayerField growing = PlayerField.builder()
                .id(7L).player(owner).crop(crop).status(FieldStatus.GROWING)
                .plantedAt(LocalDateTime.now().minusMinutes(1))
                .readyAt(LocalDateTime.now().plusMinutes(8)).build();
        PlayerField bare = PlayerField.builder()
                .id(8L).player(owner).status(FieldStatus.EMPTY).build();

        when(fieldRepository.findAllByPlayerId(1L))
                .thenReturn(List.of(ripe, alsoRipe, growing, bare));
        when(fieldRepository.findById(5L)).thenReturn(Optional.of(ripe));
        when(fieldRepository.findById(6L)).thenReturn(Optional.of(alsoRipe));
        when(progressionService.harvestYield(eq(1L), any(BigDecimal.class)))
                .thenAnswer(call -> call.getArgument(1));

        assertEquals(2, service.harvestAll(1L));

        verify(inventoryService, times(2)).addIngredient(any());
        assertEquals(FieldStatus.EMPTY, ripe.getStatus());
        assertEquals(FieldStatus.EMPTY, alsoRipe.getStatus());
        assertEquals(FieldStatus.GROWING, growing.getStatus(), "ce qui pousse encore reste en terre");
        assertEquals(FieldStatus.EMPTY, bare.getStatus());
    }

    @Test
    void harvestAllOnAnIdleDomainTakesNothing() {
        when(fieldRepository.findAllByPlayerId(1L)).thenReturn(List.of());

        assertEquals(0, service.harvestAll(1L));
        verifyNoInteractions(inventoryService);
    }
}
