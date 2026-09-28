package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.PlayerProgress;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface PlayerProgressRepository extends JpaRepository<PlayerProgress, Long> {
    Optional<PlayerProgress> findByPlayerId(Long playerId);

    @Query("select coalesce(sum(p.seasonPoints), 0) from PlayerProgress p where p.seasonKey = :seasonKey")
    long sumSeasonPoints(@Param("seasonKey") String seasonKey);
}
