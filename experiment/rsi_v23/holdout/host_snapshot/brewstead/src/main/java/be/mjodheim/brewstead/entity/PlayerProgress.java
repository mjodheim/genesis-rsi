package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.ProgressAction;
import be.mjodheim.brewstead.enums.EstateTheme;
import be.mjodheim.brewstead.enums.Specialization;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDate;

@Entity
@Table(name = "player_progress")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class PlayerProgress {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "player_id", nullable = false, unique = true)
    private PlayerProfile player;

    @Builder.Default private long harvestedFields = 0;
    @Builder.Default private long harvestedHives = 0;
    @Builder.Default private long startedBatches = 0;
    @Builder.Default private long completedOrders = 0;
    @Builder.Default private long playerTrades = 0;
    @Builder.Default private long tavernTastings = 0;

    private LocalDate lastVisitDate;
    @Builder.Default private int visitStreak = 0;

    private LocalDate dailyDate;

    @Enumerated(EnumType.STRING)
    @Column(length = 30)
    private ProgressAction dailyAction;

    @Builder.Default private int dailyProgress = 0;
    @Builder.Default private boolean dailyClaimed = false;

    @Enumerated(EnumType.STRING)
    @Column(length = 24)
    private Specialization specialization;

    @Builder.Default
    @Enumerated(EnumType.STRING)
    @Column(length = 24)
    private EstateTheme estateTheme = EstateTheme.NORDIQUE;

    @Column(length = 24)
    private String seasonKey;

    @Builder.Default private int seasonPoints = 0;
    @Builder.Default private int seasonRewardTier = 0;

    public EstateTheme getEstateTheme() {
        return estateTheme == null ? EstateTheme.NORDIQUE : estateTheme;
    }
}
