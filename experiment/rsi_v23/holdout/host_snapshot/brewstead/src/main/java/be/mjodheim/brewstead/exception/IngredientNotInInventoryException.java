package be.mjodheim.brewstead.exception;

public class IngredientNotInInventoryException extends RuntimeException {
    public IngredientNotInInventoryException(String message) {
        super(message);
    }
}
