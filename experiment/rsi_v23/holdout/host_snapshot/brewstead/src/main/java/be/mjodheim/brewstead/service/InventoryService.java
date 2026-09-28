package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.inventory.IngredientRequest;
import be.mjodheim.brewstead.dto.inventory.PlayerInventoryResponse;
import be.mjodheim.brewstead.entity.Ingredient;
import be.mjodheim.brewstead.entity.PlayerInventory;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.exception.IngredientNotInInventoryException;
import be.mjodheim.brewstead.exception.InsufficientStockException;
import be.mjodheim.brewstead.mapper.InventoryMapper;
import be.mjodheim.brewstead.repository.IngredientRepository;
import be.mjodheim.brewstead.repository.PlayerInventoryRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

@Service
@RequiredArgsConstructor
public class InventoryService {

    private final PlayerInventoryRepository playerInventoryRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final IngredientRepository ingredientRepository;
    private final InventoryMapper inventoryMapper;

    @Transactional
    public List<PlayerInventoryResponse> getPlayerInventory(Long id) {
        List<PlayerInventory> playerInventory = playerInventoryRepository.findAllByPlayerId(id);
        return inventoryMapper.toResponseList(playerInventory);
    }

    @Transactional
    public PlayerInventoryResponse addIngredient(IngredientRequest request) {
        validateQuantity(request.quantity());
        PlayerProfile player = getPlayer(request.playerId());
        Ingredient ingredient = getIngredient(request.ingredientId());

        PlayerInventory playerInventory = playerInventoryRepository
                .findByPlayerAndIngredient(player, ingredient)
                .orElseGet(() -> PlayerInventory.builder()
                        .player(player)
                        .ingredient(ingredient)
                        .quantity(BigDecimal.ZERO)
                        .build());

        playerInventory.setQuantity(playerInventory.getQuantity().add(request.quantity()));
        PlayerInventory inventory = playerInventoryRepository.save(playerInventory);
        return inventoryMapper.toPlayerInventoryResponse(inventory);
    }

    @Transactional
    public PlayerInventoryResponse removeIngredient(IngredientRequest request) {
        validateQuantity(request.quantity());
        PlayerProfile player = getPlayer(request.playerId());
        Ingredient ingredient = getIngredient(request.ingredientId());

        PlayerInventory playerInventory = playerInventoryRepository
                .findByPlayerAndIngredient(player, ingredient)
                .orElseThrow(() -> new IngredientNotInInventoryException("Ingredient not found"));

        if (playerInventory.getQuantity().subtract(request.quantity()).compareTo(BigDecimal.ZERO) < 0) {
            throw new InsufficientStockException("Not enough ingredients");
        }

        playerInventory.setQuantity(playerInventory.getQuantity().subtract(request.quantity()));
        PlayerInventory inventory = playerInventoryRepository.save(playerInventory);
        return inventoryMapper.toPlayerInventoryResponse(inventory);
    }

    private void validateQuantity(BigDecimal quantity) {
        if (quantity == null || quantity.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Quantity must be greater than zero");
        }
    }

    private PlayerProfile getPlayer(Long playerId) {
        return playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Player not found"));
    }

    private Ingredient getIngredient(Long ingredientId) {
        return ingredientRepository.findById(ingredientId)
                .orElseThrow(() -> new IllegalArgumentException("Ingredient not found"));
    }
}
