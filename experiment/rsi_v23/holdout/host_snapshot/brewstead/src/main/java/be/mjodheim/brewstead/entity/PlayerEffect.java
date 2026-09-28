package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.EffectKind;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/** Un effet en cours sur un joueur, hérité d'une dégustation. */
@Entity
@Table(name = "player_effects")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class PlayerEffect {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "player_id", nullable = false)
    private PlayerProfile player;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private EffectKind kind;

    /** Ampleur en pourcentage. */
    @Column(nullable = false)
    private int magnitude;

    @Column(nullable = false)
    private LocalDateTime startedAt;

    @Column(nullable = false)
    private LocalDateTime expiresAt;

    /** Le breuvage responsable, pour l'afficher au joueur. */
    @Column(length = 100)
    private String source;
}
