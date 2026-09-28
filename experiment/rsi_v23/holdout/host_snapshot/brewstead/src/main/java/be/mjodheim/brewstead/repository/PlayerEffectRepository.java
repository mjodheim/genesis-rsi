package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.PlayerEffect;
import be.mjodheim.brewstead.enums.EffectKind;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

public interface PlayerEffectRepository extends JpaRepository<PlayerEffect, Long> {

    List<PlayerEffect> findAllByPlayerIdAndExpiresAtAfterOrderByExpiresAtAsc(Long playerId, LocalDateTime moment);

    Optional<PlayerEffect> findFirstByPlayerIdAndKindAndExpiresAtAfter(Long playerId, EffectKind kind, LocalDateTime moment);

    void deleteAllByExpiresAtBefore(LocalDateTime moment);
}
