package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.progression.*;
import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.*;
import be.mjodheim.brewstead.repository.*;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.*;
import java.time.temporal.ChronoUnit;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;
import java.util.function.ToLongFunction;

@Service
@RequiredArgsConstructor
public class ProgressionService {

    private static final int XP_PER_LEVEL = 1_000;
    private static final int DAILY_TARGET = 3;
    private static final int DAILY_COINS = 75;
    private static final int DAILY_XP = 100;
    private static final LocalDate SEASON_EPOCH = LocalDate.of(2026, 1, 1);
    private static final int SEASON_DAYS = 28;
    private static final List<Integer> SEASON_MILESTONES = List.of(10, 30, 75);
    private static final int[] SEASON_COINS = {100, 250, 600};
    private static final int[] SEASON_XP = {100, 300, 750};
    private static final long COMMUNITY_TARGET = 500;

    private final PlayerProgressRepository progressRepository;
    private final PlayerAchievementRepository achievementRepository;
    private final PlayerProfileRepository playerRepository;

    private record Achievement(String code, String title, String description,
                               ProgressAction action, long target, int coins, int xp,
                               ToLongFunction<PlayerProgress> counter) { }

    private static final List<Achievement> ACHIEVEMENTS = List.of(
            new Achievement("FIRST_HARVEST", "Première moisson", "Récolter une parcelle.", ProgressAction.HARVEST_FIELD, 1, 40, 50, PlayerProgress::getHarvestedFields),
            new Achievement("MASTER_FARMER", "Terres généreuses", "Récolter 25 parcelles.", ProgressAction.HARVEST_FIELD, 25, 250, 350, PlayerProgress::getHarvestedFields),
            new Achievement("HONEY_KEEPER", "Ami des abeilles", "Récolter 10 ruches.", ProgressAction.HARVEST_HIVE, 10, 150, 200, PlayerProgress::getHarvestedHives),
            new Achievement("FIRST_BREW", "Premier brassin", "Lancer son premier brassin.", ProgressAction.START_BATCH, 1, 60, 75, PlayerProgress::getStartedBatches),
            new Achievement("MASTER_BREWER", "Maître brasseur", "Lancer 25 brassins.", ProgressAction.START_BATCH, 25, 300, 500, PlayerProgress::getStartedBatches),
            new Achievement("TRUSTED_SUPPLIER", "Fournisseur du fjord", "Honorer 10 commandes.", ProgressAction.COMPLETE_ORDER, 10, 300, 400, PlayerProgress::getCompletedOrders),
            new Achievement("GOOD_NEIGHBOUR", "Bon voisin", "Servir 5 commandes de joueurs.", ProgressAction.PLAYER_TRADE, 5, 200, 250, PlayerProgress::getPlayerTrades),
            new Achievement("TAVERN_REGULAR", "Habitué de la taverne", "Goûter 10 productions voisines.", ProgressAction.TASTE_AT_TAVERN, 10, 150, 200, PlayerProgress::getTavernTastings)
    );

    @Transactional
    public ProgressionResponse visit(Long playerId) {
        PlayerProgress progress = getOrCreate(playerId);
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        if (!today.equals(progress.getLastVisitDate())) {
            progress.setVisitStreak(today.minusDays(1).equals(progress.getLastVisitDate())
                    ? progress.getVisitStreak() + 1 : 1);
            progress.setLastVisitDate(today);
        }
        prepareDaily(progress, today);
        prepareSeason(progress, today);
        unlockEligible(progress);
        return toResponse(progress);
    }

    @Transactional
    public void record(Long playerId, ProgressAction action) {
        PlayerProgress progress = getOrCreate(playerId);
        increment(progress, action);
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        prepareDaily(progress, today);
        prepareSeason(progress, today);
        if (progress.getDailyAction() == action && !progress.isDailyClaimed()) {
            progress.setDailyProgress(Math.min(DAILY_TARGET, progress.getDailyProgress() + 1));
            if (progress.getDailyProgress() >= DAILY_TARGET) {
                progress.setDailyClaimed(true);
                reward(progress.getPlayer(), DAILY_COINS, DAILY_XP);
            }
        }
        progress.setSeasonPoints(progress.getSeasonPoints() + seasonValue(action));
        rewardSeasonMilestones(progress);
        unlockEligible(progress);
    }

    @Transactional
    public ProgressionResponse chooseSpecialization(Long playerId, String raw) {
        PlayerProgress progress = getOrCreate(playerId);
        if (progress.getPlayer().getLevel() < 2) {
            throw new IllegalStateException("La spécialisation se débloque au niveau 2.");
        }
        Specialization choice = parseSpecialization(raw);
        if (progress.getSpecialization() != null && progress.getSpecialization() != choice) {
            throw new IllegalStateException("La spécialisation du domaine est définitive.");
        }
        progress.setSpecialization(choice);
        return visit(playerId);
    }

    @Transactional
    public ProgressionResponse chooseTheme(Long playerId, String raw) {
        PlayerProgress progress = getOrCreate(playerId);
        try {
            progress.setEstateTheme(EstateTheme.valueOf(raw.trim().toUpperCase(Locale.ROOT)));
        } catch (RuntimeException exception) {
            throw new IllegalArgumentException("Thème inconnu.");
        }
        return visit(playerId);
    }

    @Transactional
    public BigDecimal harvestYield(Long playerId, BigDecimal base) {
        if (getOrCreate(playerId).getSpecialization() != Specialization.CULTIVATEUR) return base;
        return base.multiply(new BigDecimal("1.15")).setScale(base.scale(), RoundingMode.HALF_UP);
    }

    @Transactional
    public int brewingQualityBonus(Long playerId) {
        return getOrCreate(playerId).getSpecialization() == Specialization.BRASSEUR ? 5 : 0;
    }

    @Transactional
    public int npcCoinReward(Long playerId, int base) {
        return getOrCreate(playerId).getSpecialization() == Specialization.MARCHAND
                ? Math.round(base * 1.10f) : base;
    }

    private PlayerProgress getOrCreate(Long playerId) {
        return progressRepository.findByPlayerId(playerId).orElseGet(() -> {
            PlayerProfile player = playerRepository.findById(playerId)
                    .orElseThrow(() -> new IllegalArgumentException("Player not found"));
            return progressRepository.save(PlayerProgress.builder().player(player).build());
        });
    }

    private static final ProgressAction[] DAILY_ROTATION = {
            ProgressAction.HARVEST_FIELD, ProgressAction.HARVEST_HIVE,
            ProgressAction.START_BATCH, ProgressAction.COMPLETE_ORDER,
            ProgressAction.PLAYER_TRADE, ProgressAction.TASTE_AT_TAVERN
    };

    private void prepareDaily(PlayerProgress progress, LocalDate today) {
        if (today.equals(progress.getDailyDate())) return;
        progress.setDailyDate(today);
        progress.setDailyAction(dailyAction(progress, today));
        progress.setDailyProgress(0);
        progress.setDailyClaimed(false);
    }

    /**
     * L'objectif du jour, pris dans ce que ce domaine sait déjà faire.
     *
     * <p>La rotation reste celle du calendrier — le jour de l'année donne le
     * point de départ, identique pour tout le monde — mais on avance jusqu'à
     * une tâche que le joueur peut réellement accomplir. Demander « Aide trois
     * domaines voisins » à quelqu'un qui n'a jamais rien brassé n'est pas un
     * objectif, c'est un mur : le fil conducteur lui dit de semer pendant que
     * le bandeau lui réclame l'impossible.
     */
    private ProgressAction dailyAction(PlayerProgress progress, LocalDate today) {
        int depart = Math.floorMod(today.getDayOfYear(), DAILY_ROTATION.length);
        for (int pas = 0; pas < DAILY_ROTATION.length; pas++) {
            ProgressAction candidate = DAILY_ROTATION[(depart + pas) % DAILY_ROTATION.length];
            if (alreadyLearned(progress, candidate)) return candidate;
        }
        return ProgressAction.HARVEST_FIELD;
    }

    /**
     * Les deux récoltes sont là dès le premier jour : un domaine neuf arrive
     * avec ses parcelles et ses ruches. Tout le reste s'ouvre le jour où le
     * joueur l'a fait une première fois de lui-même, en suivant le fil
     * conducteur — et rejoint alors la rotation.
     */
    private boolean alreadyLearned(PlayerProgress progress, ProgressAction action) {
        return switch (action) {
            case HARVEST_FIELD, HARVEST_HIVE -> true;
            case START_BATCH -> progress.getStartedBatches() > 0;
            case COMPLETE_ORDER -> progress.getCompletedOrders() > 0;
            case PLAYER_TRADE -> progress.getPlayerTrades() > 0;
            case TASTE_AT_TAVERN -> progress.getTavernTastings() > 0;
        };
    }

    private void prepareSeason(PlayerProgress progress, LocalDate today) {
        String key = seasonKey(today);
        if (key.equals(progress.getSeasonKey())) return;
        progress.setSeasonKey(key);
        progress.setSeasonPoints(0);
        progress.setSeasonRewardTier(0);
    }

    private String seasonKey(LocalDate date) {
        long cycle = Math.floorDiv(ChronoUnit.DAYS.between(SEASON_EPOCH, date), SEASON_DAYS);
        return "S" + cycle;
    }

    private LocalDate seasonEnds(LocalDate date) {
        long elapsed = ChronoUnit.DAYS.between(SEASON_EPOCH, date);
        long cycle = Math.floorDiv(elapsed, SEASON_DAYS);
        return SEASON_EPOCH.plusDays((cycle + 1) * SEASON_DAYS - 1);
    }

    private int seasonValue(ProgressAction action) {
        return switch (action) {
            case HARVEST_FIELD, HARVEST_HIVE -> 2;
            case START_BATCH -> 3;
            case COMPLETE_ORDER, PLAYER_TRADE -> 5;
            case TASTE_AT_TAVERN -> 1;
        };
    }

    private void rewardSeasonMilestones(PlayerProgress progress) {
        while (progress.getSeasonRewardTier() < SEASON_MILESTONES.size()
                && progress.getSeasonPoints() >= SEASON_MILESTONES.get(progress.getSeasonRewardTier())) {
            int tier = progress.getSeasonRewardTier();
            reward(progress.getPlayer(), SEASON_COINS[tier], SEASON_XP[tier]);
            progress.setSeasonRewardTier(tier + 1);
        }
    }

    private Specialization parseSpecialization(String raw) {
        try {
            return Specialization.valueOf(raw.trim().toUpperCase(Locale.ROOT));
        } catch (RuntimeException exception) {
            throw new IllegalArgumentException("Spécialisation inconnue.");
        }
    }

    private void increment(PlayerProgress p, ProgressAction action) {
        switch (action) {
            case HARVEST_FIELD -> p.setHarvestedFields(p.getHarvestedFields() + 1);
            case HARVEST_HIVE -> p.setHarvestedHives(p.getHarvestedHives() + 1);
            case START_BATCH -> p.setStartedBatches(p.getStartedBatches() + 1);
            case COMPLETE_ORDER -> p.setCompletedOrders(p.getCompletedOrders() + 1);
            case PLAYER_TRADE -> p.setPlayerTrades(p.getPlayerTrades() + 1);
            case TASTE_AT_TAVERN -> p.setTavernTastings(p.getTavernTastings() + 1);
        }
    }

    private void unlockEligible(PlayerProgress progress) {
        for (Achievement achievement : ACHIEVEMENTS) {
            if (achievement.counter().applyAsLong(progress) < achievement.target()
                    || achievementRepository.existsByPlayerIdAndCode(progress.getPlayer().getId(), achievement.code())) continue;
            achievementRepository.save(PlayerAchievement.builder()
                    .player(progress.getPlayer()).code(achievement.code()).unlockedAt(LocalDateTime.now()).build());
            reward(progress.getPlayer(), achievement.coins(), achievement.xp());
        }
    }

    private void reward(PlayerProfile player, int coins, int xp) {
        player.setCoin(player.getCoin() + coins);
        player.setExperience(player.getExperience() + xp);
        player.setLevel(Math.max(player.getLevel(), 1 + player.getExperience() / XP_PER_LEVEL));
    }

    private ProgressionResponse toResponse(PlayerProgress progress) {
        Map<String, LocalDateTime> unlocked = new HashMap<>();
        achievementRepository.findAllByPlayerId(progress.getPlayer().getId())
                .forEach(value -> unlocked.put(value.getCode(), value.getUnlockedAt()));
        List<AchievementResponse> achievements = ACHIEVEMENTS.stream().map(a -> new AchievementResponse(
                a.code(), a.title(), a.description(), a.counter().applyAsLong(progress), a.target(),
                a.coins(), a.xp(), unlocked.containsKey(a.code()), unlocked.get(a.code()))).toList();
        List<SpecializationResponse> specializations = Arrays.stream(Specialization.values())
                .map(value -> new SpecializationResponse(value.name(), value.getLabel(), value.getDescription(),
                        value == progress.getSpecialization())).toList();
        List<ThemeResponse> themes = Arrays.stream(EstateTheme.values())
                .map(value -> new ThemeResponse(value.name(), value.getLabel(), value == progress.getEstateTheme())).toList();
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        SeasonResponse season = new SeasonResponse(progress.getSeasonKey(), seasonName(today), seasonEnds(today),
                progress.getSeasonPoints(), progress.getSeasonRewardTier(), SEASON_MILESTONES,
                progressRepository.sumSeasonPoints(progress.getSeasonKey()), COMMUNITY_TARGET);
        return new ProgressionResponse(progress.getVisitStreak(), daily(progress), achievements,
                specializations, themes, season);
    }

    private String seasonName(LocalDate today) {
        String[] names = {"Saison des Semis", "Saison du Soleil", "Saison des Brumes", "Saison des Veillées"};
        long cycle = Math.floorDiv(ChronoUnit.DAYS.between(SEASON_EPOCH, today), SEASON_DAYS);
        return names[Math.floorMod((int) cycle, names.length)];
    }

    private DailyQuestResponse daily(PlayerProgress progress) {
        ProgressAction action = progress.getDailyAction();
        return new DailyQuestResponse(action.name(), dailyTitle(action), dailyPlace(action),
                progress.getDailyProgress(), DAILY_TARGET, DAILY_COINS, DAILY_XP, progress.isDailyClaimed());
    }

    private String dailyTitle(ProgressAction action) {
        return switch (action) {
            case HARVEST_FIELD -> "Récolter 3 parcelles";
            case HARVEST_HIVE -> "Récolter 3 ruches";
            case START_BATCH -> "Lancer 3 brassins";
            case COMPLETE_ORDER -> "Honorer 3 commandes";
            case PLAYER_TRADE -> "Aider 3 domaines voisins";
            case TASTE_AT_TAVERN -> "Goûter 3 breuvages voisins";
        };
    }

    private String dailyPlace(ProgressAction action) {
        return switch (action) {
            case HARVEST_FIELD -> "champs";
            case HARVEST_HIVE -> "rucher";
            case START_BATCH -> "brasserie";
            case COMPLETE_ORDER, PLAYER_TRADE -> "commandes";
            case TASTE_AT_TAVERN -> "taverne";
        };
    }
}
