package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.apiary.BeehiveResponse;
import be.mjodheim.brewstead.entity.Beehive;
import org.mapstruct.Mapper;

import java.util.List;

@Mapper(componentModel = "spring")
public interface ApiaryMapper {

    BeehiveResponse toResponse(Beehive beehive);

    List<BeehiveResponse> toResponseList(List<Beehive> beehives);
}
