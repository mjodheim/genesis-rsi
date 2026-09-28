package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.brew.TastingResponse;
import be.mjodheim.brewstead.dto.tavern.OpenOfferRequest;
import be.mjodheim.brewstead.dto.tavern.TastingOfferResponse;
import be.mjodheim.brewstead.service.CurrentPlayerService;
import be.mjodheim.brewstead.service.TastingCounterService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.security.Principal;
import java.util.List;

@RestController
@RequestMapping("/api/tavern/counter")
@RequiredArgsConstructor
public class TastingCounterController {

    private final TastingCounterService counterService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping
    public List<TastingOfferResponse> counter(Principal principal) {
        return counterService.counter(currentPlayer.id(principal));
    }

    @PostMapping
    public TastingOfferResponse open(Principal principal, @Valid @RequestBody OpenOfferRequest request) {
        return counterService.open(currentPlayer.id(principal), request);
    }

    @PostMapping("/{offerId}/serve")
    public TastingResponse serve(Principal principal, @PathVariable Long offerId) {
        return counterService.serve(currentPlayer.id(principal), offerId);
    }
}
