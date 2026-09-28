package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.entity.PlayerProfile;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring")
public interface PlayerMapper {

    @Mapping(source = "user.username", target = "username")
    @Mapping(source = "coin", target = "coins")
    PlayerProfileResponse toResponse(PlayerProfile player);
}
