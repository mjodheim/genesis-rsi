package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.Beehive;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface BeehiveRepository extends JpaRepository<Beehive, Long> {

    List<Beehive> findAllByPlayerId(Long playerId);
}
