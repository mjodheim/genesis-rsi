package be.mjodheim.brewstead.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Table(name = "crops")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class Crop {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 80)
    private String name;

    @ManyToOne(fetch = FetchType.LAZY,  optional = false)
    @JoinColumn(name = "ingredient_id", nullable = false)
    private Ingredient ingredient;

    @Column(nullable = false)
    private int growDurationMinutes;

    @Column(nullable = false, precision = 12, scale = 3)
    private BigDecimal yieldQuantity;
}
