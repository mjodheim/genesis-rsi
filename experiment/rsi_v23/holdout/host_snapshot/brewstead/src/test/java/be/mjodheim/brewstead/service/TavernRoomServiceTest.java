package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.tavern.CreateTavernRoomRequest;
import be.mjodheim.brewstead.dto.tavern.TavernRoomSnapshot;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.TavernPresence;
import be.mjodheim.brewstead.entity.TavernRoom;
import be.mjodheim.brewstead.enums.TavernRoomType;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.TavernPresenceRepository;
import be.mjodheim.brewstead.repository.TavernRoomRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TavernRoomServiceTest {

    @Mock TavernRoomRepository rooms;
    @Mock TavernPresenceRepository presences;
    @Mock PlayerProfileRepository players;
    @Mock TavernChatService chat;
    @Mock TastingCounterService counter;

    TavernRoomService service;

    @BeforeEach
    void setUp() {
        service = new TavernRoomService(rooms, presences, players, chat, counter);
    }

    @Test
    void autoJoinPrefersAnOccupiedRoomWithSpace() {
        PlayerProfile me = player(7);
        TavernRoom empty = room(1, TavernRoomType.COMMON);
        TavernRoom lively = room(2, TavernRoomType.COMMON);
        TavernPresence joined = presence(lively, me);

        when(presences.findByPlayerId(7L))
                .thenReturn(Optional.empty(), Optional.empty(), Optional.of(joined));
        when(rooms.findAllByTypeOrderByCreatedAtAsc(TavernRoomType.COMMON)).thenReturn(List.of(empty, lively));
        when(presences.countByRoomId(1L)).thenReturn(0L);
        when(presences.countByRoomId(2L)).thenReturn(4L);
        when(rooms.findForUpdateById(2L)).thenReturn(Optional.of(lively));
        when(players.findById(7L)).thenReturn(Optional.of(me));
        when(presences.findAllByRoomIdOrderByJoinedAtAsc(2L)).thenReturn(List.of(joined));
        when(chat.recentInRoom(2L, null)).thenReturn(List.of());
        when(counter.counter(7L)).thenReturn(List.of());

        TavernRoomSnapshot result = service.joinAuto(7L);

        assertEquals(2L, result.id());
        verify(presences, times(2)).save(argThat(p -> p.getRoom().getId().equals(2L)));
    }

    @Test
    void seatCannotBeStolenAndEightSeatsLeaveChoiceForSixPlayers() {
        PlayerProfile me = player(7);
        PlayerProfile other = player(8);
        TavernRoom room = room(4, TavernRoomType.COMMON);
        TavernPresence mine = presence(room, me);
        TavernPresence taken = presence(room, other);
        taken.setSeatKey("bar-gauche");

        when(rooms.findForUpdateById(4L)).thenReturn(Optional.of(room));
        when(presences.findByPlayerId(7L)).thenReturn(Optional.of(mine));
        when(presences.findByRoomIdAndSeatKey(4L, "bar-gauche")).thenReturn(Optional.of(taken));

        assertThrows(IllegalStateException.class,
                () -> service.takeSeat(7L, 4L, "bar-gauche"));

        when(presences.findByRoomIdAndSeatKey(4L, "feu-gauche")).thenReturn(Optional.empty());
        when(presences.findAllByRoomIdOrderByJoinedAtAsc(4L)).thenReturn(List.of(mine, taken));
        when(chat.recentInRoom(4L, null)).thenReturn(List.of());
        when(counter.counter(7L)).thenReturn(List.of());

        TavernRoomSnapshot seated = service.takeSeat(7L, 4L, "feu-gauche");
        assertEquals(8, seated.seats().size());
        assertEquals("feu-gauche", mine.getSeatKey());
    }

    @Test
    void privateRoomProducesAShareableCode() {
        PlayerProfile me = player(7);
        when(players.findById(7L)).thenReturn(Optional.of(me));
        when(rooms.findByCodeIgnoreCase(anyString())).thenReturn(Optional.empty());
        when(rooms.save(any(TavernRoom.class))).thenAnswer(invocation -> {
            TavernRoom room = invocation.getArgument(0);
            room.setId(9L);
            return room;
        });

        TavernRoom[] created = new TavernRoom[1];
        when(presences.save(any(TavernPresence.class))).thenAnswer(invocation -> {
            TavernPresence p = invocation.getArgument(0);
            created[0] = p.getRoom();
            return p;
        });
        when(presences.findByPlayerId(7L)).thenAnswer(invocation ->
                created[0] == null ? Optional.empty() : Optional.of(presence(created[0], me)));
        when(presences.findAllByRoomIdOrderByJoinedAtAsc(9L)).thenAnswer(invocation ->
                List.of(presence(created[0], me)));
        when(chat.recentInRoom(9L, null)).thenReturn(List.of());
        when(counter.counter(7L)).thenReturn(List.of());

        TavernRoomSnapshot result = service.createPrivate(7L, new CreateTavernRoomRequest("Les copains"));

        assertEquals("PRIVATE", result.type());
        assertEquals(6, result.code().length());
        verify(presences).deleteByPlayerId(7L);
    }

    private TavernRoom room(long id, TavernRoomType type) {
        return TavernRoom.builder().id(id).code("ABC123").name("Salle " + id)
                .type(type).capacity(6).createdAt(LocalDateTime.now()).build();
    }

    private TavernPresence presence(TavernRoom room, PlayerProfile player) {
        return TavernPresence.builder().room(room).player(player)
                .joinedAt(LocalDateTime.now()).lastSeenAt(LocalDateTime.now()).build();
    }
}
