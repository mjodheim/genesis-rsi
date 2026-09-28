package be.mjodheim.brewstead.integration;

import be.mjodheim.brewstead.entity.*;
import be.mjodheim.brewstead.enums.BatchStatus;
import be.mjodheim.brewstead.enums.BehiveStatus;
import be.mjodheim.brewstead.enums.FieldStatus;
import be.mjodheim.brewstead.enums.IngredientType;
import be.mjodheim.brewstead.enums.OrderStatus;
import be.mjodheim.brewstead.repository.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestBuilders.formLogin;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.response.SecurityMockMvcResultMatchers.authenticated;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class GameJourneyIntegrationTest {

    @Autowired MockMvc mockMvc;
    @Autowired UserRepository userRepository;
    @Autowired PlayerProfileRepository playerRepository;
    @Autowired PlayerFieldRepository fieldRepository;
    @Autowired BeehiveRepository hiveRepository;
    @Autowired CropRepository cropRepository;
    @Autowired IngredientRepository ingredientRepository;
    @Autowired PlayerInventoryRepository inventoryRepository;
    @Autowired RecipeRepository recipeRepository;
    @Autowired RecipeIngredientRepository recipeIngredientRepository;
    @Autowired BatchRepository batchRepository;
    @Autowired TastingOfferRepository tastingOfferRepository;
    @Autowired PlayerOrderRepository playerOrderRepository;
    @Autowired TavernMessageRepository tavernMessageRepository;
    @Autowired PlayerProgressRepository progressRepository;

    @Test
    void fullTwoPlayerJourneyUsesRealPostgresAndSecurity() throws Exception {
        String alphaName = "it_alpha";
        String betaName = "it_beta";
        String password = "Secret123!";

        register(alphaName, password);
        register(betaName, password);

        MockHttpSession alpha = login(alphaName, password);
        MockHttpSession beta = login(betaName, password);

        PlayerProfile alphaPlayer = profile(alphaName);
        PlayerProfile betaPlayer = profile(betaName);

        alphaPlayer.setLevel(2);
        playerRepository.save(alphaPlayer);

        mockMvc.perform(post("/api/progression/specialization")
                        .session(alpha).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"specialization\":\"BRASSEUR\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.specializations[1].selected").value(true));

        mockMvc.perform(put("/api/progression/theme")
                        .session(alpha).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"theme\":\"HIVER\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.themes[2].selected").value(true))
                .andExpect(jsonPath("$.season.milestones.length()").value(3));

        assertEquals("BRASSEUR", progressRepository.findByPlayerId(alphaPlayer.getId())
                .orElseThrow().getSpecialization().name());

        mockMvc.perform(get("/api/account/me").session(alpha))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(alphaPlayer.getId()))
                .andExpect(jsonPath("$.username").value(alphaName));

        mockMvc.perform(get("/api/players/{id}/state", alphaPlayer.getId()).session(alpha))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fields.length()").value(3))
                .andExpect(jsonPath("$.hives.length()").value(2))
                .andExpect(jsonPath("$.inventory.length()").value(greaterThanOrEqualTo(5)))
                .andExpect(jsonPath("$.recipes.length()").value(greaterThanOrEqualTo(1)));

        mockMvc.perform(get("/api/players/{id}/state", betaPlayer.getId()).session(alpha))
                .andExpect(status().isForbidden());

        Ingredient catalogIngredient = ingredientRepository.findAll().stream()
                .findFirst()
                .orElseThrow();

        String privateName = "Recette privée intégration";
        String privateRecipeJson = """
                {
                  "ownerId": %d,
                  "name": "%s",
                  "drinkType": "MEAD",
                  "baseVolume": 1.00,
                  "fermentationDurationHours": 1,
                  "ingredients": [
                    {"ingredientId": %d, "quantity": 0.100}
                  ]
                }
                """.formatted(alphaPlayer.getId(), privateName, catalogIngredient.getId());

        mockMvc.perform(post("/api/recipes")
                        .session(alpha)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(privateRecipeJson))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ownerId").value(alphaPlayer.getId()))
                .andExpect(jsonPath("$.isPublic").value(false));

        Recipe privateRecipe = recipeRepository.findAll().stream()
                .filter(recipe -> privateName.equals(recipe.getName()))
                .findFirst()
                .orElseThrow();

        mockMvc.perform(get("/api/recipes/{recipeId}/players/{playerId}",
                        privateRecipe.getId(), betaPlayer.getId())
                        .session(beta))
                .andExpect(status().isConflict());

        String spoofedOwnerJson = """
                {
                  "ownerId": %d,
                  "name": "Recette usurpée",
                  "drinkType": "MEAD",
                  "baseVolume": 1.00,
                  "fermentationDurationHours": 1,
                  "ingredients": [
                    {"ingredientId": %d, "quantity": 0.100}
                  ]
                }
                """.formatted(betaPlayer.getId(), catalogIngredient.getId());

        mockMvc.perform(post("/api/recipes")
                        .session(alpha)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(spoofedOwnerJson))
                .andExpect(status().isForbidden());

        PlayerField field = fieldRepository.findAllByPlayerId(alphaPlayer.getId()).stream()
                .filter(candidate -> candidate.getStatus() == FieldStatus.EMPTY)
                .findFirst()
                .orElseThrow();
        Crop crop = cropRepository.findAll().stream().findFirst().orElseThrow();
        BigDecimal cropStockBefore = stock(alphaPlayer, crop.getIngredient());

        mockMvc.perform(post("/api/farm/plant")
                        .session(alpha)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"fieldId": %d, "cropId": %d}
                                """.formatted(field.getId(), crop.getId())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("GROWING"));

        field = fieldRepository.findById(field.getId()).orElseThrow();
        field.setReadyAt(LocalDateTime.now().minusSeconds(1));
        fieldRepository.save(field);

        mockMvc.perform(post("/api/farm/fields/{id}/harvest", field.getId())
                        .session(alpha)
                        .with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("EMPTY"));

        assertTrue(stock(alphaPlayer, crop.getIngredient()).compareTo(cropStockBefore) > 0);

        // Les ruches n'attendent plus qu'on les réveille : elles produisent
        // dès qu'on les regarde, et repartent seules après la récolte.
        mockMvc.perform(get("/api/apiary/players/{playerId}/hives", alphaPlayer.getId()).session(alpha))
                .andExpect(status().isOk());

        Beehive hive = hiveRepository.findAllByPlayerId(alphaPlayer.getId()).stream()
                .filter(candidate -> candidate.getStatus() == BehiveStatus.PRODUCING)
                .findFirst()
                .orElseThrow();

        hive.setReadyAt(LocalDateTime.now().minusSeconds(1));
        hiveRepository.save(hive);

        Ingredient honey = ingredientRepository.findFirstByType(IngredientType.HONEY).orElseThrow();
        BigDecimal honeyBefore = stock(alphaPlayer, honey);

        mockMvc.perform(post("/api/apiary/hives/{id}/harvest", hive.getId())
                        .session(alpha)
                        .with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PRODUCING"));

        BigDecimal levelOneYield = stock(alphaPlayer, honey).subtract(honeyBefore);
        assertTrue(levelOneYield.compareTo(BigDecimal.ZERO) > 0);

        // Le domaine s'agrandit : c'est la seule sortie des pièces, et le
        // niveau de ruche — écrit dans le modèle depuis le début — commence
        // enfin à bouger.
        PlayerProfile purse = playerRepository.findById(alphaPlayer.getId()).orElseThrow();
        purse.setCoin(9_000);
        playerRepository.save(purse);

        mockMvc.perform(get("/api/players/{id}/state", alphaPlayer.getId()).session(alpha))
                .andExpect(jsonPath("$.estate.fields").value(3))
                .andExpect(jsonPath("$.estate.fieldPrice").value(400))
                .andExpect(jsonPath("$.estate.hives").value(2))
                .andExpect(jsonPath("$.estate.hivePrice").value(500));

        mockMvc.perform(post("/api/farm/fields").session(alpha).with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(4));

        mockMvc.perform(post("/api/apiary/hives").session(alpha).with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(3));

        mockMvc.perform(post("/api/apiary/hives/{id}/upgrade", hive.getId())
                        .session(alpha).with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.level").value(2));

        assertEquals(9_000 - 400 - 500 - 700,
                playerRepository.findById(alphaPlayer.getId()).orElseThrow().getCoin(),
                "le défrichage, la ruche et l'agrandissement se paient");

        // La ruche agrandie rapporte le double : la formule de rendement
        // existait déjà, rien ne l'avait jamais activée.
        Beehive upgraded = hiveRepository.findById(hive.getId()).orElseThrow();
        upgraded.setReadyAt(LocalDateTime.now().minusSeconds(1));
        hiveRepository.save(upgraded);
        BigDecimal beforeSecond = stock(alphaPlayer, honey);

        mockMvc.perform(post("/api/apiary/hives/{id}/harvest", hive.getId())
                        .session(alpha).with(csrf()))
                .andExpect(status().isOk());

        assertEquals(0, stock(alphaPlayer, honey).subtract(beforeSecond)
                        .compareTo(levelOneYield.multiply(BigDecimal.valueOf(2))),
                "une ruche de niveau 2 doit rendre deux fois plus de miel");

        Recipe brewable = findBrewableRecipe(alphaPlayer);

        mockMvc.perform(post("/api/brewery/batches")
                        .session(alpha)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"playerId": %d, "recipeId": %d, "volume": %s}
                                """.formatted(alphaPlayer.getId(), brewable.getId(), brewable.getBaseVolume().toPlainString())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("BREWING"));

        Batch batch = batchRepository.findAllByPlayerIdOrderByStartedAtDesc(alphaPlayer.getId())
                .stream().findFirst().orElseThrow();
        batch.setReadyAt(LocalDateTime.now().minusSeconds(1));
        batchRepository.save(batch);

        mockMvc.perform(post("/api/brewery/batches/{id}/refresh", batch.getId())
                        .session(alpha)
                        .with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("READY"))
                .andExpect(jsonPath("$.quality").isNumber());

        BigDecimal volumeBeforeTaste = batchRepository.findById(batch.getId()).orElseThrow().getVolume();
        mockMvc.perform(post("/api/brewery/batches/{id}/taste", batch.getId())
                        .session(alpha)
                        .with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recipeName").value(brewable.getName()));

        Batch tasted = batchRepository.findById(batch.getId()).orElseThrow();
        assertTrue(tasted.getVolume().compareTo(volumeBeforeTaste) < 0);

        if (tasted.getStatus() == BatchStatus.READY
                && tasted.getVolume().compareTo(new BigDecimal("0.50")) >= 0) {
            mockMvc.perform(post("/api/tavern/counter")
                            .session(alpha)
                            .with(csrf())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"batchId": %d, "servings": 1, "price": 1, "note": "Test intégration"}
                                    """.formatted(tasted.getId())))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.servings").value(1));

            TastingOffer offer = tastingOfferRepository.findAll().stream()
                    .filter(candidate -> candidate.getSeller().getId().equals(alphaPlayer.getId()))
                    .max(Comparator.comparing(TastingOffer::getId))
                    .orElseThrow();

            int betaCoinsBefore = playerRepository.findById(betaPlayer.getId()).orElseThrow().getCoin();

            mockMvc.perform(post("/api/tavern/counter/{id}/serve", offer.getId())
                            .session(beta)
                            .with(csrf()))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.recipeName").value(brewable.getName()));

            assertEquals(betaCoinsBefore - 1,
                    playerRepository.findById(betaPlayer.getId()).orElseThrow().getCoin());
            assertEquals(0, tastingOfferRepository.findById(offer.getId()).orElseThrow().getServings());
        }

        PlayerInventory betaStock = inventoryRepository.findAllByPlayerId(betaPlayer.getId()).stream()
                .filter(line -> line.getQuantity().compareTo(new BigDecimal("0.100")) >= 0)
                .findFirst()
                .orElseThrow();

        mockMvc.perform(post("/api/player-orders")
                        .session(alpha)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "creatorId": %d,
                                  "rewardCoins": 20,
                                  "expiresInMinutes": 60,
                                  "lines": [{"ingredientId": %d, "quantity": 0.100}]
                                }
                                """.formatted(alphaPlayer.getId(), betaStock.getIngredient().getId())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("OPEN"));

        PlayerOrder order = playerOrderRepository.findAllByCreatorIdOrderByCreatedAtDesc(alphaPlayer.getId())
                .stream().findFirst().orElseThrow();

        mockMvc.perform(post("/api/player-orders/{id}/fulfill", order.getId())
                        .session(beta)
                        .with(csrf()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"))
                .andExpect(jsonPath("$.fulfillerId").value(betaPlayer.getId()));

        assertEquals(OrderStatus.COMPLETED,
                playerOrderRepository.findById(order.getId()).orElseThrow().getStatus());

        mockMvc.perform(post("/api/tavern/chat")
                        .session(alpha)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"body": "Skål depuis le test d'intégration"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.authorId").value(alphaPlayer.getId()));

        mockMvc.perform(get("/api/tavern/chat").session(beta))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("Skål depuis le test d'intégration")));

        assertTrue(tavernMessageRepository.count() >= 1);

        mockMvc.perform(put("/api/account/me")
                        .session(alpha)
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"displayName": "Eirik Integration", "avatar": "LOUP"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.displayName").value("Eirik Integration"))
                .andExpect(jsonPath("$.avatar").value("LOUP"));
    }

    private void register(String username, String password) throws Exception {
        mockMvc.perform(post("/register")
                        .with(csrf())
                        .param("username", username)
                        .param("password", password)
                        .param("confirmation", password))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/login?registered"));
    }

    private MockHttpSession login(String username, String password) throws Exception {
        MvcResult result = mockMvc.perform(formLogin()
                        .user(username)
                        .password(password))
                .andExpect(authenticated().withUsername(username))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrl("/"))
                .andReturn();
        return (MockHttpSession) result.getRequest().getSession(false);
    }

    private PlayerProfile profile(String username) {
        User user = userRepository.findByUsername(username).orElseThrow();
        return playerRepository.findByUserId(user.getId()).orElseThrow();
    }

    private BigDecimal stock(PlayerProfile player, Ingredient ingredient) {
        return inventoryRepository.findByPlayerAndIngredient(player, ingredient)
                .map(PlayerInventory::getQuantity)
                .orElse(BigDecimal.ZERO);
    }

    private Recipe findBrewableRecipe(PlayerProfile player) {
        Map<Long, BigDecimal> stock = inventoryRepository.findAllByPlayerId(player.getId()).stream()
                .collect(Collectors.toMap(
                        line -> line.getIngredient().getId(),
                        PlayerInventory::getQuantity,
                        BigDecimal::add
                ));

        return recipeRepository.findAllByIsPublicTrue().stream()
                .filter(recipe -> recipe.getBaseVolume().compareTo(BigDecimal.ONE) >= 0)
                .filter(recipe -> {
                    List<RecipeIngredient> lines = recipeIngredientRepository.findAllByRecipeId(recipe.getId());
                    return !lines.isEmpty() && lines.stream().allMatch(line ->
                            stock.getOrDefault(line.getIngredient().getId(), BigDecimal.ZERO)
                                    .compareTo(line.getQuantity()) >= 0);
                })
                .findFirst()
                .orElseThrow(() -> new AssertionError("Aucune recette publique brassable avec le stock de départ."));
    }
}
