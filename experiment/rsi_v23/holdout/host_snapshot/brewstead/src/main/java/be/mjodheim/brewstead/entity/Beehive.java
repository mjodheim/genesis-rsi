package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.BehiveStatus;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "beehives")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Beehive {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "player_id", nullable = false)
    private PlayerProfile player;

    @Column(nullable = false)
    @Builder.Default
    private int level = 1;

    private LocalDateTime startedAt;

    private LocalDateTime readyAt;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    @Builder.Default
    private BehiveStatus status = BehiveStatus.IDLE;
}
