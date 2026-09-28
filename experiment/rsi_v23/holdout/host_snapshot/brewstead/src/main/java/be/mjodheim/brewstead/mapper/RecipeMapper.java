package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.recipe.RecipeIngredientResponse;
import be.mjodheim.brewstead.dto.recipe.RecipeResponse;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.RecipeIngredient;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

import java.util.List;

@Mapper(componentModel = "spring")
public interface RecipeMapper {

    @Mapping(source = "ingredient.id", target = "ingredientId")
    @Mapping(source = "ingredient.name", target = "ingredientName")
    @Mapping(source = "ingredient.unit", target = "unit")
    RecipeIngredientResponse toIngredientResponse(RecipeIngredient recipeIngredient);

    default RecipeResponse toResponse(Recipe recipe, List<RecipeIngredient> ingredientLines) {
        Long ownerId = recipe.getOwner() == null ? null : recipe.getOwner().getId();
        String ownerUsername = recipe.getOwner() == null ? null : recipe.getOwner().getUser().getUsername();
        List<RecipeIngredientResponse> ingredients = ingredientLines.stream()
                .map(this::toIngredientResponse)
                .toList();

        return new RecipeResponse(
                recipe.getId(),
                ownerId,
                ownerUsername,
                recipe.getName(),
                recipe.getDrinkType(),
                recipe.getBaseVolume(),
                recipe.getFermentationDurationHours(),
                recipe.getFermentationMinutes(),
                recipe.getRarity(),
                recipe.getEffectKind(),
                recipe.getEffectKind().getLabel(),
                recipe.getEffectMagnitude(),
                recipe.getEffectDurationMinutes(),
                recipe.getFlavour(),
                recipe.isPublic(),
                ingredients
        );
    }
}
