package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.tavern.*;
import be.mjodheim.brewstead.service.CurrentPlayerService;
import be.mjodheim.brewstead.service.TavernChatService;
import be.mjodheim.brewstead.service.TavernRoomService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.security.Principal;

@RestController
@RequestMapping("/api/tavern/rooms")
@RequiredArgsConstructor
public class TavernSocialController {

    private final TavernRoomService roomService;
    private final TavernChatService chatService;
    private final CurrentPlayerService currentPlayer;

    @GetMapping
    public TavernLobbyResponse lobby(Principal principal) {
        return roomService.lobby(currentPlayer.id(principal));
    }

    @GetMapping("/{roomId}")
    public TavernRoomSnapshot room(Principal principal, @PathVariable Long roomId) {
        return roomService.snapshot(currentPlayer.id(principal), roomId);
    }

    @PostMapping("/join-auto")
    public TavernRoomSnapshot joinAuto(Principal principal) {
        return roomService.joinAuto(currentPlayer.id(principal));
    }

    @PostMapping("/{roomId}/join")
    public TavernRoomSnapshot join(Principal principal, @PathVariable Long roomId) {
        return roomService.join(currentPlayer.id(principal), roomId);
    }

    @PostMapping("/private")
    @ResponseStatus(HttpStatus.CREATED)
    public TavernRoomSnapshot privateRoom(Principal principal,
                                           @Valid @RequestBody(required = false) CreateTavernRoomRequest request) {
        return roomService.createPrivate(currentPlayer.id(principal), request);
    }

    @PostMapping("/join-code/{code}")
    public TavernRoomSnapshot joinCode(Principal principal, @PathVariable String code) {
        return roomService.joinByCode(currentPlayer.id(principal), code);
    }

    @PostMapping("/{roomId}/seats/{seatKey}")
    public TavernRoomSnapshot seat(Principal principal, @PathVariable Long roomId, @PathVariable String seatKey) {
        return roomService.takeSeat(currentPlayer.id(principal), roomId, seatKey);
    }

    @PostMapping("/{roomId}/emotes/{emote}")
    public TavernRoomSnapshot emote(Principal principal, @PathVariable Long roomId, @PathVariable String emote) {
        return roomService.emote(currentPlayer.id(principal), roomId, emote);
    }

    @PostMapping("/{roomId}/messages")
    public TavernMessageResponse message(Principal principal, @PathVariable Long roomId,
                                         @Valid @RequestBody PostMessageRequest request) {
        return chatService.postInRoom(roomId, currentPlayer.id(principal), request);
    }

    @DeleteMapping("/me")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void leave(Principal principal) {
        roomService.leave(currentPlayer.id(principal));
    }
}
