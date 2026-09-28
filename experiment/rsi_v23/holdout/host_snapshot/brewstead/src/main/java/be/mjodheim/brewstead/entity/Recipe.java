package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.DrinkType;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.Rarity;
import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Table(name = "recipes")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Recipe {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    // Les recettes officielles du jeu n'ont pas de 'owner' → nullable
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "owner_id")
    private PlayerProfile owner;

    @Column(nullable = false, length = 100)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private DrinkType drinkType;

    @Column(nullable = false, precision = 8, scale = 2)
    private BigDecimal baseVolume;

    @Column(nullable = false)
    private int fermentationDurationHours;

    /**
     * Durée fine, en minutes. Prime sur les heures quand elle est renseignée :
     * une cervoise de tous les jours ne doit pas demander une heure pleine.
     */
    private Integer fermentationDurationMinutes;

    /** La durée réellement utilisée par la brasserie. */
    public int getFermentationMinutes() {
        if (fermentationDurationMinutes != null && fermentationDurationMinutes > 0) {
            return fermentationDurationMinutes;
        }
        return Math.max(1, fermentationDurationHours) * 60;
    }

    @Column(nullable = false)
    @Builder.Default
    private boolean isPublic = false;

    /* --- Ce que ça fait quand on y goûte ------------------------------------
       Colonnes nullables : les recettes créées avant cette version restent
       lisibles, le code retombe sur des valeurs neutres. */

    @Enumerated(EnumType.STRING)
    @Column(length = 30)
    private EffectKind effectKind;

    /** Ampleur de l'effet, en pourcentage. */
    private Integer effectMagnitude;

    private Integer effectDurationMinutes;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private Rarity rarity;

    /** La ligne que lit le joueur dans le grimoire. */
    @Column(length = 240)
    private String flavour;

    public EffectKind getEffectKind() {
        return effectKind == null ? EffectKind.AUCUN : effectKind;
    }

    public int getEffectMagnitude() {
        return effectMagnitude == null ? 0 : effectMagnitude;
    }

    public int getEffectDurationMinutes() {
        return effectDurationMinutes == null ? 0 : effectDurationMinutes;
    }

    public Rarity getRarity() {
        return rarity == null ? Rarity.COMMUNE : rarity;
    }
}
