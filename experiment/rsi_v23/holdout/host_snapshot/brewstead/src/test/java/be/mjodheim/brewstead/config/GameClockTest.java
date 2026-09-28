package be.mjodheim.brewstead.config;

import be.mjodheim.brewstead.service.PlayerOrderService;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.Mockito.*;

class GameClockTest {

    @Test
    void relayOrdersDelegatesToPlayerOrderService() {
        PlayerOrderService service = mock(PlayerOrderService.class);
        when(service.relayStaleOrders()).thenReturn(2);
        GameClock clock = new GameClock(service);

        clock.relayOrders();

        verify(service).relayStaleOrders();
    }

    @Test
    void relayOrdersDoesNotBreakSchedulerWhenServiceFails() {
        PlayerOrderService service = mock(PlayerOrderService.class);
        when(service.relayStaleOrders()).thenThrow(new IllegalStateException("db unavailable"));
        GameClock clock = new GameClock(service);

        assertDoesNotThrow(clock::relayOrders);
    }
}
