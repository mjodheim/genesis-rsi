package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.entity.User;
import be.mjodheim.brewstead.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.userdetails.UsernameNotFoundException;

import java.util.Optional;

import static be.mjodheim.brewstead.TestData.user;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock UserRepository userRepository;
    @InjectMocks AuthService service;

    @Test
    void loadsExistingUser() {
        User expected = user(1);
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(expected));

        assertSame(expected, service.loadUserByUsername("eirik"));
    }

    @Test
    void rejectsUnknownUser() {
        when(userRepository.findByUsername("ghost")).thenReturn(Optional.empty());

        assertThrows(UsernameNotFoundException.class,
                () -> service.loadUserByUsername("ghost"));
    }
}
