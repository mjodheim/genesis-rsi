package be.mjodheim.brewstead.service;

import lombok.RequiredArgsConstructor;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;

import java.security.Principal;

/**
 * Résout le domaine de la session. Rien de ce qui touche à un joueur ne doit
 * dépendre d'un identifiant choisi par le navigateur.
 */
@Service
@RequiredArgsConstructor
public class CurrentPlayerService {

    private final AccountService accountService;

    public Long id(Principal principal) {
        if (principal == null || principal.getName() == null) {
            throw new AccessDeniedException("Session requise.");
        }
        return accountService.currentPlayerId(principal.getName());
    }

    /** Un joueur ne peut pas agir au nom d'un autre, même s'il en connaît l'identifiant. */
    public Long requireSelf(Principal principal, Long claimed) {
        Long self = id(principal);
        if (claimed != null && !self.equals(claimed)) {
            throw new AccessDeniedException("Ce domaine n'est pas le tien.");
        }
        return self;
    }
}
