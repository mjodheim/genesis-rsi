package be.mjodheim.brewstead.service;

import be.mjodheim.brewstead.dto.tavern.TavernPlayerResponse;
import be.mjodheim.brewstead.dto.tavern.TavernResponse;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.enums.OrderStatus;
import be.mjodheim.brewstead.repository.PlayerOrderRepository;
import be.mjodheim.brewstead.repository.PlayerProfileRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TavernService {

    private final PlayerProfileRepository playerProfileRepository;
    private final PlayerOrderRepository playerOrderRepository;

    @Transactional
    public TavernResponse getTavern() {
        List<TavernPlayerResponse> players = playerProfileRepository
                .findTop10ByOrderByReputationDescLevelDesc()
                .stream()
                .map(this::toResponse)
                .toList();

        return new TavernResponse(
                players,
                playerOrderRepository.countByStatus(OrderStatus.OPEN)
        );
    }

    private TavernPlayerResponse toResponse(PlayerProfile player) {
        return new TavernPlayerResponse(
                player.getId(),
                player.getDisplayName(),
                player.getLevel(),
                player.getReputation()
        );
    }
}
