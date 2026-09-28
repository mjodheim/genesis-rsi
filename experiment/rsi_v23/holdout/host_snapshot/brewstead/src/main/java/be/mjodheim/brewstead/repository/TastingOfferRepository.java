package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.TastingOffer;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface TastingOfferRepository extends JpaRepository<TastingOffer, Long> {

    List<TastingOffer> findAllByServingsGreaterThanOrderByOpenedAtDesc(int servings);

    Optional<TastingOffer> findFirstByBatchIdAndServingsGreaterThan(Long batchId, int servings);

    long countBySellerIdAndServingsGreaterThan(Long sellerId, int servings);
}
