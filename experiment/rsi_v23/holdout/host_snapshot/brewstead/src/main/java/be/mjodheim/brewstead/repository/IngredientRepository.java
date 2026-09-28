package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.enums.IngredientType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface IngredientRepository extends JpaRepository<Ingredient, Long> {

    Optional<Ingredient> findFirstByType(IngredientType type);

    Optional<Ingredient> findByNameIgnoreCase(String name);
}
