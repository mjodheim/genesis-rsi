package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.account.ChangePasswordRequest;
import be.mjodheim.brewstead.dto.account.UpdateAccountRequest;
import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.User;
import be.mjodheim.brewstead.enums.Avatar;
import be.mjodheim.brewstead.mapper.PlayerMapper;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import be.mjodheim.brewstead.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static be.mjodheim.brewstead.TestData.player;
import static be.mjodheim.brewstead.TestData.user;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AccountServiceTest {

    @Mock UserRepository userRepository;
    @Mock PlayerProfileRepository playerProfileRepository;
    @Mock PlayerService playerService;
    @Mock PlayerMapper playerMapper;
    @Mock PasswordEncoder passwordEncoder;
    @InjectMocks AccountService service;

    @Test
    void currentAccountReturnsExistingProfile() {
        User user = user(1);
        PlayerProfile profile = player(10);
        PlayerProfileResponse expected = mock(PlayerProfileResponse.class);
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(user));
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.of(profile));
        when(playerMapper.toResponse(profile)).thenReturn(expected);

        assertSame(expected, service.currentAccount("eirik"));
        verifyNoInteractions(playerService);
    }

    @Test
    void currentAccountInitializesMissingProfile() {
        User user = user(1);
        PlayerProfileResponse expected = mock(PlayerProfileResponse.class);
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(user));
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.empty());
        when(playerService.initializePlayer(1L)).thenReturn(expected);

        assertSame(expected, service.currentAccount("eirik"));
    }

    @Test
    void currentPlayerIdUsesExistingOrInitializedProfile() {
        User user = user(1);
        PlayerProfile profile = player(10);
        when(userRepository.findByUsername("existing")).thenReturn(Optional.of(user));
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.of(profile));

        assertEquals(10L, service.currentPlayerId("existing"));

        User second = user(2);
        PlayerProfileResponse initialized = new PlayerProfileResponse(
                20L, "new", "new", Avatar.CERF, 1, 0, 500, 0);
        when(userRepository.findByUsername("new")).thenReturn(Optional.of(second));
        when(playerProfileRepository.findByUserId(2L)).thenReturn(Optional.empty());
        when(playerService.initializePlayer(2L)).thenReturn(initialized);

        assertEquals(20L, service.currentPlayerId("new"));
    }

    @Test
    void updateAccountNormalizesNameAndAvatar() {
        User user = user(1);
        PlayerProfile profile = player(10);
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(user));
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.of(profile));

        service.updateAccount("eirik", new UpdateAccountRequest("  Eirik   le Rouge  ", "loup"));

        assertEquals("Eirik le Rouge", profile.getDisplayName());
        assertEquals(Avatar.LOUP, profile.getAvatar());
        verify(playerMapper).toResponse(profile);
    }

    @Test
    void updateAccountAllowsBlankDisplayNameAndRejectsInvalidName() {
        User user = user(1);
        PlayerProfile profile = player(10);
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(user));
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.of(profile));

        service.updateAccount("eirik", new UpdateAccountRequest("   ", ""));
        assertEquals("user10", profile.getDisplayName());
        assertEquals(Avatar.CERF, profile.getAvatar());

        assertThrows(IllegalArgumentException.class,
                () -> service.updateAccount("eirik", new UpdateAccountRequest("x!", "CERF")));
    }

    @Test
    void updateAccountRequiresExistingDomain() {
        User user = user(1);
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(user));
        when(playerProfileRepository.findByUserId(1L)).thenReturn(Optional.empty());

        assertThrows(IllegalStateException.class,
                () -> service.updateAccount("eirik", new UpdateAccountRequest("Eirik", "CERF")));
    }

    @Test
    void changePasswordValidatesCurrentConfirmationAndReuse() {
        User user = user(1);
        user.setPassword("encoded-old");
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(user));

        when(passwordEncoder.matches("wrong", "encoded-old")).thenReturn(false);
        assertThrows(IllegalArgumentException.class,
                () -> service.changePassword("eirik",
                        new ChangePasswordRequest("wrong", "newSecret", "newSecret")));

        when(passwordEncoder.matches("oldSecret", "encoded-old")).thenReturn(true);
        assertThrows(IllegalArgumentException.class,
                () -> service.changePassword("eirik",
                        new ChangePasswordRequest("oldSecret", "newSecret", "different")));

        when(passwordEncoder.matches("newSecret", "encoded-old")).thenReturn(true);
        assertThrows(IllegalArgumentException.class,
                () -> service.changePassword("eirik",
                        new ChangePasswordRequest("oldSecret", "newSecret", "newSecret")));
    }

    @Test
    void changePasswordEncodesAndSavesNewPassword() {
        User user = user(1);
        user.setPassword("encoded-old");
        when(userRepository.findByUsername("eirik")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("oldSecret", "encoded-old")).thenReturn(true);
        when(passwordEncoder.matches("newSecret", "encoded-old")).thenReturn(false);
        when(passwordEncoder.encode("newSecret")).thenReturn("encoded-new");

        service.changePassword("eirik",
                new ChangePasswordRequest("oldSecret", "newSecret", "newSecret"));

        assertEquals("encoded-new", user.getPassword());
        verify(userRepository).save(user);
    }

    @Test
    void unknownAccountIsRejected() {
        when(userRepository.findByUsername("ghost")).thenReturn(Optional.empty());

        assertThrows(IllegalStateException.class, () -> service.currentAccount("ghost"));
    }
}
