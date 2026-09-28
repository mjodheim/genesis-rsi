package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.Batch;
import be.mjodheim.brewstead.enums.BatchStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface BatchRepository extends JpaRepository<Batch, Long> {

    List<Batch> findAllByPlayerIdOrderByStartedAtDesc(Long playerId);

    List<Batch> findAllByPlayerIdAndRecipeIdAndStatusAndQualityGreaterThanEqualOrderByReadyAtAsc(
            Long playerId,
            Long recipeId,
            BatchStatus status,
            Integer minQuality
    );
}
