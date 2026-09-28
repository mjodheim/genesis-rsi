package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.brew.TastingResponse;
import be.mjodheim.brewstead.dto.effect.PlayerEffectResponse;
import be.mjodheim.brewstead.dto.tavern.OpenOfferRequest;
import be.mjodheim.brewstead.dto.tavern.TastingOfferResponse;
import be.mjodheim.brewstead.entity.Batch;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.TastingOffer;
import be.mjodheim.brewstead.enums.BatchStatus;
import be.mjodheim.brewstead.enums.ProgressAction;
import be.mjodheim.brewstead.exception.InsufficientCoinsException;
import be.mjodheim.brewstead.repository.BatchRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.TastingOfferRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Le comptoir : on y propose son fût au verre. Le prix libre permet de vendre
 * comme de faire goûter pour rien, ce qui est souvent le meilleur placement.
 */
@Service
@RequiredArgsConstructor
public class TastingCounterService {

    /** Un service, c'est un demi-litre. */
    private static final BigDecimal SERVING = new BigDecimal("0.50");
    private static final int MAX_OPEN_OFFERS = 5;

    private final TastingOfferRepository offerRepository;
    private final BatchRepository batchRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final PlayerService playerService;
    private final EffectService effectService;
    private final ProgressionService progressionService;

    @Transactional
    public List<TastingOfferResponse> counter(Long viewerId) {
        return offerRepository.findAllByServingsGreaterThanOrderByOpenedAtDesc(0).stream()
                .map(offer -> toResponse(offer, viewerId))
                .toList();
    }

    @Transactional
    public TastingOfferResponse open(Long playerId, OpenOfferRequest request) {
        Batch batch = batchRepository.findById(request.batchId())
                .orElseThrow(() -> new IllegalArgumentException("Brassin introuvable."));
        if (!batch.getPlayer().getId().equals(playerId)) {
            throw new AccessDeniedException("Ce brassin n'est pas le tien.");
        }
        if (batch.getStatus() != BatchStatus.READY) {
            throw new IllegalStateException("Ce brassin n'est pas encore prêt.");
        }
        if (offerRepository.findFirstByBatchIdAndServingsGreaterThan(batch.getId(), 0).isPresent()) {
            throw new IllegalStateException("Ce fût est déjà au comptoir.");
        }
        if (offerRepository.countBySellerIdAndServingsGreaterThan(playerId, 0) >= MAX_OPEN_OFFERS) {
            throw new IllegalStateException("Ton comptoir est déjà bien chargé.");
        }

        BigDecimal needed = SERVING.multiply(BigDecimal.valueOf(request.servings()));
        if (batch.getVolume().compareTo(needed) < 0) {
            throw new IllegalStateException("Il n'y a pas assez dans ce fût pour autant de services.");
        }

        batch.setVolume(batch.getVolume().subtract(needed));
        if (batch.getVolume().compareTo(BigDecimal.ZERO) <= 0) {
            batch.setStatus(BatchStatus.SOLD_OUT);
        }

        TastingOffer offer = offerRepository.save(
                TastingOffer.builder()
                        .seller(batch.getPlayer())
                        .batch(batch)
                        .servings(request.servings())
                        .price(request.price())
                        .note(request.note())
                        .openedAt(LocalDateTime.now())
                        .build());

        return toResponse(offer, playerId);
    }

    /** Se servir au comptoir : on paie, on boit, on subit. */
    @Transactional
    public TastingResponse serve(Long playerId, Long offerId) {
        TastingOffer offer = offerRepository.findById(offerId)
                .orElseThrow(() -> new IllegalArgumentException("Offre introuvable."));
        if (offer.getServings() <= 0) {
            throw new IllegalStateException("Le fût est vide.");
        }
        if (offer.getSeller().getId().equals(playerId)) {
            throw new IllegalStateException("Boire sa propre production au comptoir, c'est tricher un peu.");
        }

        PlayerProfile drinker = playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Joueur introuvable."));

        if (offer.getPrice() > 0) {
            if (drinker.getCoin() < offer.getPrice()) {
                throw new InsufficientCoinsException("Pas assez de pièces pour ce verre.");
            }
            playerService.spendCoins(playerId, offer.getPrice());
            playerService.reward(offer.getSeller().getId(), offer.getPrice(), 1, 0);
        } else {
            // Offrir sa tournée ne rapporte rien, sauf ce qui compte : la réputation.
            playerService.reward(offer.getSeller().getId(), 0, 2, 0);
        }

        offer.setServings(offer.getServings() - 1);

        Recipe recipe = offer.getBatch().getRecipe();
        PlayerEffectResponse effect = effectService.grant(playerId, recipe);
        progressionService.record(playerId, ProgressAction.TASTE_AT_TAVERN);
        return new TastingResponse(recipe.getName(), recipe.getFlavour(), effect);
    }

    private TastingOfferResponse toResponse(TastingOffer offer, Long viewerId) {
        Recipe recipe = offer.getBatch().getRecipe();
        return new TastingOfferResponse(
                offer.getId(),
                offer.getSeller().getId(),
                offer.getSeller().getDisplayName(),
                recipe.getName(),
                recipe.getRarity(),
                offer.getBatch().getQuality(),
                recipe.getEffectKind(),
                recipe.getEffectKind().getLabel(),
                recipe.getFlavour(),
                offer.getServings(),
                offer.getPrice(),
                offer.getNote(),
                offer.getSeller().getId().equals(viewerId),
                offer.getOpenedAt()
        );
    }
}
