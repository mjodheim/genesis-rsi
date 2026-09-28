package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.order.NpcOrderResponse;
import be.mjodheim.brewstead.service.NpcOrderService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.security.Principal;
import be.mjodheim.brewstead.service.CurrentPlayerService;

@RestController
@RequestMapping("/api/npc-orders")
@RequiredArgsConstructor
public class NpcOrderController {

    private final NpcOrderService npcOrderService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping("/players/{playerId}")
    public List<NpcOrderResponse> orders(Principal principal, @PathVariable Long playerId) {
        return npcOrderService.findAllOrders(currentPlayer.requireSelf(principal, playerId));
    }

    @PostMapping("/players/{playerId}/generate")
    public NpcOrderResponse generate(Principal principal, @PathVariable Long playerId) {
        return npcOrderService.generateOrder(currentPlayer.requireSelf(principal, playerId));
    }

    @PostMapping("/{orderId}/accept")
    public NpcOrderResponse accept(Principal principal, @PathVariable Long orderId) {
        return npcOrderService.acceptOrder(currentPlayer.id(principal), orderId);
    }

    @PostMapping("/{orderId}/complete")
    public NpcOrderResponse complete(Principal principal, @PathVariable Long orderId) {
        return npcOrderService.completeOrder(currentPlayer.id(principal), orderId);
    }
}
