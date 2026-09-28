package be.mjodheim.brewstead.mapper;

import be.mjodheim.brewstead.dto.apiary.BeehiveResponse;
import be.mjodheim.brewstead.dto.brew.BatchResponse;
import be.mjodheim.brewstead.dto.farm.PlayerFieldResponse;
import be.mjodheim.brewstead.dto.inventory.PlayerInventoryResponse;
import be.mjodheim.brewstead.dto.order.NpcOrderResponse;
import be.mjodheim.brewstead.dto.order.PlayerOrderResponse;
import be.mjodheim.brewstead.dto.player.PlayerProfileResponse;
import be.mjodheim.brewstead.dto.recipe.RecipeResponse;
import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.*;
import org.junit.jupiter.api.Test;
import org.mapstruct.factory.Mappers;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import static be.mjodheim.brewstead.TestData.*;
import static org.junit.jupiter.api.Assertions.*;

class MapperTest {

    @Test
    void apiaryMapperCopiesHiveState() {
        ApiaryMapper mapper = Mappers.getMapper(ApiaryMapper.class);
        Beehive hive = Beehive.builder()
                .id(3L).player(player(1)).level(4)
                .startedAt(LocalDateTime.now().minusMinutes(2))
                .readyAt(LocalDateTime.now().plusMinutes(2))
                .status(BehiveStatus.PRODUCING)
                .build();

        BeehiveResponse response = mapper.toResponse(hive);

        assertEquals(3L, response.id());
        assertEquals(4, response.level());
        assertEquals(BehiveStatus.PRODUCING, response.status());
    }

    @Test
    void brewMapperFlattensRecipeIdentity() {
        BrewMapper mapper = Mappers.getMapper(BrewMapper.class);
        Recipe recipe = recipe(9);
        Batch batch = batch(4, player(1), recipe);
        batch.setQuality(88);

        BatchResponse response = mapper.toResponse(batch);

        assertEquals(4L, response.id());
        assertEquals(9L, response.recipeId());
        assertEquals(recipe.getName(), response.recipeName());
        assertEquals(88, response.quality());
    }

    @Test
    void farmMapperMapsCropNameAndAllowsEmptyField() {
        FarmMapper mapper = Mappers.getMapper(FarmMapper.class);
        Crop crop = Crop.builder().id(2L).name("Orge du Nord").build();
        PlayerField planted = PlayerField.builder()
                .id(5L).player(player(1)).crop(crop).status(FieldStatus.GROWING).build();
        PlayerField empty = PlayerField.builder()
                .id(6L).player(player(1)).status(FieldStatus.EMPTY).build();

        PlayerFieldResponse plantedResponse = mapper.toResponse(planted);
        PlayerFieldResponse emptyResponse = mapper.toResponse(empty);

        assertEquals("Orge du Nord", plantedResponse.cropName());
        assertNull(emptyResponse.cropName());
    }

    @Test
    void inventoryMapperFlattensIngredientMetadata() {
        InventoryMapper mapper = Mappers.getMapper(InventoryMapper.class);
        Ingredient ingredient = ingredient(7, IngredientType.HONEY);
        ingredient.setName("Miel");
        PlayerInventory inventory = PlayerInventory.builder()
                .id(2L).player(player(1)).ingredient(ingredient)
                .quantity(new BigDecimal("3.500")).build();

        PlayerInventoryResponse response = mapper.toPlayerInventoryResponse(inventory);

        assertEquals(7L, response.ingredientId());
        assertEquals("Miel", response.ingredientName());
        assertEquals(IngredientType.HONEY, response.type());
        assertEquals(ingredient.getUnit(), response.unit());
        assertEquals(new BigDecimal("3.500"), response.quantity());
    }

    @Test
    void playerMapperRenamesCoinAndUsesProfilePresentation() {
        PlayerMapper mapper = Mappers.getMapper(PlayerMapper.class);
        PlayerProfile profile = player(7);
        profile.setDisplayName("Eirik");
        profile.setAvatar(Avatar.LOUP);
        profile.setCoin(640);
        profile.setReputation(12);

        PlayerProfileResponse response = mapper.toResponse(profile);

        assertEquals("user7", response.username());
        assertEquals("Eirik", response.displayName());
        assertEquals(Avatar.LOUP, response.avatar());
        assertEquals(640, response.coins());
        assertEquals(12, response.reputation());
    }

    @Test
    void npcOrderMapperMapsRecipeLines() {
        NpcOrderMapper mapper = Mappers.getMapper(NpcOrderMapper.class);
        PlayerProfile player = player(1);
        Recipe recipe = recipe(8);
        NpcOrder order = NpcOrder.builder()
                .id(4L).player(player).customerName("Jarl")
                .createdAt(LocalDateTime.now()).expiresAt(LocalDateTime.now().plusHours(1))
                .status(OrderStatus.OPEN).rewardCoins(100).rewardReputation(5).build();
        NpcOrderLine line = NpcOrderLine.builder()
                .order(order).recipe(recipe).quantity(3).minQuality(70).build();

        NpcOrderResponse response = mapper.toResponse(order, List.of(line));

        assertEquals(1L, response.playerId());
        assertEquals(8L, response.lines().getFirst().recipeId());
        assertEquals(recipe.getName(), response.lines().getFirst().recipeName());
        assertEquals(70, response.lines().getFirst().minQuality());
    }

    @Test
    void playerOrderMapperShowsNpcMerchantWhenRelayed() {
        PlayerOrderMapper mapper = Mappers.getMapper(PlayerOrderMapper.class);
        PlayerProfile creator = player(1);
        Ingredient ingredient = ingredient(7, IngredientType.HONEY);
        PlayerOrder order = PlayerOrder.builder()
                .id(4L).creator(creator)
                .createdAt(LocalDateTime.now()).expiresAt(LocalDateTime.now().plusHours(1))
                .status(OrderStatus.COMPLETED).rewardCoins(100).fulfilledByNpc(true).build();
        PlayerOrderLine line = PlayerOrderLine.builder()
                .order(order).ingredient(ingredient).quantity(BigDecimal.ONE).build();

        PlayerOrderResponse response = mapper.toResponse(order, List.of(line));

        assertTrue(response.fulfilledByNpc());
        assertNull(response.fulfillerId());
        assertEquals("Marchand de passage", response.fulfillerUsername());
        assertEquals(7L, response.lines().getFirst().ingredientId());
    }

    @Test
    void recipeMapperIncludesOwnershipEffectsAndIngredients() {
        RecipeMapper mapper = Mappers.getMapper(RecipeMapper.class);
        PlayerProfile owner = player(2);
        Ingredient honey = ingredient(7, IngredientType.HONEY);
        Recipe recipe = recipe(9);
        recipe.setOwner(owner);
        recipe.setPublic(false);
        recipe.setFermentationDurationMinutes(25);
        recipe.setEffectKind(EffectKind.INSPIRATION);
        recipe.setEffectMagnitude(30);
        recipe.setEffectDurationMinutes(10);
        RecipeIngredient line = RecipeIngredient.builder()
                .recipe(recipe).ingredient(honey).quantity(new BigDecimal("2.000")).build();

        RecipeResponse response = mapper.toResponse(recipe, List.of(line));

        assertEquals(2L, response.ownerId());
        assertEquals("user2", response.ownerUsername());
        assertEquals(25, response.fermentationDurationMinutes());
        assertEquals(EffectKind.INSPIRATION, response.effectKind());
        assertEquals(30, response.effectMagnitude());
        assertEquals(7L, response.ingredients().getFirst().ingredientId());
    }
}
