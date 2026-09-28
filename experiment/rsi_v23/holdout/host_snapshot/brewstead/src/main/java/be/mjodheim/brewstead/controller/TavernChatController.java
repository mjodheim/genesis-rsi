package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.tavern.PostMessageRequest;
import be.mjodheim.brewstead.dto.tavern.TavernMessageResponse;
import be.mjodheim.brewstead.service.CurrentPlayerService;
import be.mjodheim.brewstead.service.TavernChatService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.security.Principal;
import java.util.List;

@RestController
@RequestMapping("/api/tavern/chat")
@RequiredArgsConstructor
public class TavernChatController {

    private final TavernChatService chatService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping
    public List<TavernMessageResponse> messages(@RequestParam(required = false) Long since) {
        return chatService.recent(since);
    }

    @PostMapping
    public TavernMessageResponse post(Principal principal, @Valid @RequestBody PostMessageRequest request) {
        return chatService.post(currentPlayer.id(principal), request);
    }
}
