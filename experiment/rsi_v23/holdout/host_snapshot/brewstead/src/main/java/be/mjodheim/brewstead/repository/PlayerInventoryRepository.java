package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerInventory;
import be.mjodheim.brewstead.entity.PlayerProfile;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PlayerInventoryRepository extends JpaRepository<PlayerInventory, Long> {

    List<PlayerInventory> findAllByPlayerId(Long playerId);

    Optional<PlayerInventory> findByPlayerAndIngredient(PlayerProfile player, Ingredient ingredient);
}
