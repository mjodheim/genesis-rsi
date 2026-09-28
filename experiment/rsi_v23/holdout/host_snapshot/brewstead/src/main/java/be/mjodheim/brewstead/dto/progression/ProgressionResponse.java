package be.mjodheim.brewstead.dto.progression;

import java.util.List;

public record ProgressionResponse(
        int visitStreak,
        DailyQuestResponse dailyQuest,
        List<AchievementResponse> achievements,
        List<SpecializationResponse> specializations,
        List<ThemeResponse> themes,
        SeasonResponse season
) { }
