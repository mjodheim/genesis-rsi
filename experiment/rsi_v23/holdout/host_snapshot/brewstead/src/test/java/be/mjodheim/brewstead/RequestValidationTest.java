package be.mjodheim.brewstead;

import be.mjodheim.brewstead.dto.account.ChangePasswordRequest;
import be.mjodheim.brewstead.dto.account.RegisterForm;
import be.mjodheim.brewstead.dto.account.UpdateAccountRequest;
import be.mjodheim.brewstead.dto.tavern.OpenOfferRequest;
import be.mjodheim.brewstead.dto.tavern.PostMessageRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class RequestValidationTest {

    private static jakarta.validation.ValidatorFactory factory;
    private static Validator validator;

    @BeforeAll
    static void setUpValidator() {
        factory = Validation.buildDefaultValidatorFactory();
        validator = factory.getValidator();
    }

    @AfterAll
    static void closeValidator() {
        factory.close();
    }

    @Test
    void registrationFormRejectsInvalidUsernameAndShortPassword() {
        RegisterForm form = new RegisterForm();
        form.setUsername("a!");
        form.setPassword("short");
        form.setConfirmation("");

        Set<ConstraintViolation<RegisterForm>> violations = validator.validate(form);

        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("username")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("confirmation")));
    }

    @Test
    void registrationFormAcceptsValidValues() {
        RegisterForm form = new RegisterForm();
        form.setUsername("Eirik_7");
        form.setPassword("secret123");
        form.setConfirmation("secret123");

        assertTrue(validator.validate(form).isEmpty());
    }

    @Test
    void changePasswordRequiresEightCharacterNewPassword() {
        ChangePasswordRequest request = new ChangePasswordRequest("oldSecret", "short", "short");

        assertTrue(validator.validate(request).stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("newPassword")));
    }

    @Test
    void accountDisplayNameCannotExceedThirtyCharacters() {
        UpdateAccountRequest request = new UpdateAccountRequest("x".repeat(31), "CERF");

        assertFalse(validator.validate(request).isEmpty());
    }

    @Test
    void tastingOfferEnforcesServingAndPriceBounds() {
        OpenOfferRequest invalid = new OpenOfferRequest(1L, 0, -1, "note");
        Set<ConstraintViolation<OpenOfferRequest>> violations = validator.validate(invalid);

        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("servings")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("price")));

        OpenOfferRequest valid = new OpenOfferRequest(1L, 40, 5000, "Skål");
        assertTrue(validator.validate(valid).isEmpty());
    }

    @Test
    void chatMessageRejectsBlankAndOversizedBody() {
        assertFalse(validator.validate(new PostMessageRequest(" ")).isEmpty());
        assertFalse(validator.validate(new PostMessageRequest("x".repeat(281))).isEmpty());
        assertTrue(validator.validate(new PostMessageRequest("Skål !")).isEmpty());
    }
}
