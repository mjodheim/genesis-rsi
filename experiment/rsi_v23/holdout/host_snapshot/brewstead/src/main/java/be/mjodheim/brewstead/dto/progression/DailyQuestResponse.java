package be.mjodheim.brewstead.dto.progression;

public record DailyQuestResponse(
        String action,
        String title,
        String place,
        int progress,
        int target,
        int rewardCoins,
        int rewardExperience,
        boolean claimed
) { }
