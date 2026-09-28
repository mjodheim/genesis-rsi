package be.mjodheim.brewstead.exception;

public class InsufficientCoinsException extends RuntimeException {

    public InsufficientCoinsException(String message) {
        super(message);
    }
}
