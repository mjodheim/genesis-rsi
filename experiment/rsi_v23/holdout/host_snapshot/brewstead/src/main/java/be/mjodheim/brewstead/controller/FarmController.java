package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.farm.PlantCropRequest;
import be.mjodheim.brewstead.dto.farm.PlayerFieldResponse;
import be.mjodheim.brewstead.service.FarmService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.security.Principal;
import be.mjodheim.brewstead.service.CurrentPlayerService;

@RestController
@RequestMapping("/api/farm")
@RequiredArgsConstructor
public class FarmController {

    private final FarmService farmService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping("/players/{playerId}/fields")
    public List<PlayerFieldResponse> fields(Principal principal, @PathVariable Long playerId) {
        return farmService.findAllFields(currentPlayer.requireSelf(principal, playerId));
    }

    @PostMapping("/plant")
    public PlayerFieldResponse plant(Principal principal, @RequestBody PlantCropRequest request) {
        return farmService.plant(currentPlayer.id(principal), request);
    }

    /** Défricher une parcelle de plus, contre des pièces. */
    @PostMapping("/fields")
    public List<PlayerFieldResponse> clear(Principal principal) {
        return farmService.clearNewField(currentPlayer.id(principal));
    }

    @PostMapping("/fields/{fieldId}/refresh")
    public PlayerFieldResponse refresh(Principal principal, @PathVariable Long fieldId) {
        return farmService.updateFieldStatus(currentPlayer.id(principal), fieldId);
    }

    @PostMapping("/fields/{fieldId}/harvest")
    public PlayerFieldResponse harvest(Principal principal, @PathVariable Long fieldId) {
        return farmService.harvest(currentPlayer.id(principal), fieldId);
    }
}
