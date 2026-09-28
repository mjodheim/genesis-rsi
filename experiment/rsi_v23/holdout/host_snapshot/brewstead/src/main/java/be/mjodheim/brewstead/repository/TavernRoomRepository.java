package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.TavernRoom;
import be.mjodheim.brewstead.enums.TavernRoomType;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface TavernRoomRepository extends JpaRepository<TavernRoom, Long> {
    List<TavernRoom> findAllByTypeOrderByCreatedAtAsc(TavernRoomType type);
    Optional<TavernRoom> findByCodeIgnoreCase(String code);
    long countByType(TavernRoomType type);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select r from TavernRoom r where r.id = :id")
    Optional<TavernRoom> findForUpdateById(Long id);
}
