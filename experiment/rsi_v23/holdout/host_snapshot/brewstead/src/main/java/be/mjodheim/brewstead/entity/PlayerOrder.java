package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.OrderStatus;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "player_orders")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PlayerOrder {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "creator_id", nullable = false)
    private PlayerProfile creator;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "fulfilled_by_id")
    private PlayerProfile fulfilledBy;

    @Column(nullable = false)
    private LocalDateTime createdAt;

    @Column(nullable = false)
    private LocalDateTime expiresAt;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    @Builder.Default
    private OrderStatus status = OrderStatus.OPEN;

    @Column(nullable = false)
    private int rewardCoins;

    /** Colonne nullable : les commandes déjà en base restent lisibles. */
    private Boolean fulfilledByNpc;

    public boolean isFulfilledByNpc() {
        return Boolean.TRUE.equals(fulfilledByNpc);
    }
}
