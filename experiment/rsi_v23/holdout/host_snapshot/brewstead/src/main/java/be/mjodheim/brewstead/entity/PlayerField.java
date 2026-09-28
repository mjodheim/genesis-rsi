package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.FieldStatus;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "player_fields")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PlayerField {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY,  optional = false)
    @JoinColumn(name = "player_id",  nullable = false)
    private PlayerProfile player;

    // Une parcelle peut être 'EMPTY' (sans culture plantée) donc crop peut être nullable
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "crop_id")
    private Crop crop;

    private LocalDateTime plantedAt;

    private LocalDateTime readyAt;

    @Enumerated(EnumType.STRING)
    @Builder.Default
    @Column(nullable = false)
    private FieldStatus status = FieldStatus.EMPTY;
}
