package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.inventory.PlayerInventoryResponse;
import be.mjodheim.brewstead.service.InventoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.security.Principal;
import be.mjodheim.brewstead.service.CurrentPlayerService;

@RestController
@RequestMapping("/api/players")
@RequiredArgsConstructor
public class InventoryController {

    private final InventoryService inventoryService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping("/{playerId}/inventory")
    public List<PlayerInventoryResponse> inventory(Principal principal, @PathVariable Long playerId) {
        return inventoryService.getPlayerInventory(currentPlayer.requireSelf(principal, playerId));
    }
}
