package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.catalog.CropResponse;
import be.mjodheim.brewstead.dto.catalog.IngredientCatalogResponse;
import be.mjodheim.brewstead.entity.Crop;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.repository.CropRepository;
import be.mjodheim.brewstead.repository.IngredientRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class CatalogService {

    private final IngredientRepository ingredientRepository;
    private final CropRepository cropRepository;

    @Transactional
    public List<IngredientCatalogResponse> findAllIngredients() {
        return ingredientRepository.findAll().stream()
                .map(this::toIngredientResponse)
                .toList();
    }

    @Transactional
    public List<CropResponse> findAllCrops() {
        return cropRepository.findAll().stream()
                .map(this::toCropResponse)
                .toList();
    }

    private IngredientCatalogResponse toIngredientResponse(Ingredient ingredient) {
        return new IngredientCatalogResponse(
                ingredient.getId(),
                ingredient.getName(),
                ingredient.getType(),
                ingredient.getUnit(),
                ingredient.getBaseValue()
        );
    }

    private CropResponse toCropResponse(Crop crop) {
        return new CropResponse(
                crop.getId(),
                crop.getName(),
                crop.getIngredient().getId(),
                crop.getIngredient().getName(),
                crop.getGrowDurationMinutes(),
                crop.getYieldQuantity()
        );
    }
}
