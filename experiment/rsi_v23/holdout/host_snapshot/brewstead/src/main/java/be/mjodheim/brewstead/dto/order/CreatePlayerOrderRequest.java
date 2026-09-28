package be.mjodheim.brewstead.dto.order;

import java.util.List;

public record CreatePlayerOrderRequest(
        Long creatorId,
        int rewardCoins,
        int expiresInMinutes,
        List<PlayerOrderLineRequest> lines
) {
}
