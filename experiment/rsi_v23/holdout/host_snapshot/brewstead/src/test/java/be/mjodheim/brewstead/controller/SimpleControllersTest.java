package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.account.ChangePasswordRequest;
import be.mjodheim.brewstead.dto.account.RegisterForm;
import be.mjodheim.brewstead.dto.account.UpdateAccountRequest;
import be.mjodheim.brewstead.dto.effect.PlayerEffectResponse;
import be.mjodheim.brewstead.enums.Avatar;
import be.mjodheim.brewstead.service.*;
import org.junit.jupiter.api.Test;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.validation.ObjectError;

import java.security.Principal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SimpleControllersTest {

    private final Principal principal = () -> "eirik";

    @Test
    void accountControllerDelegatesUsingPrincipalName() {
        AccountService account = mock(AccountService.class);
        EffectService effects = mock(EffectService.class);
        AccountController controller = new AccountController(account, effects);
        UpdateAccountRequest update = new UpdateAccountRequest("Eirik", "LOUP");
        ChangePasswordRequest password = new ChangePasswordRequest("oldSecret", "newSecret1", "newSecret1");
        when(account.currentPlayerId("eirik")).thenReturn(7L);

        controller.me(principal);
        controller.update(principal, update);
        controller.changePassword(principal, password);
        controller.effects(principal);

        verify(account).currentAccount("eirik");
        verify(account).updateAccount("eirik", update);
        verify(account).changePassword("eirik", password);
        verify(effects).activeEffects(7L);
        assertEquals(Avatar.values().length, controller.avatars().size());
    }

    @Test
    void catalogTavernAndGameControllersAreSimpleDelegates() {
        CatalogService catalog = mock(CatalogService.class);
        CatalogController catalogController = new CatalogController(catalog);
        catalogController.ingredients();
        catalogController.crops();
        verify(catalog).findAllIngredients();
        verify(catalog).findAllCrops();

        TavernService tavern = mock(TavernService.class);
        new TavernController(tavern).tavern();
        verify(tavern).getTavern();

        assertEquals("game/brewstead-world", new GameController().home());
    }

    @Test
    void authViewRendersFormsAndSuccessfulRegistrationRedirect() {
        RegistrationService registration = mock(RegistrationService.class);
        AuthViewController controller = new AuthViewController(registration);
        Model model = mock(Model.class);
        BindingResult binding = mock(BindingResult.class);
        RegisterForm form = new RegisterForm();

        assertEquals("auth/login", controller.login());
        assertEquals("auth/register", controller.registerForm(model));
        verify(model).addAttribute(eq("form"), any(RegisterForm.class));

        when(binding.hasErrors()).thenReturn(false);
        assertEquals("redirect:/login?registered",
                controller.register(form, binding, model));
        verify(registration).register(form);
    }

    @Test
    void authViewReturnsValidationAndRegistrationErrors() {
        RegistrationService registration = mock(RegistrationService.class);
        AuthViewController controller = new AuthViewController(registration);
        Model model = mock(Model.class);
        BindingResult binding = mock(BindingResult.class);
        RegisterForm form = new RegisterForm();
        ObjectError error = new ObjectError("form", "Nom invalide");

        when(binding.hasErrors()).thenReturn(true);
        when(binding.getAllErrors()).thenReturn(List.of(error));
        assertEquals("auth/register", controller.register(form, binding, model));
        verify(model).addAttribute("error", "Nom invalide");
        verifyNoInteractions(registration);

        reset(binding, model, registration);
        when(binding.hasErrors()).thenReturn(false);
        doThrow(new IllegalArgumentException("Déjà pris")).when(registration).register(form);
        assertEquals("auth/register", controller.register(form, binding, model));
        verify(model).addAttribute("error", "Déjà pris");
    }
}
