package be.mjodheim.brewstead.entity;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "npc_order_lines")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class NpcOrderLine {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY,  optional = false)
    @JoinColumn(name = "order_id", nullable = false)
    private NpcOrder order;

    @ManyToOne(fetch = FetchType.LAZY,  optional = false)
    @JoinColumn(name = "recipe_id", nullable = false)
    private Recipe recipe;

    @Column(nullable = false)
    private int quantity;

    @Column(nullable = false)
    @Builder.Default
    private int minQuality = 0;
}
