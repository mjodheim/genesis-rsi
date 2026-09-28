package be.mjodheim.brewstead.dto.game;

/**
 * Le résultat d'une tournée de récolte.
 *
 * <p>Le client n'a pas à compter lui-même : il annonce ce qui a été ramassé,
 * et le total sert à savoir s'il y avait seulement quelque chose à faire.
 */
public record HarvestAllResponse(int fields, int hives) {

    public int total() {
        return fields + hives;
    }
}
