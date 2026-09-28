package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.order.CreatePlayerOrderRequest;
import be.mjodheim.brewstead.dto.order.PlayerOrderResponse;
import be.mjodheim.brewstead.service.PlayerOrderService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.security.Principal;
import be.mjodheim.brewstead.service.CurrentPlayerService;

@RestController
@RequestMapping("/api/player-orders")
@RequiredArgsConstructor
public class PlayerOrderController {

    private final PlayerOrderService playerOrderService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping("/market")
    public List<PlayerOrderResponse> market() {
        return playerOrderService.findOpenOrders();
    }

    @GetMapping("/players/{playerId}")
    public List<PlayerOrderResponse> playerOrders(Principal principal, @PathVariable Long playerId) {
        return playerOrderService.findPlayerOrders(currentPlayer.requireSelf(principal, playerId));
    }

    @PostMapping
    public PlayerOrderResponse create(Principal principal, @RequestBody CreatePlayerOrderRequest request) {
        currentPlayer.requireSelf(principal, request.creatorId());
        return playerOrderService.createOrder(request);
    }

    @PostMapping("/{orderId}/fulfill")
    public PlayerOrderResponse fulfill(
            Principal principal,
            @PathVariable Long orderId
    ) {
        return playerOrderService.fulfillOrder(orderId, currentPlayer.id(principal));
    }

    @PostMapping("/{orderId}/cancel")
    public PlayerOrderResponse cancel(
            Principal principal,
            @PathVariable Long orderId
    ) {
        return playerOrderService.cancelOrder(orderId, currentPlayer.id(principal));
    }
}
