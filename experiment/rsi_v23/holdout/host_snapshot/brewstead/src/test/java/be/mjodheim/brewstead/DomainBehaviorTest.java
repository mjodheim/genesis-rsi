package be.mjodheim.brewstead;

import be.mjodheim.brewstead.entity.PlayerOrder;
import be.mjodheim.brewstead.entity.PlayerProfile;
import be.mjodheim.brewstead.entity.Recipe;
import be.mjodheim.brewstead.entity.User;
import be.mjodheim.brewstead.enums.Avatar;
import be.mjodheim.brewstead.enums.EffectKind;
import be.mjodheim.brewstead.enums.UserRole;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class DomainBehaviorTest {

    @Test
    void playerProfileFallsBackToUsernameAndDefaultAvatar() {
        User user = TestData.user(1);
        PlayerProfile profile = PlayerProfile.builder().user(user).build();

        assertEquals("user1", profile.getDisplayName());
        assertEquals(Avatar.CERF, profile.getAvatar());

        profile.setDisplayName("Eirik");
        profile.setAvatar(Avatar.LOUP);
        assertEquals("Eirik", profile.getDisplayName());
        assertEquals(Avatar.LOUP, profile.getAvatar());
    }

    @Test
    void recipeProvidesSafeDefaultsAndMinuteOverride() {
        Recipe recipe = Recipe.builder().fermentationDurationHours(2).build();

        assertEquals(120, recipe.getFermentationMinutes());
        assertEquals(EffectKind.AUCUN, recipe.getEffectKind());
        assertEquals(0, recipe.getEffectMagnitude());
        assertEquals(0, recipe.getEffectDurationMinutes());

        recipe.setFermentationDurationMinutes(15);
        assertEquals(15, recipe.getFermentationMinutes());
    }

    @Test
    void playerOrderNpcFlagTreatsNullAsFalse() {
        PlayerOrder order = PlayerOrder.builder().build();

        assertFalse(order.isFulfilledByNpc());
        order.setFulfilledByNpc(true);
        assertTrue(order.isFulfilledByNpc());
    }

    @Test
    void avatarParsingIsNormalizedAndValidated() {
        assertEquals(Avatar.CERF, Avatar.fromNullable(null));
        assertEquals(Avatar.CERF, Avatar.fromNullable(" "));
        assertEquals(Avatar.LOUP, Avatar.fromNullable(" loup "));
        assertThrows(IllegalArgumentException.class, () -> Avatar.fromNullable("dragon"));
    }

    @Test
    void effectKindExposesNarrativeAndBeneficialMetadata() {
        assertTrue(EffectKind.INSPIRATION.isBeneficial());
        assertFalse(EffectKind.MAIN_LOURDE.isBeneficial());
        assertTrue(EffectKind.VISION_DOUBLE.isCosmetic());
        assertFalse(EffectKind.MAIN_VERTE.isCosmetic());
        assertNotNull(EffectKind.BOURDONNEMENT.getLabel());
    }

    @Test
    void userAuthorityMatchesStoredRole() {
        User user = User.builder()
                .username("eirik").password("x").role(UserRole.PLAYER).build();

        assertEquals(1, user.getAuthorities().size());
        assertEquals("PLAYER", user.getAuthorities().iterator().next().getAuthority());
    }
}
