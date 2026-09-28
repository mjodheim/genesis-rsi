package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.NpcOrder;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import jakarta.persistence.LockModeType;

import java.util.List;
import java.util.Optional;

public interface NpcOrderRepository extends JpaRepository<NpcOrder, Long> {

    List<NpcOrder> findAllByPlayerIdOrderByCreatedAtDesc(Long playerId);

    long countByPlayerId(Long playerId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select o from NpcOrder o where o.id = :id")
    Optional<NpcOrder> findForUpdateById(Long id);
}
