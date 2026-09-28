package be.mjodheim.brewstead.config;

import be.mjodheim.brewstead.service.PlayerOrderService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Le temps qui passe sur le domaine, indépendamment des joueurs connectés. */
@Slf4j
@Component
@EnableScheduling
@RequiredArgsConstructor
public class GameClock {

    private final PlayerOrderService playerOrderService;

    /** Les commandes que personne ne prend finissent chez un marchand. */
    @Scheduled(fixedDelay = 60_000, initialDelay = 30_000)
    public void relayOrders() {
        try {
            int relayed = playerOrderService.relayStaleOrders();
            if (relayed > 0) {
                log.info("{} commande(s) reprise(s) par un marchand de passage", relayed);
            }
        } catch (RuntimeException failure) {
            log.warn("Relais des commandes impossible pour l'instant : {}", failure.getMessage());
        }
    }
}
