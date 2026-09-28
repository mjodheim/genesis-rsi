package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.OrderStatus;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "npc_orders")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class NpcOrder {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "player_id", nullable = false)
    private PlayerProfile player;

    @Column(nullable = false, length = 100)
    private String customerName;

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

    @Column(nullable = false)
    private int rewardReputation;
}
