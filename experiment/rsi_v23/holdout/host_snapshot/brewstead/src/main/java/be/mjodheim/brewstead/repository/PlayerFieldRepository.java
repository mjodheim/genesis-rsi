package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.PlayerField;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PlayerFieldRepository extends JpaRepository<PlayerField, Long> {

    // Toutes les parcelles appartenant à un joueur
    List<PlayerField> findAllByPlayerId (Long playerId);
}
