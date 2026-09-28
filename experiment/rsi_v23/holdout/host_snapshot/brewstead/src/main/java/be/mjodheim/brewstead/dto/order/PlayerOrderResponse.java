package be.mjodheim.brewstead.dto.order;

import be.mjodheim.brewstead.enums.OrderStatus;

import java.time.LocalDateTime;
import java.util.List;

public record PlayerOrderResponse(
        Long id,
        Long creatorId,
        String creatorUsername,
        Long fulfillerId,
        String fulfillerUsername,
        LocalDateTime createdAt,
        LocalDateTime expiresAt,
        OrderStatus status,
        int rewardCoins,
        boolean fulfilledByNpc,
        List<PlayerOrderLineResponse> lines
) {
}
