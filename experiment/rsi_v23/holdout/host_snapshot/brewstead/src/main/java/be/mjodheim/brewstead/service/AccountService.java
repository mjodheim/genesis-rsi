package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.account.ChangePasswordRequest;
import be.mjodheim.brewstead.dto.account.UpdateAccountRequest;
import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.User;
import be.mjodheim.brewstead.enums.Avatar;
import be.mjodheim.brewstead.mapper.PlayerMapper;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.UserRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.regex.Pattern;

/**
 * Espace compte : tout part de l'utilisateur connecté, jamais d'un identifiant
 * reçu du navigateur.
 */
@Service
@RequiredArgsConstructor
public class AccountService {

    private static final Pattern DISPLAY_NAME = Pattern.compile("[\\p{L}\\p{N} '\\-]{3,30}");

    private final UserRepository userRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final PlayerService playerService;
    private final PlayerMapper playerMapper;
    private final PasswordEncoder passwordEncoder;

    @Transactional
    public PlayerProfileResponse currentAccount(String username) {
        User user = requireUser(username);
        return playerProfileRepository.findByUserId(user.getId())
                .map(playerMapper::toResponse)
                .orElseGet(() -> playerService.initializePlayer(user.getId()));
    }

    /** Identifiant du domaine de la session en cours, créé au besoin. */
    @Transactional
    public Long currentPlayerId(String username) {
        User user = requireUser(username);
        return playerProfileRepository.findByUserId(user.getId())
                .map(PlayerProfile::getId)
                .orElseGet(() -> playerService.initializePlayer(user.getId()).id());
    }

    @Transactional
    public PlayerProfileResponse updateAccount(String username, UpdateAccountRequest request) {
        User user = requireUser(username);
        PlayerProfile profile = playerProfileRepository.findByUserId(user.getId())
                .orElseThrow(() -> new IllegalStateException("Aucun domaine pour ce compte."));

        profile.setDisplayName(cleanDisplayName(request.displayName()));
        profile.setAvatar(Avatar.fromNullable(request.avatar()));

        return playerMapper.toResponse(profile);
    }

    /**
     * Change le mot de passe après vérification de l'actuel. Le nouveau doit
     * différer de l'ancien : sinon on croit avoir tourné la clé sans l'avoir fait.
     */
    @Transactional
    public void changePassword(String username, ChangePasswordRequest request) {
        User user = requireUser(username);

        if (!passwordEncoder.matches(request.currentPassword(), user.getPassword())) {
            throw new IllegalArgumentException("Mot de passe actuel incorrect.");
        }
        if (!request.newPassword().equals(request.confirmation())) {
            throw new IllegalArgumentException("Les deux mots de passe ne correspondent pas.");
        }
        if (passwordEncoder.matches(request.newPassword(), user.getPassword())) {
            throw new IllegalArgumentException("Le nouveau mot de passe est identique à l'ancien.");
        }

        user.setPassword(passwordEncoder.encode(request.newPassword()));
        userRepository.save(user);
    }

    /** Un nom vide remet simplement l'identifiant de connexion en vitrine. */
    private String cleanDisplayName(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String trimmed = value.trim().replaceAll("\\s{2,}", " ");
        if (!DISPLAY_NAME.matcher(trimmed).matches()) {
            throw new IllegalArgumentException(
                    "Le nom affiché fait 3 à 30 caractères : lettres, chiffres, espace, apostrophe ou tiret.");
        }
        return trimmed;
    }

    private User requireUser(String username) {
        return userRepository.findByUsername(username)
                .orElseThrow(() -> new IllegalStateException("Compte introuvable."));
    }
}
