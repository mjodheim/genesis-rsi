package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.BehiveStatus;
import be.mjodheim.brewstead.enums.FieldStatus;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.exception.InsufficientCoinsException;
import be.mjodheim.brewstead.mapper.PlayerMapper;
import be.mjodheim.brewstead.repository.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static be.mjodheim.brewstead.TestData.ingredient;
import static be.mjodheim.brewstead.TestData.player;
import static be.mjodheim.brewstead.TestData.user;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class PlayerServiceTest {

    @Mock PlayerProfileRepository playerProfileRepository;
    @Mock UserRepository userRepository;
    @Mock PlayerFieldRepository playerFieldRepository;
    @Mock BeehiveRepository beehiveRepository;
    @Mock IngredientRepository ingredientRepository;
    @Mock InventoryService inventoryService;
    @Mock PlayerMapper playerMapper;
    @Mock EffectService effectService;
    @InjectMocks PlayerService service;

    @Test
    void getPlayerMapsEntity() {
        PlayerProfile entity = player(7);
        PlayerProfileResponse expected = mock(PlayerProfileResponse.class);
        when(playerProfileRepository.findById(7L)).thenReturn(Optional.of(entity));
        when(playerMapper.toResponse(entity)).thenReturn(expected);

        assertSame(expected, service.getPlayer(7L));
    }

    @Test
    void initializePlayerIsIdempotent() {
        PlayerProfile existing = player(7);
        PlayerProfileResponse expected = mock(PlayerProfileResponse.class);
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.of(existing));
        when(playerMapper.toResponse(existing)).thenReturn(expected);

        assertSame(expected, service.initializePlayer(1L));
        verifyNoInteractions(userRepository, playerFieldRepository, beehiveRepository,
                ingredientRepository, inventoryService);
    }

    @Test
    void initializePlayerCreatesStarterDomainAndResources() {
        User user = user(1);
        Ingredient starter = ingredient(50, IngredientType.WATER);
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.empty());
        when(userRepository.findById(1L)).thenReturn(Optional.of(user));
        when(playerProfileRepository.save(any(PlayerProfile.class))).thenAnswer(invocation -> {
            PlayerProfile saved = invocation.getArgument(0);
            saved.setId(7L);
            return saved;
        });
        when(ingredientRepository.findByNameIgnoreCase(anyString()))
                .thenReturn(Optional.of(starter));

        service.initializePlayer(1L);

        verify(playerFieldRepository).saveAll(argThat(fields -> {
            int count = 0;
            for (PlayerField field : fields) {
                count++;
                if (field.getStatus() != FieldStatus.EMPTY || field.getPlayer().getId() != 7L) return false;
            }
            return count == 3;
        }));
        verify(beehiveRepository).saveAll(argThat(hives -> {
            int count = 0;
            for (Beehive hive : hives) {
                count++;
                if (hive.getStatus() != BehiveStatus.IDLE || hive.getPlayer().getId() != 7L) return false;
            }
            return count == 2;
        }));
        verify(inventoryService, times(9)).addIngredient(argThat(request ->
                request.playerId().equals(7L) && request.quantity().signum() > 0));
    }

    @Test
    void initializePlayerRequiresUser() {
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.empty());
        when(userRepository.findById(1L)).thenReturn(Optional.empty());

        assertThrows(IllegalArgumentException.class,
                () -> service.initializePlayer(1L));
    }

    @Test
    void spendCoinsValidatesAndDeducts() {
        PlayerProfile player = player(7);
        player.setCoin(100);
        when(playerProfileRepository.findById(7L)).thenReturn(Optional.of(player));

        service.spendCoins(7L, 40);
        assertEquals(60, player.getCoin());

        assertThrows(IllegalArgumentException.class,
                () -> service.spendCoins(7L, 0));
        assertThrows(InsufficientCoinsException.class,
                () -> service.spendCoins(7L, 61));
    }

    @Test
    void refundReturnsExactlyTheEscrowWithoutRewardBonuses() {
        PlayerProfile player = player(7);
        player.setCoin(100);
        when(playerProfileRepository.findById(7L)).thenReturn(Optional.of(player));
        service.spendCoins(7L, 40);
        service.refundCoins(7L, 40);
        assertEquals(100, player.getCoin());
        verifyNoInteractions(effectService);
        assertThrows(IllegalArgumentException.class, () -> service.refundCoins(7L, -1));
    }

    @Test
    void rewardAppliesEffectsAndLevelsPlayer() {
        PlayerProfile player = player(7);
        player.setExperience(995);
        when(playerProfileRepository.findById(7L)).thenReturn(Optional.of(player));
        when(effectService.boostCoins(7L, 100)).thenReturn(125);
        when(effectService.boostReputation(7L, 10)).thenReturn(15);

        service.reward(7L, 100, 10, 10);

        assertEquals(625, player.getCoin());
        assertEquals(15, player.getReputation());
        assertEquals(1005, player.getExperience());
        assertEquals(2, player.getLevel());
    }

    @Test
    void rewardRejectsNegativeValues() {
        assertThrows(IllegalArgumentException.class,
                () -> service.reward(1L, -1, 0, 0));
        assertThrows(IllegalArgumentException.class,
                () -> service.reward(1L, 0, -1, 0));
        assertThrows(IllegalArgumentException.class,
                () -> service.reward(1L, 0, 0, -1));
        verifyNoInteractions(playerProfileRepository);
    }

    @Test
    void getPlayerEntityRejectsUnknownPlayer() {
        when(playerProfileRepository.findById(404L)).thenReturn(Optional.empty());

        assertThrows(IllegalArgumentException.class,
                () -> service.getPlayerEntity(404L));
    }
}
