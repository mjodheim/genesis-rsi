package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.brew.BatchResponse;
import be.mjodheim.brewstead.dto.brew.TastingResponse;
import be.mjodheim.brewstead.service.AccountService;
import be.mjodheim.brewstead.dto.brew.StartBatchRequest;
import be.mjodheim.brewstead.service.BrewService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.security.Principal;
import be.mjodheim.brewstead.service.CurrentPlayerService;

@RestController
@RequestMapping("/api/brewery")
@RequiredArgsConstructor
public class BrewController {

    private final BrewService brewService;
    private final CurrentPlayerService currentPlayer;
    private final AccountService accountService;

    @GetMapping("/players/{playerId}/batches")
    public List<BatchResponse> batches(Principal principal, @PathVariable Long playerId) {
        return brewService.findPlayerBatches(currentPlayer.requireSelf(principal, playerId));
    }

    @PostMapping("/batches")
    public BatchResponse start(Principal principal, @RequestBody StartBatchRequest request) {
        return brewService.startBatch(currentPlayer.requireSelf(principal, request.playerId()), request);
    }

    @PostMapping("/batches/{batchId}/taste")
    public TastingResponse taste(Principal principal, @PathVariable Long batchId) {
        return brewService.taste(currentPlayer.id(principal), batchId);
    }

    @PostMapping("/batches/{batchId}/refresh")
    public BatchResponse refresh(Principal principal, @PathVariable Long batchId) {
        return brewService.updateBatchStatus(currentPlayer.id(principal), batchId);
    }
}
