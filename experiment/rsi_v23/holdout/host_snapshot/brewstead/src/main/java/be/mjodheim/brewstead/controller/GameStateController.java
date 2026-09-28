package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.game.GameStateResponse;
import be.mjodheim.brewstead.dto.game.HarvestAllResponse;
import be.mjodheim.brewstead.service.ApiaryService;
import be.mjodheim.brewstead.service.FarmService;
import be.mjodheim.brewstead.service.GameStateService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.security.Principal;
import be.mjodheim.brewstead.service.CurrentPlayerService;

@RestController
@RequestMapping("/api/players")
@RequiredArgsConstructor
public class GameStateController {

    private final GameStateService gameStateService;
    private final FarmService farmService;
    private final ApiaryService apiaryService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping("/{playerId}/state")
    public GameStateResponse getState(Principal principal, @PathVariable Long playerId) {
        return gameStateService.getState(currentPlayer.requireSelf(principal, playerId));
    }

    /**
     * La tournée du matin : champs et ruches ramassés d'un seul geste.
     *
     * <p>Une seule requête plutôt qu'une par parcelle : le domaine reste
     * cohérent et le client n'a qu'un rafraîchissement à faire.
     */
    @PostMapping("/{playerId}/harvest-all")
    public HarvestAllResponse harvestAll(Principal principal, @PathVariable Long playerId) {
        Long self = currentPlayer.requireSelf(principal, playerId);
        return new HarvestAllResponse(farmService.harvestAll(self), apiaryService.harvestAll(self));
    }
}
