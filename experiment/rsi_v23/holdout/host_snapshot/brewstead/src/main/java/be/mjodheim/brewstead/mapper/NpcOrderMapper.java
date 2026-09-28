package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.order.NpcOrderLineResponse;
import be.mjodheim.brewstead.dto.order.NpcOrderResponse;
import be.mjodheim.brewstead.entity.NpcOrder;
import be.mjodheim.brewstead.entity.NpcOrderLine;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

import java.util.List;

@Mapper(componentModel = "spring")
public interface NpcOrderMapper {

    @Mapping(source = "recipe.id", target = "recipeId")
    @Mapping(source = "recipe.name", target = "recipeName")
    NpcOrderLineResponse toLineResponse(NpcOrderLine line);

    default NpcOrderResponse toResponse(NpcOrder order, List<NpcOrderLine> lines) {
        return new NpcOrderResponse(
                order.getId(),
                order.getPlayer().getId(),
                order.getCustomerName(),
                order.getCreatedAt(),
                order.getExpiresAt(),
                order.getStatus(),
                order.getRewardCoins(),
                order.getRewardReputation(),
                lines.stream().map(this::toLineResponse).toList()
        );
    }
}
