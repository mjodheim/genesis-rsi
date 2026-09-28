package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.TavernMessage;
import org.springframework.data.domain.Limit;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.EntityGraph;

import java.time.LocalDateTime;
import java.util.List;

public interface TavernMessageRepository extends JpaRepository<TavernMessage, Long> {

    @EntityGraph(attributePaths = "author")
    List<TavernMessage> findByOrderByIdDesc(Limit limit);

    @EntityGraph(attributePaths = "author")
    List<TavernMessage> findByIdGreaterThanOrderByIdAsc(Long id, Limit limit);

    @EntityGraph(attributePaths = "author")
    List<TavernMessage> findByRoomIdOrderByIdDesc(Long roomId, Limit limit);

    @EntityGraph(attributePaths = "author")
    List<TavernMessage> findByRoomIdAndIdGreaterThanOrderByIdAsc(Long roomId, Long id, Limit limit);

    long countByRoomIdAndAuthorIdAndPostedAtAfter(Long roomId, Long authorId, LocalDateTime moment);

    long countByAuthorIdAndPostedAtAfter(Long authorId, LocalDateTime moment);
}
