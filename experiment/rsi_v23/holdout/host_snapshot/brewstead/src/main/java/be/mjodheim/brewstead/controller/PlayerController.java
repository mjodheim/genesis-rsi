package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.service.PlayerService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.security.Principal;
import be.mjodheim.brewstead.service.CurrentPlayerService;

@RestController
@RequestMapping("/api/players")
@RequiredArgsConstructor
public class PlayerController {

    private final PlayerService playerService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping("/{playerId}")
    public PlayerProfileResponse getPlayer(Principal principal, @PathVariable Long playerId) {
        return playerService.getPlayer(currentPlayer.requireSelf(principal, playerId));
    }
}
