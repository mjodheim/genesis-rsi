package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;


@Service
@RequiredArgsConstructor
public class AuthService implements UserDetailsService {
    private final UserRepository userRepository;

    public UserDetails loadUserByUsername(String username)
        throws UsernameNotFoundException {
        // findByUsername renvoie un Optional → s'il ne trouve pas de 'User' il renvoie une exception
        return userRepository.findByUsername(username)
                .orElseThrow(() -> new UsernameNotFoundException("User " + username + " not found."));
    }
}
