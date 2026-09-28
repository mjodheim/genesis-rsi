package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.Recipe;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface RecipeRepository extends JpaRepository<Recipe, Long> {

    List<Recipe> findAllByIsPublicTrueOrOwnerId(Long ownerId);

    /** Le même grimoire, auteur et compte chargés avec : le nom de l'auteur est affiché. */
    @Query("select r from Recipe r left join fetch r.owner o left join fetch o.user"
            + " where r.isPublic = true or o.id = :ownerId order by r.id")
    List<Recipe> findAvailableWithOwner(@Param("ownerId") Long ownerId);

    List<Recipe> findAllByIsPublicTrue();

    Optional<Recipe> findFirstByNameIgnoreCaseAndOwnerIsNull(String name);

    long countByOwnerId(Long ownerId);

    boolean existsByOwnerIdAndNameIgnoreCase(Long ownerId, String name);
}
