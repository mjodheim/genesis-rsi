package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.brew.BatchResponse;
import be.mjodheim.brewstead.entity.Batch;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

import java.util.List;

@Mapper(componentModel = "spring")
public interface BrewMapper {

    @Mapping(source = "recipe.id", target = "recipeId")
    @Mapping(source = "recipe.name", target = "recipeName")
    BatchResponse toResponse(Batch batch);

    List<BatchResponse> toResponseList(List<Batch> batches);
}
