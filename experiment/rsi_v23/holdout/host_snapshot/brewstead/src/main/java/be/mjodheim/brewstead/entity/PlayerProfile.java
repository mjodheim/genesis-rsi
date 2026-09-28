package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.Avatar;
import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "player_profiles")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class PlayerProfile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(cascade = CascadeType.MERGE,  fetch = FetchType.LAZY, optional = false)
    @JoinColumn(
            name = "user_id",
            nullable = false,
            unique = true
    )
    private User user;

    @Builder.Default
    @Column(nullable = false)
    private int level = 1;

    @Builder.Default
    @Column(nullable = false)
    private int experience = 0;

    @Builder.Default
    @Column(nullable = false)
    private int coin = 500;

    @Builder.Default
    @Column(nullable = false)
    private int reputation = 0;

    /**
     * Nom montré dans le jeu. Reste nul tant que le joueur n'en a pas choisi un :
     * on retombe alors sur l'identifiant de connexion.
     */
    @Column(length = 30)
    private String displayName;

    /** Colonne laissée nullable pour ne pas casser les lignes déjà en base. */
    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private Avatar avatar;

    public String getDisplayName() {
        if (displayName != null && !displayName.isBlank()) {
            return displayName;
        }
        return user == null ? null : user.getUsername();
    }

    public Avatar getAvatar() {
        return avatar == null ? Avatar.DEFAULT : avatar;
    }

}
