package be.mjodheim.brewstead.dto.order;

import be.mjodheim.brewstead.enums.OrderStatus;

import java.time.LocalDateTime;
import java.util.List;

public record NpcOrderResponse(
        Long id,
        Long playerId,
        String customerName,
        LocalDateTime createdAt,
        LocalDateTime expiresAt,
        OrderStatus status,
        int rewardCoins,
        int rewardReputation,
        List<NpcOrderLineResponse> lines
) {
}
