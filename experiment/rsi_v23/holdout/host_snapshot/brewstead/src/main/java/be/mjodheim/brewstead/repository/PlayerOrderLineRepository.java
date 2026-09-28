package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.PlayerOrderLine;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PlayerOrderLineRepository extends JpaRepository<PlayerOrderLine, Long> {

    List<PlayerOrderLine> findAllByOrderId(Long orderId);
}
