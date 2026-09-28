package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.entity.Beehive;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.enums.BehiveStatus;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.mapper.ApiaryMapper;
import be.mjodheim.brewstead.repository.BeehiveRepository;
import be.mjodheim.brewstead.repository.IngredientRepository;
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
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.ingredient;
import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ApiaryServiceTest {

    @Mock BeehiveRepository beehiveRepository;
    @Mock IngredientRepository ingredientRepository;
    @Mock InventoryService inventoryService;
    @Mock ApiaryMapper mapper;
    @Mock EffectService effectService;
    @Mock ProgressionService progressionService;
    @Mock PlayerService playerService;
    @InjectMocks ApiaryService service;

    @Test
    void installingAHiveCostsCoinsAndStartsItWorking() {
        PlayerProfile owner = player(1);
        when(beehiveRepository.findAllByPlayerId(1L))
                .thenReturn(List.of(hiveOf(owner), hiveOf(owner)))   // les deux du départ
                .thenReturn(List.of());
        when(playerService.getPlayerEntity(1L)).thenReturn(owner);
        when(mapper.toResponseList(anyList())).thenReturn(List.of());

        service.installNewHive(1L);

        // Deux ruches possédées : la troisième est au premier palier.
        verify(playerService).spendCoins(1L, 500);
        ArgumentCaptor<Beehive> posee = ArgumentCaptor.forClass(Beehive.class);
        verify(beehiveRepository).save(posee.capture());
        assertEquals(1, posee.getValue().getLevel());
        assertEquals(BehiveStatus.PRODUCING, posee.getValue().getStatus(),
                "une ruche qu'on vient de payer ne doit pas attendre un clic de plus");
    }

    @Test
    void theApiaryStopsAtSixHives() {
        when(beehiveRepository.findAllByPlayerId(1L))
                .thenReturn(List.of(hiveOf(player(1)), hiveOf(player(1)), hiveOf(player(1)),
                        hiveOf(player(1)), hiveOf(player(1)), hiveOf(player(1))));

        assertThrows(IllegalStateException.class, () -> service.installNewHive(1L));
        verify(playerService, never()).spendCoins(anyLong(), anyInt());
        verify(beehiveRepository, never()).save(any());
    }

    @Test
    void upgradingAHiveRaisesItsLevelUpToTheCeiling() {
        PlayerProfile owner = player(1);
        Beehive hive = Beehive.builder().id(5L).player(owner).level(1).status(BehiveStatus.PRODUCING).build();
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));

        service.upgradeHive(1L, 5L);
        assertEquals(2, hive.getLevel());
        verify(playerService).spendCoins(1L, 700);

        service.upgradeHive(1L, 5L);
        assertEquals(3, hive.getLevel());
        verify(playerService).spendCoins(1L, 1800);

        // Au plafond, on ne prend pas la pièce.
        assertThrows(IllegalStateException.class, () -> service.upgradeHive(1L, 5L));
        assertEquals(3, hive.getLevel());
        verifyNoMoreInteractions(playerService);
    }

    @Test
    void upgradingLetsTheBeesFinishTheirCurrentRound() {
        PlayerProfile owner = player(1);
        LocalDateTime debut = LocalDateTime.now().minusMinutes(3);
        Beehive hive = Beehive.builder().id(5L).player(owner).level(1)
                .status(BehiveStatus.PRODUCING).startedAt(debut).readyAt(debut.plusMinutes(10)).build();
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));

        service.upgradeHive(1L, 5L);

        assertEquals(debut, hive.getStartedAt(), "la tournée en cours ne doit pas être relancée");
        assertEquals(debut.plusMinutes(10), hive.getReadyAt());
    }

    private static Beehive hiveOf(PlayerProfile owner) {
        return Beehive.builder().player(owner).level(1).status(BehiveStatus.IDLE).build();
    }

    @Test
    void findAllHivesRefreshesReadyHives() {
        Beehive hive = Beehive.builder()
                .player(player(1))
                .status(BehiveStatus.PRODUCING)
                .readyAt(LocalDateTime.now().minusSeconds(1))
                .build();
        List<Beehive> hives = List.of(hive);
        when(beehiveRepository.findAllByPlayerId(1L)).thenReturn(hives);
        when(mapper.toResponseList(hives)).thenReturn(List.of());

        service.findAllHives(1L);

        assertEquals(BehiveStatus.READY, hive.getStatus());
    }

    @Test
    void startProductionUsesLevelAndEffectForDuration() {
        PlayerProfile owner = player(1);
        Beehive hive = Beehive.builder()
                .id(5L).player(owner).level(3).status(BehiveStatus.IDLE).build();
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));
        when(effectService.durationFactor(1L, EffectKind.BOURDONNEMENT)).thenReturn(0.5);

        service.startProduction(1L, 5L);

        assertEquals(BehiveStatus.PRODUCING, hive.getStatus());
        assertEquals(4, Duration.between(hive.getStartedAt(), hive.getReadyAt()).toMinutes());
    }

    @Test
    void startProductionRequiresIdleHive() {
        Beehive hive = Beehive.builder()
                .id(5L).player(player(1)).status(BehiveStatus.READY).build();
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));

        assertThrows(IllegalStateException.class,
                () -> service.startProduction(1L, 5L));
    }

    @Test
    void operationsRejectForeignHive() {
        Beehive hive = Beehive.builder()
                .id(5L).player(player(2)).status(BehiveStatus.IDLE).build();
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));

        assertThrows(AccessDeniedException.class,
                () -> service.updateHiveStatus(1L, 5L));
    }

    @Test
    void harvestRequiresReadyHive() {
        Beehive hive = Beehive.builder()
                .id(5L).player(player(1)).status(BehiveStatus.PRODUCING)
                .readyAt(LocalDateTime.now().plusMinutes(1)).build();
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));

        assertThrows(IllegalStateException.class, () -> service.harvest(1L, 5L));
        verifyNoInteractions(ingredientRepository, inventoryService);
    }

    @Test
    void harvestAddsHoneyScaledByHiveLevelAndResetsHive() {
        Beehive hive = Beehive.builder()
                .id(5L).player(player(1)).level(3).status(BehiveStatus.READY).build();
        Ingredient honey = ingredient(8, IngredientType.HONEY);
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));
        when(ingredientRepository.findFirstByType(IngredientType.HONEY))
                .thenReturn(Optional.of(honey));

        when(progressionService.harvestYield(eq(1L), any(BigDecimal.class)))
                .thenAnswer(call -> call.getArgument(1));
        service.harvest(1L, 5L);

        verify(inventoryService).addIngredient(argThat(request ->
                request.playerId().equals(1L)
                        && request.ingredientId().equals(8L)
                        && request.quantity().compareTo(new BigDecimal("3.000")) == 0));
        // La ruche ne s'endort plus : elle repart aussitôt.
        assertEquals(BehiveStatus.PRODUCING, hive.getStatus());
        assertNotNull(hive.getStartedAt());
        assertTrue(hive.getReadyAt().isAfter(LocalDateTime.now()));
    }

    @Test
    void harvestFailsWhenHoneyIsNotConfigured() {
        Beehive hive = Beehive.builder()
                .id(5L).player(player(1)).status(BehiveStatus.READY).build();
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(hive));
        when(ingredientRepository.findFirstByType(IngredientType.HONEY))
                .thenReturn(Optional.empty());

        assertThrows(IllegalStateException.class, () -> service.harvest(1L, 5L));
    }

    /** La tournée vide les ruches mûres et laisse travailler les autres. */
    @Test
    void harvestAllEmptiesOnlyTheReadyHives() {
        PlayerProfile owner = player(1);
        Beehive ready = Beehive.builder()
                .id(5L).player(owner).level(1).status(BehiveStatus.READY).build();
        Beehive justDone = Beehive.builder()
                .id(6L).player(owner).level(1).status(BehiveStatus.PRODUCING)
                .startedAt(LocalDateTime.now().minusHours(1))
                .readyAt(LocalDateTime.now().minusSeconds(1)).build();
        Beehive working = Beehive.builder()
                .id(7L).player(owner).level(1).status(BehiveStatus.PRODUCING)
                .startedAt(LocalDateTime.now().minusMinutes(1))
                .readyAt(LocalDateTime.now().plusMinutes(20)).build();
        Beehive asleep = Beehive.builder()
                .id(8L).player(owner).level(1).status(BehiveStatus.IDLE).build();

        when(beehiveRepository.findAllByPlayerId(1L))
                .thenReturn(List.of(ready, justDone, working, asleep));
        when(beehiveRepository.findById(5L)).thenReturn(Optional.of(ready));
        when(beehiveRepository.findById(6L)).thenReturn(Optional.of(justDone));
        when(ingredientRepository.findFirstByType(IngredientType.HONEY))
                .thenReturn(Optional.of(ingredient(8, IngredientType.HONEY)));
        when(progressionService.harvestYield(eq(1L), any(BigDecimal.class)))
                .thenAnswer(call -> call.getArgument(1));

        assertEquals(2, service.harvestAll(1L));

        verify(inventoryService, times(2)).addIngredient(any());
        assertEquals(BehiveStatus.PRODUCING, ready.getStatus(), "une ruche récoltée repart");
        assertEquals(BehiveStatus.PRODUCING, justDone.getStatus());
        assertEquals(BehiveStatus.PRODUCING, working.getStatus(), "une ruche au travail n'est pas dérangée");
        assertEquals(BehiveStatus.PRODUCING, asleep.getStatus(), "une ruche endormie se réveille seule");
    }

    @Test
    void harvestAllOnAnIdleApiaryTakesNothing() {
        when(beehiveRepository.findAllByPlayerId(1L)).thenReturn(List.of());

        assertEquals(0, service.harvestAll(1L));
        verifyNoInteractions(inventoryService);
    }
}
