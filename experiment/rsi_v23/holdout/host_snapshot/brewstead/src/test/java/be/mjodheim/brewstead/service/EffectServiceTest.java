package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.effect.PlayerEffectResponse;
import be.mjodheim.brewstead.entity.PlayerEffect;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.repository.PlayerEffectRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.player;
import static be.mjodheim.brewstead.TestData.recipe;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class EffectServiceTest {

    @Mock PlayerEffectRepository effectRepository;
    @Mock PlayerProfileRepository playerRepository;
    @InjectMocks EffectService service;

    @Test
    void activeEffectsMapsRepositoryResults() {
        PlayerEffect effect = effect(EffectKind.INSPIRATION, 20);
        effect.setId(9L);
        effect.setSource("Hydromel");
        when(effectRepository.findAllByPlayerIdAndExpiresAtAfterOrderByExpiresAtAsc(
                eq(1L), any(LocalDateTime.class))).thenReturn(List.of(effect));

        List<PlayerEffectResponse> result = service.activeEffects(1L);

        assertEquals(1, result.size());
        assertEquals(9L, result.getFirst().id());
        assertEquals(EffectKind.INSPIRATION, result.getFirst().kind());
        assertEquals(20, result.getFirst().magnitude());
    }

    @Test
    void grantIgnoresNeutralOrExpiredDefinition() {
        Recipe neutral = recipe(1);
        neutral.setEffectKind(EffectKind.AUCUN);
        neutral.setEffectDurationMinutes(10);
        assertNull(service.grant(1L, neutral));

        Recipe zeroDuration = recipe(2);
        zeroDuration.setEffectKind(EffectKind.INSPIRATION);
        zeroDuration.setEffectDurationMinutes(0);
        assertNull(service.grant(1L, zeroDuration));

        verifyNoInteractions(playerRepository, effectRepository);
    }

    @Test
    void grantCreatesAndClampsEffectMagnitude() {
        PlayerProfile player = player(1);
        Recipe recipe = recipe(1);
        recipe.setName("Berserker");
        recipe.setEffectKind(EffectKind.INSPIRATION);
        recipe.setEffectMagnitude(90);
        recipe.setEffectDurationMinutes(15);
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player));
        when(effectRepository.findFirstByPlayerIdAndKindAndExpiresAtAfter(
                eq(1L), eq(EffectKind.INSPIRATION), any(LocalDateTime.class)))
                .thenReturn(Optional.empty());
        when(effectRepository.save(any(PlayerEffect.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        PlayerEffectResponse result = service.grant(1L, recipe);

        assertEquals(50, result.magnitude());
        assertEquals("Berserker", result.source());
        assertTrue(result.expiresAt().isAfter(result.startedAt().plusMinutes(14)));
    }

    @Test
    void grantExtendsExistingEffectAndKeepsHighestMagnitude() {
        PlayerProfile player = player(1);
        LocalDateTime oldExpiry = LocalDateTime.now().plusMinutes(5);
        PlayerEffect existing = PlayerEffect.builder()
                .player(player)
                .kind(EffectKind.INSPIRATION)
                .magnitude(40)
                .startedAt(LocalDateTime.now().minusMinutes(2))
                .expiresAt(oldExpiry)
                .source("Old")
                .build();
        Recipe recipe = recipe(1);
        recipe.setEffectKind(EffectKind.INSPIRATION);
        recipe.setEffectMagnitude(20);
        recipe.setEffectDurationMinutes(10);
        when(playerRepository.findById(1L)).thenReturn(Optional.of(player));
        when(effectRepository.findFirstByPlayerIdAndKindAndExpiresAtAfter(
                eq(1L), eq(EffectKind.INSPIRATION), any(LocalDateTime.class)))
                .thenReturn(Optional.of(existing));
        when(effectRepository.save(existing)).thenReturn(existing);

        PlayerEffectResponse result = service.grant(1L, recipe);

        assertEquals(40, result.magnitude());
        assertEquals(oldExpiry.plusMinutes(10), result.expiresAt());
    }

    @Test
    void grantRequiresExistingPlayer() {
        Recipe recipe = recipe(1);
        recipe.setEffectKind(EffectKind.INSPIRATION);
        recipe.setEffectDurationMinutes(10);
        when(playerRepository.findById(1L)).thenReturn(Optional.empty());

        assertThrows(IllegalArgumentException.class,
                () -> service.grant(1L, recipe));
    }

    @Test
    void magnitudeReturnsActiveValueOrZero() {
        when(effectRepository.findFirstByPlayerIdAndKindAndExpiresAtAfter(
                eq(1L), eq(EffectKind.INSPIRATION), any(LocalDateTime.class)))
                .thenReturn(Optional.of(effect(EffectKind.INSPIRATION, 30)));

        assertEquals(30, service.magnitudeOf(1L, EffectKind.INSPIRATION));

        when(effectRepository.findFirstByPlayerIdAndKindAndExpiresAtAfter(
                eq(1L), eq(EffectKind.MAIN_LOURDE), any(LocalDateTime.class)))
                .thenReturn(Optional.empty());
        assertEquals(0, service.magnitudeOf(1L, EffectKind.MAIN_LOURDE));
    }

    @Test
    void durationFactorCombinesHasteAndSleepAndClamps() {
        when(effectRepository.findFirstByPlayerIdAndKindAndExpiresAtAfter(
                eq(1L), any(EffectKind.class), any(LocalDateTime.class)))
                .thenAnswer(invocation -> {
                    EffectKind kind = invocation.getArgument(1);
                    if (kind == EffectKind.MAIN_VERTE) {
                        return Optional.of(effect(kind, 50));
                    }
                    if (kind == EffectKind.SOMMEIL_DE_L_OURS) {
                        return Optional.of(effect(kind, 50));
                    }
                    return Optional.empty();
                });

        assertEquals(0.75, service.durationFactor(1L, EffectKind.MAIN_VERTE), 0.0001);
    }

    @Test
    void qualityAndRewardModifiersUseTheirEffects() {
        when(effectRepository.findFirstByPlayerIdAndKindAndExpiresAtAfter(
                eq(1L), any(EffectKind.class), any(LocalDateTime.class)))
                .thenAnswer(invocation -> {
                    EffectKind kind = invocation.getArgument(1);
                    int magnitude = switch (kind) {
                        case INSPIRATION -> 30;
                        case MAIN_LOURDE -> 10;
                        case BOURSE_PERCEE -> 25;
                        case LANGUE_DOREE -> 50;
                        default -> 0;
                    };
                    return magnitude == 0 ? Optional.empty() : Optional.of(effect(kind, magnitude));
                });

        assertEquals(10, service.qualityShift(1L));
        assertEquals(125, service.boostCoins(1L, 100));
        assertEquals(15, service.boostReputation(1L, 10));
    }

    private PlayerEffect effect(EffectKind kind, int magnitude) {
        return PlayerEffect.builder()
                .player(player(1))
                .kind(kind)
                .magnitude(magnitude)
                .startedAt(LocalDateTime.now().minusMinutes(1))
                .expiresAt(LocalDateTime.now().plusMinutes(5))
                .build();
    }
}
