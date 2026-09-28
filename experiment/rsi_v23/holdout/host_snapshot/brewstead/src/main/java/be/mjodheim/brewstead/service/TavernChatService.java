package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.tavern.PostMessageRequest;
import be.mjodheim.brewstead.dto.tavern.TavernMessageResponse;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.TavernMessage;
import be.mjodheim.brewstead.entity.TavernPresence;
import be.mjodheim.brewstead.entity.TavernRoom;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.TavernMessageRepository;
import be.mjodheim.brewstead.repository.TavernPresenceRepository;
import be.mjodheim.brewstead.repository.TavernRoomRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Limit;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/** La salle commune : tout le monde lit, tout le monde parle. */
@Service
@RequiredArgsConstructor
public class TavernChatService {

    private static final int WINDOW = 60;
    /** Assez pour discuter, trop peu pour noyer la salle. */
    private static final int MAX_PER_MINUTE = 12;

    private final TavernMessageRepository messageRepository;
    private final PlayerProfileRepository playerProfileRepository;
    private final TavernRoomRepository roomRepository;
    private final TavernPresenceRepository presenceRepository;

    @Transactional
    public List<TavernMessageResponse> recent(Long sinceId) {
        List<TavernMessage> messages = sinceId == null
                ? reversed(messageRepository.findByOrderByIdDesc(Limit.of(WINDOW)))
                : messageRepository.findByIdGreaterThanOrderByIdAsc(sinceId, Limit.of(WINDOW));
        return messages.stream().map(this::toResponse).toList();
    }

    @Transactional
    public List<TavernMessageResponse> recentInRoom(Long roomId, Long sinceId) {
        List<TavernMessage> messages = sinceId == null
                ? reversed(messageRepository.findByRoomIdOrderByIdDesc(roomId, Limit.of(WINDOW)))
                : messageRepository.findByRoomIdAndIdGreaterThanOrderByIdAsc(roomId, sinceId, Limit.of(WINDOW));
        return messages.stream().map(this::toResponse).toList();
    }

    @Transactional
    public TavernMessageResponse postInRoom(Long roomId, Long playerId, PostMessageRequest request) {
        TavernPresence presence = presenceRepository.findByPlayerId(playerId)
                .orElseThrow(() -> new IllegalStateException("Entre dans une salle avant de parler."));
        if (!presence.getRoom().getId().equals(roomId)) {
            throw new IllegalStateException("Tu n'es pas dans cette salle.");
        }

        String body = normalize(request);
        long recent = messageRepository.countByRoomIdAndAuthorIdAndPostedAtAfter(
                roomId, playerId, LocalDateTime.now().minusMinutes(1));
        if (recent >= MAX_PER_MINUTE) {
            throw new IllegalStateException("Laisse les autres placer un mot.");
        }

        PlayerProfile author = playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Joueur introuvable."));
        TavernRoom room = roomRepository.findById(roomId)
                .orElseThrow(() -> new IllegalArgumentException("Salle introuvable."));

        return toResponse(messageRepository.save(TavernMessage.builder()
                .author(author)
                .room(room)
                .body(body)
                .postedAt(LocalDateTime.now())
                .build()));
    }

    @Transactional
    public TavernMessageResponse post(Long playerId, PostMessageRequest request) {
        String body = normalize(request);

        long recent = messageRepository.countByAuthorIdAndPostedAtAfter(
                playerId, LocalDateTime.now().minusMinutes(1));
        if (recent >= MAX_PER_MINUTE) {
            throw new IllegalStateException("Laisse les autres placer un mot.");
        }

        PlayerProfile author = playerProfileRepository.findById(playerId)
                .orElseThrow(() -> new IllegalArgumentException("Joueur introuvable."));

        return toResponse(messageRepository.save(
                TavernMessage.builder()
                        .author(author)
                        .body(body)
                        .postedAt(LocalDateTime.now())
                        .build()));
    }

    private String normalize(PostMessageRequest request) {
        String body = request.body() == null ? "" : request.body().trim().replaceAll("\\s{3,}", "  ");
        if (body.isEmpty()) {
            throw new IllegalArgumentException("Dis quelque chose.");
        }
        return body;
    }

    private List<TavernMessage> reversed(List<TavernMessage> messages) {
        List<TavernMessage> copy = new ArrayList<>(messages);
        java.util.Collections.reverse(copy);
        return copy;
    }

    private TavernMessageResponse toResponse(TavernMessage message) {
        PlayerProfile author = message.getAuthor();
        return new TavernMessageResponse(
                message.getId(),
                author.getId(),
                author.getDisplayName(),
                author.getAvatar(),
                message.getBody(),
                message.getPostedAt()
        );
    }
}
