package be.mjodheim.brewstead.dto.progression;

import java.time.LocalDate;
import java.util.List;

public record SeasonResponse(
        String key,
        String name,
        LocalDate endsOn,
        int points,
        int rewardTier,
        List<Integer> milestones,
        long communityPoints,
        long communityTarget
) { }
