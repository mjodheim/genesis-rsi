package be.mjodheim.brewstead.dto.progression;

import java.time.LocalDateTime;

public record AchievementResponse(
        String code,
        String title,
        String description,
        long progress,
        long target,
        int rewardCoins,
        int rewardExperience,
        boolean unlocked,
        LocalDateTime unlockedAt
) { }
