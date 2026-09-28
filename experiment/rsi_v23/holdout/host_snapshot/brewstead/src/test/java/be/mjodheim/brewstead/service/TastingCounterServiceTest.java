package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.brew.TastingResponse;
import be.mjodheim.brewstead.dto.tavern.OpenOfferRequest;
import be.mjodheim.brewstead.dto.tavern.TastingOfferResponse;
import be.mjodheim.brewstead.entity.Batch;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.TastingOffer;
import be.mjodheim.brewstead.enums.BatchStatus;
import be.mjodheim.brewstead.exception.InsufficientCoinsException;
import be.mjodheim.brewstead.repository.BatchRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.TastingOfferRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.access.AccessDeniedException;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.batch;
import static be.mjodheim.brewstead.TestData.player;
import static be.mjodheim.brewstead.TestData.recipe;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TastingCounterServiceTest {

    @Mock TastingOfferRepository offerRepository;
    @Mock BatchRepository batchRepository;
    @Mock PlayerProfileRepository playerRepository;
    @Mock PlayerService playerService;
    @Mock EffectService effectService;
    @Mock ProgressionService progressionService;
    @InjectMocks TastingCounterService service;

    @Test
    void counterMarksOwnOffers() {
        PlayerProfile seller = player(1);
        Recipe recipe = recipe(3);
        Batch batch = readyBatch(4, seller, recipe, "5.00");
        TastingOffer offer = offer(8, seller, batch, 3, 10);
        when(offerRepository.findAllByServingsGreaterThanOrderByOpenedAtDesc(0))
                .thenReturn(List.of(offer));

        List<TastingOfferResponse> mine = service.counter(1L);
        List<TastingOfferResponse> theirs = service.counter(2L);

        assertTrue(mine.getFirst().mine());
        assertFalse(theirs.getFirst().mine());
        assertEquals(recipe.getName(), mine.getFirst().recipeName());
    }

    @Test
    void openReservesServingsFromReadyOwnedBatch() {
        PlayerProfile seller = player(1);
        Batch batch = readyBatch(4, seller, recipe(3), "5.00");
        when(batchRepository.findById(4L)).thenReturn(Optional.of(batch));
        when(offerRepository.findFirstByBatchIdAndServingsGreaterThan(4L, 0))
                .thenReturn(Optional.empty());
        when(offerRepository.countBySellerIdAndServingsGreaterThan(1L, 0)).thenReturn(0L);
        when(offerRepository.save(any(TastingOffer.class))).thenAnswer(invocation -> {
            TastingOffer saved = invocation.getArgument(0);
            saved.setId(8L);
            return saved;
        });

        TastingOfferResponse result = service.open(1L,
                new OpenOfferRequest(4L, 4, 12, "À goûter"));

        assertEquals(0, batch.getVolume().compareTo(new BigDecimal("3.00")));
        assertEquals(4, result.servings());
        assertEquals(12, result.price());
        assertTrue(result.mine());
    }

    @Test
    void openRejectsForeignUnreadyDuplicateFullCounterOrInsufficientVolume() {
        Batch foreign = readyBatch(1, player(2), recipe(3), "5.00");
        when(batchRepository.findById(1L)).thenReturn(Optional.of(foreign));
        assertThrows(AccessDeniedException.class,
                () -> service.open(1L, new OpenOfferRequest(1L, 1, 0, null)));

        Batch unready = batch(2, player(1), recipe(3));
        unready.setStatus(BatchStatus.FERMENTING);
        when(batchRepository.findById(2L)).thenReturn(Optional.of(unready));
        assertThrows(IllegalStateException.class,
                () -> service.open(1L, new OpenOfferRequest(2L, 1, 0, null)));

        Batch duplicate = readyBatch(3, player(1), recipe(3), "5.00");
        when(batchRepository.findById(3L)).thenReturn(Optional.of(duplicate));
        when(offerRepository.findFirstByBatchIdAndServingsGreaterThan(3L, 0))
                .thenReturn(Optional.of(offer(9, player(1), duplicate, 1, 0)));
        assertThrows(IllegalStateException.class,
                () -> service.open(1L, new OpenOfferRequest(3L, 1, 0, null)));

        Batch full = readyBatch(4, player(1), recipe(3), "5.00");
        when(batchRepository.findById(4L)).thenReturn(Optional.of(full));
        when(offerRepository.findFirstByBatchIdAndServingsGreaterThan(4L, 0))
                .thenReturn(Optional.empty());
        when(offerRepository.countBySellerIdAndServingsGreaterThan(1L, 0)).thenReturn(5L);
        assertThrows(IllegalStateException.class,
                () -> service.open(1L, new OpenOfferRequest(4L, 1, 0, null)));

        Batch small = readyBatch(5, player(1), recipe(3), "0.40");
        when(batchRepository.findById(5L)).thenReturn(Optional.of(small));
        when(offerRepository.findFirstByBatchIdAndServingsGreaterThan(5L, 0))
                .thenReturn(Optional.empty());
        when(offerRepository.countBySellerIdAndServingsGreaterThan(1L, 0)).thenReturn(0L);
        assertThrows(IllegalStateException.class,
                () -> service.open(1L, new OpenOfferRequest(5L, 1, 0, null)));
    }

    @Test
    void paidServeMovesCoinsReputationAndAppliesEffect() {
        PlayerProfile seller = player(1);
        PlayerProfile drinker = player(2);
        drinker.setCoin(100);
        Recipe recipe = recipe(3);
        TastingOffer offer = offer(8, seller, readyBatch(4, seller, recipe, "5.00"), 2, 25);
        when(offerRepository.findById(8L)).thenReturn(Optional.of(offer));
        when(playerRepository.findById(2L)).thenReturn(Optional.of(drinker));

        TastingResponse result = service.serve(2L, 8L);

        verify(playerService).spendCoins(2L, 25);
        verify(playerService).reward(1L, 25, 1, 0);
        verify(effectService).grant(2L, recipe);
        assertEquals(1, offer.getServings());
        assertEquals(recipe.getName(), result.recipeName());
    }

    @Test
    void freeServeRewardsSellerReputationOnly() {
        PlayerProfile seller = player(1);
        PlayerProfile drinker = player(2);
        TastingOffer offer = offer(8, seller,
                readyBatch(4, seller, recipe(3), "5.00"), 1, 0);
        when(offerRepository.findById(8L)).thenReturn(Optional.of(offer));
        when(playerRepository.findById(2L)).thenReturn(Optional.of(drinker));

        service.serve(2L, 8L);

        verify(playerService, never()).spendCoins(anyLong(), anyInt());
        verify(playerService).reward(1L, 0, 2, 0);
        assertEquals(0, offer.getServings());
    }

    @Test
    void serveRejectsEmptyOwnAndUnaffordableOffer() {
        PlayerProfile seller = player(1);
        Batch batch = readyBatch(4, seller, recipe(3), "5.00");

        TastingOffer empty = offer(7, seller, batch, 0, 0);
        when(offerRepository.findById(7L)).thenReturn(Optional.of(empty));
        assertThrows(IllegalStateException.class, () -> service.serve(2L, 7L));

        TastingOffer own = offer(8, seller, batch, 1, 0);
        when(offerRepository.findById(8L)).thenReturn(Optional.of(own));
        assertThrows(IllegalStateException.class, () -> service.serve(1L, 8L));

        PlayerProfile poor = player(2);
        poor.setCoin(5);
        TastingOffer pricey = offer(9, seller, batch, 1, 20);
        when(offerRepository.findById(9L)).thenReturn(Optional.of(pricey));
        when(playerRepository.findById(2L)).thenReturn(Optional.of(poor));
        assertThrows(InsufficientCoinsException.class, () -> service.serve(2L, 9L));
    }

    private Batch readyBatch(long id, PlayerProfile seller, Recipe recipe, String volume) {
        Batch batch = batch(id, seller, recipe);
        batch.setStatus(BatchStatus.READY);
        batch.setQuality(80);
        batch.setVolume(new BigDecimal(volume));
        return batch;
    }

    private TastingOffer offer(long id, PlayerProfile seller, Batch batch, int servings, int price) {
        return TastingOffer.builder()
                .id(id).seller(seller).batch(batch)
                .servings(servings).price(price)
                .openedAt(LocalDateTime.now())
                .build();
    }
}
