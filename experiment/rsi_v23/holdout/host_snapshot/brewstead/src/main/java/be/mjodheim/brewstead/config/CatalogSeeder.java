package be.mjodheim.brewstead.config;

import be.mjodheim.brewstead.entity.Crop;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.RecipeIngredient;
import be.mjodheim.brewstead.enums.DrinkType;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.Rarity;
import be.mjodheim.brewstead.enums.Unit;
import be.mjodheim.brewstead.repository.CropRepository;
import be.mjodheim.brewstead.repository.IngredientRepository;
import be.mjodheim.brewstead.repository.RecipeIngredientRepository;
import be.mjodheim.brewstead.repository.RecipeRepository;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Charge le garde-manger et le grimoire depuis les fichiers de données.
 * Idempotent : n'ajoute que ce qui manque, pour qu'enrichir le catalogue
 * revienne à éditer un JSON et redéployer.
 */
@Slf4j
@Component
@Order(1)
@RequiredArgsConstructor
public class CatalogSeeder implements CommandLineRunner {

    private final IngredientRepository ingredientRepository;
    private final CropRepository cropRepository;
    private final RecipeRepository recipeRepository;
    private final RecipeIngredientRepository recipeIngredientRepository;
    private final ObjectMapper objectMapper;

    @Override
    public void run(String... args) throws Exception {
        int ingredients = seedIngredients();
        int crops = seedCrops();
        int recipes = seedRecipes();
        log.info("Catalogue Brewstead : +{} ingrédients, +{} cultures, +{} recettes",
                ingredients, crops, recipes);
    }

    private List<Map<String, Object>> read(String file) throws Exception {
        try (InputStream in = new ClassPathResource("data/" + file).getInputStream()) {
            return objectMapper.readValue(in, new TypeReference<List<Map<String, Object>>>() {});
        }
    }

    private int seedIngredients() throws Exception {
        int added = 0;
        for (Map<String, Object> row : read("ingredients.json")) {
            String name = text(row, "name");
            if (ingredientRepository.findByNameIgnoreCase(name).isPresent()) {
                continue;
            }
            ingredientRepository.save(Ingredient.builder()
                    .name(name)
                    .type(IngredientType.valueOf(text(row, "type")))
                    .unit(Unit.valueOf(text(row, "unit")))
                    .baseValue(decimal(row, "baseValue"))
                    .build());
            added++;
        }
        return added;
    }

    private int seedCrops() throws Exception {
        int added = 0;
        for (Map<String, Object> row : read("crops.json")) {
            String name = text(row, "name");
            if (cropRepository.findByNameIgnoreCase(name).isPresent()) {
                continue;
            }
            Ingredient ingredient = ingredientRepository.findByNameIgnoreCase(text(row, "ingredient"))
                    .orElse(null);
            if (ingredient == null) {
                log.warn("Culture ignorée, ingrédient inconnu : {}", text(row, "ingredient"));
                continue;
            }
            cropRepository.save(Crop.builder()
                    .name(name)
                    .ingredient(ingredient)
                    .growDurationMinutes(number(row, "growDurationMinutes"))
                    .yieldQuantity(decimal(row, "yieldQuantity"))
                    .build());
            added++;
        }
        return added;
    }

    @SuppressWarnings("unchecked")
    private int seedRecipes() throws Exception {
        int added = 0;
        for (Map<String, Object> row : read("recipes.json")) {
            String name = text(row, "name");
            if (recipeRepository.findFirstByNameIgnoreCaseAndOwnerIsNull(name).isPresent()) {
                continue;
            }

            List<Map<String, Object>> lines = (List<Map<String, Object>>) row.get("ingredients");
            List<RecipeIngredient> resolved = new ArrayList<>();
            boolean complete = true;

            Recipe recipe = Recipe.builder()
                    .name(name)
                    .drinkType(DrinkType.valueOf(text(row, "drinkType")))
                    .baseVolume(decimal(row, "baseVolume"))
                    .fermentationDurationHours(Math.max(1, number(row, "fermentationDurationMinutes") / 60))
                    .fermentationDurationMinutes(number(row, "fermentationDurationMinutes"))
                    .isPublic(true)
                    .effectKind(EffectKind.valueOf(text(row, "effectKind")))
                    .effectMagnitude(number(row, "effectMagnitude"))
                    .effectDurationMinutes(number(row, "effectDurationMinutes"))
                    .rarity(Rarity.valueOf(text(row, "rarity")))
                    .flavour(text(row, "flavour"))
                    .build();

            for (Map<String, Object> line : lines) {
                Ingredient ingredient = ingredientRepository.findByNameIgnoreCase(text(line, "name")).orElse(null);
                if (ingredient == null) {
                    log.warn("Recette « {} » ignorée : ingrédient inconnu « {} »", name, text(line, "name"));
                    complete = false;
                    break;
                }
                resolved.add(RecipeIngredient.builder()
                        .recipe(recipe)
                        .ingredient(ingredient)
                        .quantity(decimal(line, "quantity"))
                        .build());
            }

            if (!complete) {
                continue;
            }

            recipeRepository.save(recipe);
            recipeIngredientRepository.saveAll(resolved);
            added++;
        }
        return added;
    }

    private String text(Map<String, Object> row, String key) {
        Object value = row.get(key);
        return value == null ? null : String.valueOf(value);
    }

    private int number(Map<String, Object> row, String key) {
        Object value = row.get(key);
        return value == null ? 0 : ((Number) value).intValue();
    }

    private BigDecimal decimal(Map<String, Object> row, String key) {
        Object value = row.get(key);
        return value == null ? BigDecimal.ZERO : new BigDecimal(String.valueOf(value));
    }
}
