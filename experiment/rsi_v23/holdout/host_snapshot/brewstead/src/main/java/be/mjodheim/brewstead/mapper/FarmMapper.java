package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.farm.PlayerFieldResponse;
import be.mjodheim.brewstead.entity.PlayerField;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

import java.util.List;

@Mapper (componentModel = "spring")
public interface FarmMapper {

    @Mapping(
            source = "crop.name",
            target = "cropName"
    )
    PlayerFieldResponse toResponse(PlayerField playerField);

    List<PlayerFieldResponse> toResponseList(List<PlayerField> playerFields);
}
