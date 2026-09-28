package be.mjodheim.brewstead.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Table(
        name = "player_inventory",
        uniqueConstraints = @UniqueConstraint (
                columnNames = {
                        "player_id", "ingredient_id"
                }
        )
)
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PlayerInventory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private  long id;

    @ManyToOne(fetch = FetchType.LAZY,  optional = false)
    @JoinColumn(name = "player_id", nullable = false)
    private PlayerProfile player;

    @ManyToOne(fetch = FetchType.LAZY,  optional = false)
    @JoinColumn(name = "ingredient_id",  nullable = false)
    private Ingredient ingredient;

    @Builder.Default
    @Column(nullable = false, precision = 12, scale = 3)
    private BigDecimal quantity =  BigDecimal.ZERO;
}
