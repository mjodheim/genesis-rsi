package be.mjodheim.brewstead.entity;

import be.mjodheim.brewstead.enums.TavernRoomType;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "tavern_rooms", indexes = {
        @Index(name = "idx_tavern_room_type", columnList = "type"),
        @Index(name = "idx_tavern_room_code", columnList = "code", unique = true)
})
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class TavernRoom {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 16)
    private String code;

    @Column(nullable = false, length = 40)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 12)
    private TavernRoomType type;

    @Column(nullable = false)
    private int capacity;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "owner_id")
    private PlayerProfile owner;

    @Column(nullable = false)
    private LocalDateTime createdAt;
}
