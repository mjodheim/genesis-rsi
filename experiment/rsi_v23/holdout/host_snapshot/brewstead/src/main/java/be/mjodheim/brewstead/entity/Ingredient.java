package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.Unit;
import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Table(name = "ingredients")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class Ingredient {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    @Column(unique = true, nullable = false, length = 80)
    private String name;

    // EnumType.STRING pour que la db puisse stocker des valeurs et non des clés : 'HONEY' au lieu de '0'
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private IngredientType type;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Unit unit;

    // BigDecimal pour éviter les imprécisions des 'double'
    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal baseValue;
}
