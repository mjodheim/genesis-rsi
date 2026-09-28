package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.game.EstateResponse;
import be.mjodheim.brewstead.dto.game.GameStateResponse;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class GameStateService {

    private final PlayerService playerService;
    private final FarmService farmService;
    private final ApiaryService apiaryService;
    private final InventoryService inventoryService;
    private final RecipeService recipeService;
    private final BrewService brewService;
    private final NpcOrderService npcOrderService;

    @Transactional
    public GameStateResponse getState(Long playerId) {
        var fields = farmService.findAllFields(playerId);
        var hives = apiaryService.findAllHives(playerId);
        return new GameStateResponse(
                playerService.getPlayer(playerId),
                fields,
                hives,
                inventoryService.getPlayerInventory(playerId),
                recipeService.findAvailableRecipes(playerId),
                brewService.findPlayerBatches(playerId),
                npcOrderService.findAllOrders(playerId),
                estate(fields.size(), hives.size())
        );
    }

    /**
     * Ce qu'il reste à acheter pour agrandir le domaine.
     *
     * <p>Le barème part du serveur plutôt que d'une table recopiée dans le
     * navigateur : deux copies d'un prix finissent toujours par diverger.
     */
    private EstateResponse estate(int fields, int hives) {
        return new EstateResponse(
                fields, EstatePrices.MAX_FIELDS, EstatePrices.nextField(fields),
                hives, EstatePrices.MAX_HIVES, EstatePrices.nextHive(hives),
                EstatePrices.MAX_HIVE_LEVEL, EstatePrices.upgrades());
    }
}
