package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.tavern.TavernResponse;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.enums.OrderStatus;
import be.mjodheim.brewstead.repository.PlayerOrderRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static be.mjodheim.brewstead.TestData.player;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TavernServiceTest {

    @Mock PlayerProfileRepository playerRepository;
    @Mock PlayerOrderRepository orderRepository;
    @InjectMocks TavernService service;

    @Test
    void tavernReturnsLeaderboardAndOpenOrderCount() {
        PlayerProfile first = player(1);
        first.setDisplayName("Astrid");
        first.setLevel(8);
        first.setReputation(100);
        PlayerProfile second = player(2);
        second.setLevel(4);
        second.setReputation(50);
        when(playerRepository.findTop10ByOrderByReputationDescLevelDesc())
                .thenReturn(List.of(first, second));
        when(orderRepository.countByStatus(OrderStatus.OPEN)).thenReturn(3L);

        TavernResponse result = service.getTavern();

        assertEquals(2, result.notablePlayers().size());
        assertEquals("Astrid", result.notablePlayers().getFirst().username());
        assertEquals(100, result.notablePlayers().getFirst().reputation());
        assertEquals(3L, result.openPlayerOrders());
    }
}
