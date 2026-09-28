package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.PlayerOrder;
import be.mjodheim.brewstead.enums.OrderStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PlayerOrderRepository extends JpaRepository<PlayerOrder, Long> {

    List<PlayerOrder> findAllByCreatorIdOrderByCreatedAtDesc(Long creatorId);

    List<PlayerOrder> findAllByStatusOrderByCreatedAtDesc(OrderStatus status);

    long countByStatus(OrderStatus status);
}
