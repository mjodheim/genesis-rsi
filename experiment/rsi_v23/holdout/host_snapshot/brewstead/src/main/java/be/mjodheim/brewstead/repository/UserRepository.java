package be.mjodheim.brewstead.repository;

import be.mjodheim.brewstead.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {
    // Soit on trouve un User, soit il n'existe pas
    Optional<User> findByUsername(String username);
}
