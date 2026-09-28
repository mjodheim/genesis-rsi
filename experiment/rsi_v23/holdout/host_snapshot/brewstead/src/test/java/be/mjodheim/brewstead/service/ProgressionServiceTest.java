package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.progression.ProgressionResponse;
import be.mjodheim.brewstead.entity.PlayerAchievement;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.PlayerProgress;
import be.mjodheim.brewstead.enums.ProgressAction;
import be.mjodheim.brewstead.repository.PlayerAchievementRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.PlayerProgressRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.ZoneOffset;

import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ProgressionServiceTest {

    @Mock PlayerProgressRepository progressRepository;
    @Mock PlayerAchievementRepository achievementRepository;
    @Mock PlayerProfileRepository playerRepository;

    ProgressionService service;
    PlayerProfile player;
    PlayerProgress progress;
    List<PlayerAchievement> unlocked;

    @BeforeEach
    void setUp() {
        service = new ProgressionService(progressRepository, achievementRepository, playerRepository);
        player = player(1);
        progress = PlayerProgress.builder().player(player).build();
        unlocked = new ArrayList<>();
        lenient().when(progressRepository.findByPlayerId(1L)).thenReturn(Optional.of(progress));
        lenient().when(achievementRepository.findAllByPlayerId(1L)).thenAnswer(call -> List.copyOf(unlocked));
        lenient().when(achievementRepository.existsByPlayerIdAndCode(eq(1L), anyString()))
                .thenAnswer(call -> unlocked.stream().anyMatch(a -> a.getCode().equals(call.getArgument(1))));
        lenient().when(achievementRepository.save(any())).thenAnswer(call -> {
            PlayerAchievement achievement = call.getArgument(0);
            unlocked.add(achievement);
            return achievement;
        });
    }

    @Test
    void visitStartsAndKeepsDailyStreak() {
        ProgressionResponse first = service.visit(1L);
        ProgressionResponse second = service.visit(1L);

        assertEquals(1, first.visitStreak());
        assertEquals(1, second.visitStreak());
        assertNotNull(first.dailyQuest());
        assertEquals(3, first.dailyQuest().target());
    }

    @Test
    void firstHarvestUnlocksAchievementOnlyOnce() {
        int initialCoins = player.getCoin();

        service.record(1L, ProgressAction.HARVEST_FIELD);
        service.visit(1L);

        assertTrue(unlocked.stream().anyMatch(a -> a.getCode().equals("FIRST_HARVEST")));
        assertEquals(initialCoins + 40, player.getCoin());
        verify(achievementRepository, times(1)).save(any(PlayerAchievement.class));
    }

    @Test
    void matchingDailyQuestPaysRewardAtTarget() {
        service.visit(1L);
        ProgressAction daily = progress.getDailyAction();
        int initialCoins = player.getCoin();

        service.record(1L, daily);
        service.record(1L, daily);
        service.record(1L, daily);
        service.record(1L, daily);

        ProgressionResponse response = service.visit(1L);
        assertTrue(response.dailyQuest().claimed());
        assertEquals(3, response.dailyQuest().progress());
        assertTrue(player.getCoin() >= initialCoins + 75);
    }

    @Test
    void newEstateOnlyEverGetsAQuestItCanActuallyDo() {
        ProgressionResponse response = service.visit(1L);

        // Quel que soit le jour de l'année, un domaine neuf n'a ni cave ni
        // voisins : seules les deux récoltes lui sont accessibles.
        assertTrue(Set.of("HARVEST_FIELD", "HARVEST_HIVE").contains(response.dailyQuest().action()),
                "objectif impossible pour un débutant : " + response.dailyQuest().title());
    }

    @Test
    void anAccomplishedEstateGetsTheCalendarRotationBack() {
        progress.setStartedBatches(4);
        progress.setCompletedOrders(4);
        progress.setPlayerTrades(4);
        progress.setTavernTastings(4);

        String[] rotation = {"HARVEST_FIELD", "HARVEST_HIVE", "START_BATCH",
                "COMPLETE_ORDER", "PLAYER_TRADE", "TASTE_AT_TAVERN"};
        int today = LocalDate.now(ZoneOffset.UTC).getDayOfYear();

        assertEquals(rotation[today % rotation.length], service.visit(1L).dailyQuest().action());
    }

    @Test
    void doingSomethingOnceOpensItAsATomorrowQuest() {
        assertTrue(Set.of("HARVEST_FIELD", "HARVEST_HIVE")
                .contains(service.visit(1L).dailyQuest().action()));

        // Le joueur découvre le reste du domaine en suivant le fil conducteur.
        service.record(1L, ProgressAction.START_BATCH);
        service.record(1L, ProgressAction.COMPLETE_ORDER);
        service.record(1L, ProgressAction.PLAYER_TRADE);
        service.record(1L, ProgressAction.TASTE_AT_TAVERN);

        progress.setDailyDate(null); // demain
        String[] rotation = {"HARVEST_FIELD", "HARVEST_HIVE", "START_BATCH",
                "COMPLETE_ORDER", "PLAYER_TRADE", "TASTE_AT_TAVERN"};
        assertEquals(rotation[LocalDate.now(ZoneOffset.UTC).getDayOfYear() % rotation.length],
                service.visit(1L).dailyQuest().action());
    }

    @Test
    void specializationRequiresLevelTwoAndAppliesItsBusinessBonus() {
        assertThrows(IllegalStateException.class,
                () -> service.chooseSpecialization(1L, "CULTIVATEUR"));

        player.setLevel(2);
        ProgressionResponse response = service.chooseSpecialization(1L, "CULTIVATEUR");

        assertTrue(response.specializations().stream()
                .anyMatch(choice -> choice.code().equals("CULTIVATEUR") && choice.selected()));
        assertEquals(new BigDecimal("11.500"),
                service.harvestYield(1L, new BigDecimal("10.000")));
        assertThrows(IllegalStateException.class,
                () -> service.chooseSpecialization(1L, "BRASSEUR"));
    }

    @Test
    void seasonAccumulatesPointsAndPaysEachMilestoneOnce() {
        int initialCoins = player.getCoin();
        service.visit(1L);

        service.record(1L, ProgressAction.COMPLETE_ORDER);
        service.record(1L, ProgressAction.COMPLETE_ORDER);
        int afterFirstTier = player.getCoin();
        service.visit(1L);

        ProgressionResponse response = service.visit(1L);
        assertEquals(10, response.season().points());
        assertEquals(1, response.season().rewardTier());
        assertEquals(initialCoins + 100, afterFirstTier);
        assertEquals(afterFirstTier, player.getCoin());
    }

    @Test
    void themeIsPersistentAndReturnedAsSelected() {
        ProgressionResponse response = service.chooseTheme(1L, "hiver");
        assertTrue(response.themes().stream()
                .anyMatch(theme -> theme.code().equals("HIVER") && theme.selected()));
    }
}
