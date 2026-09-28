package be.mjodheim.brewstead.dto.game;

import java.util.List;

/**
 * Ce que le joueur peut encore acheter pour agrandir son domaine.
 *
 * <p>Les prix viennent du serveur et non d'une table recopiée dans le
 * navigateur : le barème n'existe qu'à un seul endroit.
 */
public record EstateResponse(
        int fields,
        int maxFields,
        Integer fieldPrice,
        int hives,
        int maxHives,
        Integer hivePrice,
        int maxHiveLevel,
        List<Integer> hiveUpgradePrices
) { }
