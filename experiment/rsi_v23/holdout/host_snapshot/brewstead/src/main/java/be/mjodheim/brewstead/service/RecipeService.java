package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.recipe.CreateRecipeRequest;
import be.mjodheim.brewstead.dto.recipe.RecipeIngredientRequest;
import be.mjodheim.brewstead.dto.recipe.RecipeResponse;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.RecipeIngredient;
import be.mjodheim.brewstead.mapper.RecipeMapper;
import be.mjodheim.brewstead.repository.IngredientRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.RecipeIngredientRepository;
import be.mjodheim.brewstead.repository.RecipeRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class RecipeService {

    private final RecipeRepository recipeRepository;
    private final RecipeIngredientRepository recipeIngredientRepository;
    private final IngredientRepository ingredientRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final RecipeMapper recipeMapper;
    private final RecipeAlchemyService alchemy;

    /** Garde-fous d'un laboratoire : on invente, on n'inonde pas la base. */
    private static final int NOM_MAX = 60;
    private static final int LIGNES_MAX = 8;
    private static final int RECETTES_MAX = 60;
    private static final BigDecimal VOLUME_MAX = BigDecimal.valueOf(200);
    private static final BigDecimal DOSE_MAX = BigDecimal.valueOf(500);
    private static final int MINUTES_MIN = 5;
    private static final int MINUTES_MAX = 10080;

    @Transactional
    public List<RecipeResponse> findAvailableRecipes(Long playerId) {
        getPlayer(playerId);
        List<Recipe> recipes = recipeRepository.findAvailableWithOwner(playerId);
        if (recipes.isEmpty()) {
            return List.of();
        }

        // Deux requêtes pour tout le grimoire, au lieu d'une par recette.
        Map<Long, List<RecipeIngredient>> lines = new HashMap<>();
        recipeIngredientRepository.findAllWithIngredientByRecipeIdIn(
                        recipes.stream().map(Recipe::getId).toList())
                .forEach(line -> lines.computeIfAbsent(line.getRecipe().getId(), id -> new ArrayList<>()).add(line));

        return recipes.stream()
                .map(recipe -> recipeMapper.toResponse(recipe, lines.getOrDefault(recipe.getId(), List.of())))
                .toList();
    }

    @Transactional
    public RecipeResponse findRecipe(Long playerId, Long recipeId) {
        Recipe recipe = getRecipe(recipeId);
        assertAccessible(recipe, playerId);
        return toResponse(recipe);
    }

    @Transactional
    public RecipeResponse createRecipe(CreateRecipeRequest request) {
        validateRequest(request);
        PlayerProfile owner = getPlayer(request.ownerId());
        String name = request.name().trim();

        if (recipeRepository.countByOwnerId(owner.getId()) >= RECETTES_MAX) {
            throw new IllegalStateException("Ton grimoire est plein : " + RECETTES_MAX + " recettes au maximum.");
        }
        if (recipeRepository.existsByOwnerIdAndNameIgnoreCase(owner.getId(), name)) {
            throw new IllegalStateException("Une recette porte déjà ce nom dans ton grimoire.");
        }

        // Le mélange est résolu avant l'enregistrement : c'est lui qui décide
        // de la rareté et de l'effet, pas le joueur.
        List<Ingredient> ingredients = new ArrayList<>();
        List<BigDecimal> doses = new ArrayList<>();
        for (RecipeIngredientRequest line : request.ingredients()) {
            ingredients.add(getIngredient(line.ingredientId()));
            doses.add(line.quantity());
        }

        RecipeAlchemyService.Resultat resultat = alchemy.analyser(request.drinkType(), ingredients, doses);
        int minutes = request.minutes();

        Recipe recipe = recipeRepository.save(
                Recipe.builder()
                        .owner(owner)
                        .name(name)
                        .drinkType(request.drinkType())
                        .baseVolume(request.baseVolume())
                        .fermentationDurationHours(Math.max(1, (minutes + 59) / 60))
                        .fermentationDurationMinutes(minutes)
                        .rarity(resultat.rarity())
                        .effectKind(resultat.effectKind())
                        .effectMagnitude(resultat.magnitude())
                        .effectDurationMinutes(resultat.durationMinutes())
                        .flavour(resultat.flavour())
                        .isPublic(false)
                        .build()
        );

        List<RecipeIngredient> lines = new ArrayList<>();
        for (int i = 0; i < ingredients.size(); i++) {
            lines.add(RecipeIngredient.builder()
                    .recipe(recipe)
                    .ingredient(ingredients.get(i))
                    .quantity(doses.get(i))
                    .build());
        }
        recipeIngredientRepository.saveAll(lines);

        return recipeMapper.toResponse(recipe, lines);
    }

    @Transactional
    public Recipe getAccessibleRecipeEntity(Long playerId, Long recipeId) {
        Recipe recipe = getRecipe(recipeId);
        assertAccessible(recipe, playerId);
        return recipe;
    }

    private RecipeResponse toResponse(Recipe recipe) {
        return recipeMapper.toResponse(
                recipe,
                recipeIngredientRepository.findAllByRecipeId(recipe.getId())
        );
    }

    private void validateRequest(CreateRecipeRequest request) {
        if (request.ownerId() == null) {
            throw new IllegalArgumentException("Recipe owner is required");
        }
        if (request.name() == null || request.name().isBlank()) {
            throw new IllegalArgumentException("Il faut donner un nom à ta recette.");
        }
        if (request.name().trim().length() > NOM_MAX) {
            throw new IllegalArgumentException("Le nom ne peut pas dépasser " + NOM_MAX + " caractères.");
        }
        if (request.drinkType() == null) {
            throw new IllegalArgumentException("Il faut choisir un type de breuvage.");
        }
        if (request.baseVolume() == null || request.baseVolume().compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Le volume doit être positif.");
        }
        if (request.baseVolume().compareTo(VOLUME_MAX) > 0) {
            throw new IllegalArgumentException("Une cuve ne dépasse pas " + VOLUME_MAX + " litres.");
        }
        int minutes = request.minutes();
        if (minutes < MINUTES_MIN || minutes > MINUTES_MAX) {
            throw new IllegalArgumentException("La fermentation tient entre "
                    + MINUTES_MIN + " minutes et " + (MINUTES_MAX / 1440) + " jours.");
        }
        if (request.ingredients() == null || request.ingredients().isEmpty()) {
            throw new IllegalArgumentException("Une recette contient au moins un ingrédient.");
        }
        if (request.ingredients().size() > LIGNES_MAX) {
            throw new IllegalArgumentException("Pas plus de " + LIGNES_MAX + " ingrédients dans une recette.");
        }

        Set<Long> ingredientIds = new HashSet<>();
        for (RecipeIngredientRequest line : request.ingredients()) {
            if (line.ingredientId() == null || line.quantity() == null
                    || line.quantity().compareTo(BigDecimal.ZERO) <= 0) {
                throw new IllegalArgumentException("Chaque dose doit être positive.");
            }
            if (line.quantity().compareTo(DOSE_MAX) > 0) {
                throw new IllegalArgumentException("Une dose ne dépasse pas " + DOSE_MAX + ".");
            }
            if (!ingredientIds.add(line.ingredientId())) {
                throw new IllegalArgumentException("Un ingrédient ne peut figurer qu'une fois dans une recette.");
            }
        }
    }

    private Ingredient getIngredient(Long ingredientId) {
        return ingredientRepository.findById(ingredientId)
                .orElseThrow(() -> new IllegalArgumentException("Ingrédient introuvable."));
    }

    private PlayerProfile getPlayer(Long playerId) {
        return playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Player not found"));
    }

    private Recipe getRecipe(Long recipeId) {
        return recipeRepository.findById(recipeId)
                .orElseThrow(() -> new IllegalArgumentException("Recipe not found"));
    }

    private void assertAccessible(Recipe recipe, Long playerId) {
        boolean ownedByPlayer = recipe.getOwner() != null && recipe.getOwner().getId().equals(playerId);
        if (!recipe.isPublic() && !ownedByPlayer) {
            throw new IllegalStateException("Recipe is not available to this player");
        }
    }
}
