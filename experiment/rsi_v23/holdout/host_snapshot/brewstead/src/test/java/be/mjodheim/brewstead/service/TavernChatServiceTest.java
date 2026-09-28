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
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Limit;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TavernChatServiceTest {

    @Mock TavernMessageRepository messageRepository;
    @Mock PlayerProfileRepository playerRepository;
    @Mock TavernRoomRepository roomRepository;
    @Mock TavernPresenceRepository presenceRepository;
    @InjectMocks TavernChatService service;

    @Test
    void recentWithoutCursorReversesRepositoryNewestFirstOrder() {
        TavernMessage newest = message(2, "new");
        TavernMessage oldest = message(1, "old");
        when(messageRepository.findByOrderByIdDesc(any(Limit.class)))
                .thenReturn(List.of(newest, oldest));

        List<TavernMessageResponse> result = service.recent(null);

        assertEquals(List.of(1L, 2L), result.stream().map(TavernMessageResponse::id).toList());
    }

    @Test
    void recentWithCursorKeepsAscendingOrder() {
        TavernMessage one = message(3, "one");
        TavernMessage two = message(4, "two");
        when(messageRepository.findByIdGreaterThanOrderByIdAsc(eq(2L), any(Limit.class)))
                .thenReturn(List.of(one, two));

        List<TavernMessageResponse> result = service.recent(2L);

        assertEquals(List.of(3L, 4L), result.stream().map(TavernMessageResponse::id).toList());
    }

    @Test
    void roomChatRequiresPresenceAndStaysInsideTheRoom() {
        PlayerProfile author = player(1);
        TavernRoom room = TavernRoom.builder().id(9L).name("Salle").code("ABC123").capacity(6).build();
        TavernPresence presence = TavernPresence.builder().room(room).player(author).build();

        when(presenceRepository.findByPlayerId(1L)).thenReturn(Optional.of(presence));
        when(messageRepository.countByRoomIdAndAuthorIdAndPostedAtAfter(eq(9L), eq(1L), any(LocalDateTime.class)))
                .thenReturn(0L);
        when(playerRepository.findById(1L)).thenReturn(Optional.of(author));
        when(roomRepository.findById(9L)).thenReturn(Optional.of(room));
        when(messageRepository.save(any(TavernMessage.class))).thenAnswer(invocation -> {
            TavernMessage saved = invocation.getArgument(0);
            saved.setId(12L);
            return saved;
        });

        TavernMessageResponse result = service.postInRoom(9L, 1L, new PostMessageRequest("  Skål   ici  "));

        assertEquals("Skål  ici", result.body());
        verify(messageRepository).save(argThat(message -> message.getRoom() == room));
        assertThrows(IllegalStateException.class,
                () -> service.postInRoom(10L, 1L, new PostMessageRequest("ailleurs")));
    }

    @Test
    void postNormalizesBodyAndPersistsAuthor() {
        PlayerProfile author = player(1);
        when(messageRepository.countByAuthorIdAndPostedAtAfter(eq(1L), any(LocalDateTime.class)))
                .thenReturn(0L);
        when(playerRepository.findById(1L)).thenReturn(Optional.of(author));
        when(messageRepository.save(any(TavernMessage.class))).thenAnswer(invocation -> {
            TavernMessage saved = invocation.getArgument(0);
            saved.setId(5L);
            return saved;
        });

        TavernMessageResponse result = service.post(1L,
                new PostMessageRequest("  Skål    tout le monde  "));

        assertEquals("Skål  tout le monde", result.body());
        assertEquals(1L, result.authorId());
        assertEquals(5L, result.id());
    }

    @Test
    void postRejectsBlankMessageRateLimitAndMissingPlayer() {
        assertThrows(IllegalArgumentException.class,
                () -> service.post(1L, new PostMessageRequest("   ")));

        when(messageRepository.countByAuthorIdAndPostedAtAfter(eq(1L), any(LocalDateTime.class)))
                .thenReturn(12L);
        assertThrows(IllegalStateException.class,
                () -> service.post(1L, new PostMessageRequest("hello")));

        when(messageRepository.countByAuthorIdAndPostedAtAfter(eq(2L), any(LocalDateTime.class)))
                .thenReturn(0L);
        when(playerRepository.findById(2L)).thenReturn(Optional.empty());
        assertThrows(IllegalArgumentException.class,
                () -> service.post(2L, new PostMessageRequest("hello")));
    }

    private TavernMessage message(long id, String body) {
        return TavernMessage.builder()
                .id(id).author(player(1)).body(body)
                .postedAt(LocalDateTime.now())
                .build();
    }
}
