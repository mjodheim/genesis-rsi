package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.NpcOrderLine;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface NpcOrderLineRepository extends JpaRepository<NpcOrderLine, Long> {

    List<NpcOrderLine> findAllByOrderId(Long orderId);
}
