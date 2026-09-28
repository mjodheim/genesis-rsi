package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.effect.PlayerEffectResponse;
import be.mjodheim.brewstead.entity.PlayerEffect;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.repository.PlayerEffectRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Les effets temporaires d'une dégustation. Ils ne réécrivent jamais le passé :
 * une durée déjà lancée reste ce qu'elle est, l'effet ne joue que sur ce que le
 * joueur démarre pendant qu'il est actif.
 */
@Service
@RequiredArgsConstructor
public class EffectService {

    /** Un effet ne peut jamais diviser ni multiplier une durée par plus de deux. */
    private static final int MAX_MAGNITUDE = 50;

    private final PlayerEffectRepository playerEffectRepository;
    private final PlayerProfileRepository playerProfileRepository;

    @Transactional
    public List<PlayerEffectResponse> activeEffects(Long playerId) {
        return playerEffectRepository
                .findAllByPlayerIdAndExpiresAtAfterOrderByExpiresAtAsc(playerId, LocalDateTime.now())
                .stream()
                .map(this::toResponse)
                .toList();
    }

    /** Applique l'effet d'une recette. Reboire prolonge au lieu d'empiler. */
    @Transactional
    public PlayerEffectResponse grant(Long playerId, Recipe recipe) {
        EffectKind kind = recipe.getEffectKind();
        int duration = recipe.getEffectDurationMinutes();

        if (kind == EffectKind.AUCUN || duration <= 0) {
            return null;
        }

        PlayerProfile player = playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Joueur introuvable."));

        LocalDateTime now = LocalDateTime.now();
        int magnitude = Math.min(MAX_MAGNITUDE, Math.max(0, recipe.getEffectMagnitude()));

        PlayerEffect effect = playerEffectRepository
                .findFirstByPlayerIdAndKindAndExpiresAtAfter(playerId, kind, now)
                .orElseGet(() -> PlayerEffect.builder()
                        .player(player)
                        .kind(kind)
                        .startedAt(now)
                        .expiresAt(now)
                        .build());

        effect.setMagnitude(Math.max(effect.getMagnitude(), magnitude));
        effect.setExpiresAt(effect.getExpiresAt().isAfter(now)
                ? effect.getExpiresAt().plusMinutes(duration)
                : now.plusMinutes(duration));
        effect.setSource(recipe.getName());

        return toResponse(playerEffectRepository.save(effect));
    }

    /** Ampleur en cours pour un effet donné, 0 s'il n'est pas actif. */
    @Transactional
    public int magnitudeOf(Long playerId, EffectKind kind) {
        return playerEffectRepository
                .findFirstByPlayerIdAndKindAndExpiresAtAfter(playerId, kind, LocalDateTime.now())
                .map(PlayerEffect::getMagnitude)
                .orElse(0);
    }

    /**
     * Facteur appliqué à une durée : l'effet d'entrain la raccourcit, la
     * somnolence l'allonge. Jamais en dessous de la moitié ni au-delà du double.
     */
    @Transactional
    public double durationFactor(Long playerId, EffectKind hasteKind) {
        double haste = magnitudeOf(playerId, hasteKind) / 100.0;
        double sleep = magnitudeOf(playerId, EffectKind.SOMMEIL_DE_L_OURS) / 100.0;
        return Math.max(0.5, Math.min(2.0, (1.0 - haste) * (1.0 + sleep)));
    }

    /** Bonus de qualité, malus compris. */
    @Transactional
    public int qualityShift(Long playerId) {
        return magnitudeOf(playerId, EffectKind.INSPIRATION) / 2
                - magnitudeOf(playerId, EffectKind.MAIN_LOURDE) / 2;
    }

    @Transactional
    public int boostCoins(Long playerId, int coins) {
        return coins + coins * magnitudeOf(playerId, EffectKind.BOURSE_PERCEE) / 100;
    }

    @Transactional
    public int boostReputation(Long playerId, int reputation) {
        return reputation + reputation * magnitudeOf(playerId, EffectKind.LANGUE_DOREE) / 100;
    }

    private PlayerEffectResponse toResponse(PlayerEffect effect) {
        EffectKind kind = effect.getKind();
        return new PlayerEffectResponse(
                effect.getId(),
                kind,
                kind.getLabel(),
                effect.getMagnitude(),
                kind.isBeneficial(),
                kind.isCosmetic(),
                effect.getStartedAt(),
                effect.getExpiresAt(),
                effect.getSource()
        );
    }
}
