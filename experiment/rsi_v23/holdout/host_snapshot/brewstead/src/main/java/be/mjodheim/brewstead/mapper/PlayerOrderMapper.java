package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.order.PlayerOrderLineResponse;
import be.mjodheim.brewstead.dto.order.PlayerOrderResponse;
import be.mjodheim.brewstead.entity.PlayerOrder;
import be.mjodheim.brewstead.entity.PlayerOrderLine;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

import java.util.List;

@Mapper(componentModel = "spring")
public interface PlayerOrderMapper {

    @Mapping(source = "ingredient.id", target = "ingredientId")
    @Mapping(source = "ingredient.name", target = "ingredientName")
    @Mapping(source = "ingredient.unit", target = "unit")
    PlayerOrderLineResponse toLineResponse(PlayerOrderLine line);

    default PlayerOrderResponse toResponse(PlayerOrder order, List<PlayerOrderLine> lines) {
        Long fulfillerId = order.getFulfilledBy() == null ? null : order.getFulfilledBy().getId();
        String fulfillerUsername = order.getFulfilledBy() == null
                ? (order.isFulfilledByNpc() ? "Marchand de passage" : null)
                : order.getFulfilledBy().getDisplayName();

        return new PlayerOrderResponse(
                order.getId(),
                order.getCreator().getId(),
                order.getCreator().getDisplayName(),
                fulfillerId,
                fulfillerUsername,
                order.getCreatedAt(),
                order.getExpiresAt(),
                order.getStatus(),
                order.getRewardCoins(),
                order.isFulfilledByNpc(),
                lines.stream().map(this::toLineResponse).toList()
        );
    }
}
