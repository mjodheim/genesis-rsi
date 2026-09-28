package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.PlayerAchievement;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PlayerAchievementRepository extends JpaRepository<PlayerAchievement, Long> {
    List<PlayerAchievement> findAllByPlayerId(Long playerId);
    boolean existsByPlayerIdAndCode(Long playerId, String code);
}
