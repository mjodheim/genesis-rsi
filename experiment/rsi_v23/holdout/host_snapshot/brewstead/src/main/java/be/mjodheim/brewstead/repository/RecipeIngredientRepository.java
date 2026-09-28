package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.RecipeIngredient;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface RecipeIngredientRepository extends JpaRepository<RecipeIngredient, Long> {

    List<RecipeIngredient> findAllByRecipeId(Long recipeId);

    /**
     * Les lignes de plusieurs recettes d'un coup, ingrédient compris.
     *
     * <p>Le grimoire en compte près de trois cents. Lues une par une, elles
     * coûtaient une requête par recette et une par ingrédient pas encore vu :
     * près de quatre cents allers-retours à chaque relecture du domaine,
     * toutes les quinze secondes et pour chaque joueur connecté.
     */
    @Query("select ri from RecipeIngredient ri join fetch ri.ingredient"
            + " where ri.recipe.id in :recipeIds order by ri.id")
    List<RecipeIngredient> findAllWithIngredientByRecipeIdIn(@Param("recipeIds") Collection<Long> recipeIds);
}
