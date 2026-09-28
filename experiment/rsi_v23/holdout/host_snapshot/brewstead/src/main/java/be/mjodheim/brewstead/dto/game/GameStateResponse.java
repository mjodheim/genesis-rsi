package be.mjodheim.brewstead.dto.game;

import be.mjodheim.brewstead.dto.apiary.BeehiveResponse;
import be.mjodheim.brewstead.dto.brew.BatchResponse;
import be.mjodheim.brewstead.dto.farm.PlayerFieldResponse;
import be.mjodheim.brewstead.dto.inventory.PlayerInventoryResponse;
import be.mjodheim.brewstead.dto.order.NpcOrderResponse;
import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.dto.recipe.RecipeResponse;

import java.util.List;

public record GameStateResponse(
        PlayerProfileResponse player,
        List<PlayerFieldResponse> fields,
        List<BeehiveResponse> hives,
        List<PlayerInventoryResponse> inventory,
        List<RecipeResponse> recipes,
        List<BatchResponse> batches,
        List<NpcOrderResponse> npcOrders,
        EstateResponse estate
) {
}
