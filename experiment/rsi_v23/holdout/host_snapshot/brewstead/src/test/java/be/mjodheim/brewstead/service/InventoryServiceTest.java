package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.inventory.IngredientRequest;
import be.mjodheim.brewstead.dto.inventory.PlayerInventoryResponse;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerInventory;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.exception.IngredientNotInInventoryException;
import be.mjodheim.brewstead.exception.InsufficientStockException;
import be.mjodheim.brewstead.mapper.InventoryMapper;
import be.mjodheim.brewstead.repository.IngredientRepository;
import be.mjodheim.brewstead.repository.PlayerInventoryRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.ingredient;
import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class InventoryServiceTest {

    @Mock PlayerInventoryRepository inventoryRepository;
    @Mock PlayerProfileRepository playerRepository;
    @Mock IngredientRepository ingredientRepository;
    @Mock InventoryMapper mapper;
    @InjectMocks InventoryService service;

    @Test
    void returnsMappedInventory() {
        List<PlayerInventory> entities = List.of(new PlayerInventory());
        List<PlayerInventoryResponse> expected = List.of(mock(PlayerInventoryResponse.class));
        when(inventoryRepository.findAllByPlayerId(7L)).thenReturn(entities);
        when(mapper.toResponseList(entities)).thenReturn(expected);

        assertSame(expected, service.getPlayerInventory(7L));
    }

    @Test
    void addIngredientIncrementsExistingStock() {
        PlayerProfile player = player(7);
        Ingredient ingredient = ingredient(3, IngredientType.HONEY);
        PlayerInventory stock = PlayerInventory.builder()
                .player(player).ingredient(ingredient)
                .quantity(new BigDecimal("2.500")).build();
        stubEntities(player, ingredient);
        when(inventoryRepository.findByPlayerAndIngredient(player, ingredient))
                .thenReturn(Optional.of(stock));
        when(inventoryRepository.save(stock)).thenReturn(stock);

        service.addIngredient(new IngredientRequest(7L, 3L, new BigDecimal("1.250")));

        assertEquals(new BigDecimal("3.750"), stock.getQuantity());
        verify(inventoryRepository).save(stock);
    }

    @Test
    void addIngredientCreatesStockWhenAbsent() {
        PlayerProfile player = player(7);
        Ingredient ingredient = ingredient(3, IngredientType.HONEY);
        stubEntities(player, ingredient);
        when(inventoryRepository.findByPlayerAndIngredient(player, ingredient))
                .thenReturn(Optional.empty());
        when(inventoryRepository.save(any(PlayerInventory.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        service.addIngredient(new IngredientRequest(7L, 3L, new BigDecimal("1.250")));

        ArgumentCaptor<PlayerInventory> captor = ArgumentCaptor.forClass(PlayerInventory.class);
        verify(inventoryRepository).save(captor.capture());
        assertSame(player, captor.getValue().getPlayer());
        assertSame(ingredient, captor.getValue().getIngredient());
        assertEquals(new BigDecimal("1.250"), captor.getValue().getQuantity());
    }

    @Test
    void rejectsNonPositiveOrNullQuantity() {
        assertThrows(IllegalArgumentException.class,
                () -> service.addIngredient(new IngredientRequest(1L, 1L, null)));
        assertThrows(IllegalArgumentException.class,
                () -> service.addIngredient(new IngredientRequest(1L, 1L, BigDecimal.ZERO)));
        assertThrows(IllegalArgumentException.class,
                () -> service.removeIngredient(new IngredientRequest(1L, 1L, new BigDecimal("-1"))));
        verifyNoInteractions(playerRepository, ingredientRepository);
    }

    @Test
    void rejectsMissingPlayerOrIngredient() {
        when(playerRepository.findById(7L)).thenReturn(Optional.empty());
        assertThrows(IllegalArgumentException.class,
                () -> service.addIngredient(new IngredientRequest(7L, 3L, BigDecimal.ONE)));

        PlayerProfile player = player(7);
        when(playerRepository.findById(7L)).thenReturn(Optional.of(player));
        when(ingredientRepository.findById(3L)).thenReturn(Optional.empty());
        assertThrows(IllegalArgumentException.class,
                () -> service.addIngredient(new IngredientRequest(7L, 3L, BigDecimal.ONE)));
    }

    @Test
    void removeIngredientDecrementsStockIncludingToZero() {
        PlayerProfile player = player(7);
        Ingredient ingredient = ingredient(3, IngredientType.HONEY);
        PlayerInventory stock = PlayerInventory.builder()
                .player(player).ingredient(ingredient)
                .quantity(new BigDecimal("2.500")).build();
        stubEntities(player, ingredient);
        when(inventoryRepository.findByPlayerAndIngredient(player, ingredient))
                .thenReturn(Optional.of(stock));
        when(inventoryRepository.save(stock)).thenReturn(stock);

        service.removeIngredient(new IngredientRequest(7L, 3L, new BigDecimal("2.500")));

        assertEquals(0, stock.getQuantity().compareTo(BigDecimal.ZERO));
    }

    @Test
    void removeIngredientRejectsMissingOrInsufficientStock() {
        PlayerProfile player = player(7);
        Ingredient ingredient = ingredient(3, IngredientType.HONEY);
        stubEntities(player, ingredient);
        when(inventoryRepository.findByPlayerAndIngredient(player, ingredient))
                .thenReturn(Optional.empty());

        assertThrows(IngredientNotInInventoryException.class,
                () -> service.removeIngredient(new IngredientRequest(7L, 3L, BigDecimal.ONE)));

        PlayerInventory stock = PlayerInventory.builder()
                .player(player).ingredient(ingredient)
                .quantity(new BigDecimal("0.500")).build();
        when(inventoryRepository.findByPlayerAndIngredient(player, ingredient))
                .thenReturn(Optional.of(stock));

        assertThrows(InsufficientStockException.class,
                () -> service.removeIngredient(new IngredientRequest(7L, 3L, BigDecimal.ONE)));
        verify(inventoryRepository, never()).save(stock);
    }

    private void stubEntities(PlayerProfile player, Ingredient ingredient) {
        when(playerRepository.findById(player.getId())).thenReturn(Optional.of(player));
        when(ingredientRepository.findById(ingredient.getId())).thenReturn(Optional.of(ingredient));
    }
}
