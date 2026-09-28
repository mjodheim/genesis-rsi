package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.account.RegisterForm;
import be.mjodheim.brewstead.entity.User;
import be.mjodheim.brewstead.enums.UserRole;
import be.mjodheim.brewstead.repository.UserRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

/**
 * Création d'un compte joueur : l'utilisateur d'abord, puis le domaine de départ.
 */
@Service
@RequiredArgsConstructor
public class RegistrationService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final PlayerService playerService;

    @Transactional
    public User register(RegisterForm request) {
        String username = request.getUsername() == null ? "" : request.getUsername().trim();

        if (!request.getPassword().equals(request.getConfirmation())) {
            throw new IllegalArgumentException("Les deux mots de passe ne correspondent pas.");
        }
        if (userRepository.findByUsername(username).isPresent()) {
            throw new IllegalArgumentException("Ce nom de brasseur est déjà pris.");
        }

        User user = userRepository.save(
                User.builder()
                        .username(username)
                        .password(passwordEncoder.encode(request.getPassword()))
                        .role(UserRole.PLAYER)
                        .build()
        );

        // champs, ruches et réserves de départ
        playerService.initializePlayer(user.getId());

        return user;
    }
}
