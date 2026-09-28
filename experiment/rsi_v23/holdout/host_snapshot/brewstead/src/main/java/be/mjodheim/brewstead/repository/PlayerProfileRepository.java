package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.PlayerProfile;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import jakarta.persistence.LockModeType;

import java.util.List;
import java.util.Optional;

public interface PlayerProfileRepository extends JpaRepository<PlayerProfile, Long> {

    Optional<PlayerProfile> findByUserId(Long userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from PlayerProfile p where p.id = :id")
    Optional<PlayerProfile> findForUpdateById(Long id);

    List<PlayerProfile> findTop10ByOrderByReputationDescLevelDesc();
}
