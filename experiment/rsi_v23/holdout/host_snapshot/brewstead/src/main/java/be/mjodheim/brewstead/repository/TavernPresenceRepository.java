package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.TavernPresence;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

public interface TavernPresenceRepository extends JpaRepository<TavernPresence, Long> {
    @EntityGraph(attributePaths = {"room", "player", "player.user"})
    Optional<TavernPresence> findByPlayerId(Long playerId);

    @EntityGraph(attributePaths = {"player", "player.user", "room"})
    List<TavernPresence> findAllByRoomIdOrderByJoinedAtAsc(Long roomId);

    long countByRoomId(Long roomId);
    Optional<TavernPresence> findByRoomIdAndSeatKey(Long roomId, String seatKey);
    long deleteByPlayerId(Long playerId);
    long deleteByLastSeenAtBefore(LocalDateTime cutoff);
}
