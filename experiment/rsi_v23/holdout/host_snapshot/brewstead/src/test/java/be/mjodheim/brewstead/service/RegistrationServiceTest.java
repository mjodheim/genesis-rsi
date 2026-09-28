package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.account.RegisterForm;
import be.mjodheim.brewstead.entity.User;
import be.mjodheim.brewstead.enums.UserRole;
import be.mjodheim.brewstead.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class RegistrationServiceTest {

    @Mock UserRepository userRepository;
    @Mock PasswordEncoder passwordEncoder;
    @Mock PlayerService playerService;
    @InjectMocks RegistrationService service;

    RegisterForm form;

    @BeforeEach
    void setUp() {
        form = new RegisterForm();
        form.setUsername("  Eirik  ");
        form.setPassword("secret123");
        form.setConfirmation("secret123");
    }

    @Test
    void registersPlayerAndInitializesDomain() {
        when(userRepository.findByUsername("Eirik")).thenReturn(Optional.empty());
        when(passwordEncoder.encode("secret123")).thenReturn("encoded");
        when(userRepository.save(any(User.class))).thenAnswer(invocation -> {
            User user = invocation.getArgument(0);
            user.setId(42L);
            return user;
        });

        User created = service.register(form);

        assertEquals(42L, created.getId());
        assertEquals("Eirik", created.getUsername());
        assertEquals("encoded", created.getPassword());
        assertEquals(UserRole.PLAYER, created.getRole());
        verify(playerService).initializePlayer(42L);
    }

    @Test
    void rejectsPasswordMismatch() {
        form.setConfirmation("different");

        assertThrows(IllegalArgumentException.class, () -> service.register(form));
        verifyNoInteractions(userRepository, passwordEncoder, playerService);
    }

    @Test
    void rejectsDuplicateUsername() {
        when(userRepository.findByUsername("Eirik")).thenReturn(Optional.of(new User()));

        assertThrows(IllegalArgumentException.class, () -> service.register(form));
        verify(userRepository, never()).save(any());
        verifyNoInteractions(passwordEncoder, playerService);
    }
}
