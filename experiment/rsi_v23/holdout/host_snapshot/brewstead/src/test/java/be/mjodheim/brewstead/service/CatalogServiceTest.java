package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.catalog.CropResponse;
import be.mjodheim.brewstead.dto.catalog.IngredientCatalogResponse;
import be.mjodheim.brewstead.entity.Crop;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.repository.CropRepository;
import be.mjodheim.brewstead.repository.IngredientRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;

import static be.mjodheim.brewstead.TestData.ingredient;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CatalogServiceTest {

    @Mock IngredientRepository ingredientRepository;
    @Mock CropRepository cropRepository;
    @InjectMocks CatalogService service;

    @Test
    void mapsIngredientsAndCropsToCatalogResponses() {
        Ingredient ingredient = ingredient(5, IngredientType.CEREAL);
        ingredient.setName("Orge");
        Crop crop = Crop.builder()
                .id(8L).name("Orge du Nord").ingredient(ingredient)
                .growDurationMinutes(15)
                .yieldQuantity(new BigDecimal("3.500"))
                .build();
        when(ingredientRepository.findAll()).thenReturn(List.of(ingredient));
        when(cropRepository.findAll()).thenReturn(List.of(crop));

        List<IngredientCatalogResponse> ingredients = service.findAllIngredients();
        List<CropResponse> crops = service.findAllCrops();

        assertEquals(1, ingredients.size());
        assertEquals(5L, ingredients.getFirst().id());
        assertEquals("Orge", ingredients.getFirst().name());
        assertEquals(1, crops.size());
        assertEquals(8L, crops.getFirst().id());
        assertEquals(5L, crops.getFirst().ingredientId());
        assertEquals(new BigDecimal("3.500"), crops.getFirst().yieldQuantity());
    }
}
