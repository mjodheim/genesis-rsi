package be.mjodheim.brewstead.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.access.AccessDeniedException;

import java.security.Principal;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class CurrentPlayerServiceTest {

    @Mock AccountService accountService;
    @InjectMocks CurrentPlayerService service;

    @Test
    void resolvesCurrentPlayerFromPrincipal() {
        Principal principal = () -> "eirik";
        when(accountService.currentPlayerId("eirik")).thenReturn(7L);

        assertEquals(7L, service.id(principal));
    }

    @Test
    void requiresAuthenticatedPrincipal() {
        assertThrows(AccessDeniedException.class, () -> service.id(null));

        Principal nameless = mock(Principal.class);
        when(nameless.getName()).thenReturn(null);
        assertThrows(AccessDeniedException.class, () -> service.id(nameless));
    }

    @Test
    void requireSelfAcceptsOwnIdOrMissingClaim() {
        Principal principal = () -> "eirik";
        when(accountService.currentPlayerId("eirik")).thenReturn(7L);

        assertEquals(7L, service.requireSelf(principal, 7L));
        assertEquals(7L, service.requireSelf(principal, null));
    }

    @Test
    void requireSelfRejectsOtherPlayer() {
        Principal principal = () -> "eirik";
        when(accountService.currentPlayerId("eirik")).thenReturn(7L);

        assertThrows(AccessDeniedException.class,
                () -> service.requireSelf(principal, 8L));
    }
}
