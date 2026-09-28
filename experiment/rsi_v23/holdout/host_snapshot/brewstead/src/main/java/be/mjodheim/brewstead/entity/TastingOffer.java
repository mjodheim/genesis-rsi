package be.mjodheim.brewstead.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * Une offre au comptoir : un brasseur met des services de son fût à
 * disposition. Le prix peut être nul — on fait alors goûter pour rien.
 */
@Entity
@Table(name = "tasting_offers")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class TastingOffer {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "seller_id", nullable = false)
    private PlayerProfile seller;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "batch_id", nullable = false)
    private Batch batch;

    /** Nombre de services encore disponibles. */
    @Column(nullable = false)
    private int servings;

    /** Prix d'un service, en pièces. Zéro est une valeur légitime. */
    @Column(nullable = false)
    private int price;

    @Column(nullable = false)
    private LocalDateTime openedAt;

    @Column(length = 140)
    private String note;
}
