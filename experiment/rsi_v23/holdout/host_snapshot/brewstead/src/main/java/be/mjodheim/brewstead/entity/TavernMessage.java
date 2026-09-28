package be.mjodheim.brewstead.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/** Une réplique lancée dans la salle de la taverne. */
@Entity
@Table(name = "tavern_messages", indexes = @Index(name = "idx_tavern_posted", columnList = "postedAt"))
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class TavernMessage {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "author_id", nullable = false)
    private PlayerProfile author;

    /** Nul seulement pour les anciens messages du chat global. */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "room_id")
    private TavernRoom room;

    @Column(nullable = false, length = 280)
    private String body;

    @Column(nullable = false)
    private LocalDateTime postedAt;
}
