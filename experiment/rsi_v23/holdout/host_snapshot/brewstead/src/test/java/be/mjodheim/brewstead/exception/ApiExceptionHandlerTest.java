package be.mjodheim.brewstead.exception;

import be.mjodheim.brewstead.dto.error.ApiError;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ApiExceptionHandlerTest {

    private final ApiExceptionHandler handler = new ApiExceptionHandler();

    @Test
    void illegalArgumentMapsToBadRequest() {
        ResponseEntity<ApiError> response =
                handler.handleBadRequest(new IllegalArgumentException("mauvaise requête"));

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertNotNull(response.getBody());
        assertEquals(400, response.getBody().status());
        assertEquals("mauvaise requête", response.getBody().message());
    }

    @Test
    void accessDeniedMapsToForbidden() {
        ResponseEntity<ApiError> response =
                handler.handleForbidden(new AccessDeniedException("interdit"));

        assertEquals(HttpStatus.FORBIDDEN, response.getStatusCode());
        assertEquals("interdit", response.getBody().message());
    }

    @Test
    void businessExceptionsMapToConflict() {
        RuntimeException[] exceptions = {
                new IllegalStateException("état"),
                new IngredientNotInInventoryException("absent"),
                new InsufficientStockException("stock"),
                new InsufficientCoinsException("pièces")
        };

        for (RuntimeException exception : exceptions) {
            ResponseEntity<ApiError> response = handler.handleConflict(exception);
            assertEquals(HttpStatus.CONFLICT, response.getStatusCode());
            assertEquals(exception.getMessage(), response.getBody().message());
        }
    }

    @Test
    void validationUsesFirstMeaningfulFieldMessage() {
        MethodArgumentNotValidException exception = mock(MethodArgumentNotValidException.class);
        BindingResult binding = mock(BindingResult.class);
        when(exception.getBindingResult()).thenReturn(binding);
        when(binding.getFieldErrors()).thenReturn(List.of(
                new FieldError("form", "first", " "),
                new FieldError("form", "second", "Message lisible")
        ));

        ResponseEntity<ApiError> response = handler.handleInvalid(exception);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertEquals("Message lisible", response.getBody().message());
    }

    @Test
    void validationFallsBackWhenNoMessageExists() {
        MethodArgumentNotValidException exception = mock(MethodArgumentNotValidException.class);
        BindingResult binding = mock(BindingResult.class);
        when(exception.getBindingResult()).thenReturn(binding);
        when(binding.getFieldErrors()).thenReturn(List.of(
                new FieldError("form", "field", null, false, null, null, null)
        ));

        ResponseEntity<ApiError> response = handler.handleInvalid(exception);

        assertEquals("Requête invalide.", response.getBody().message());
    }
}
