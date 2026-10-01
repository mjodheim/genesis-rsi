package be.mjodheim.cellar.inventory.internal.domain;

import java.time.Instant;
import java.time.LocalDate;
import java.util.Objects;

/**
 * Physical stock lot belonging to a catalogue product.
 *
 * <p>A batch owns the current on-hand and reserved quantities and enforces
 * stock invariants. Soft-deleted batches remain available for historical
 * traceability but can no longer be modified.</p>
 */
public final class Batch {

    private final Long id;
    private final Long productId;
    private final String lotNumber;
    private final int receivedQuantity;
    private final Instant receivedAt;
    private final LocalDate expiresOn;
    private final Instant createdAt;

    private int quantityOnHand;
    private int quantityReserved;
    private Instant updatedAt;
    private Instant deletedAt;

    private Batch(Long id, Long productId, String lotNumber, int receivedQuantity, int quantityOnHand,
                  int quantityReserved, Instant receivedAt, LocalDate expiresOn, Instant createdAt,
                  Instant updatedAt, Instant deletedAt) {
        if (productId == null || productId <= 0) throw new IllegalArgumentException("Product id must be positive");
        if (lotNumber == null || lotNumber.isBlank()) throw new IllegalArgumentException("Lot number is required");
        if (receivedQuantity <= 0) throw new IllegalArgumentException("Received quantity must be greater than zero");
        if (quantityOnHand < 0) throw new IllegalArgumentException("Quantity on hand cannot be negative");
        if (quantityReserved < 0 || quantityReserved > quantityOnHand)
            throw new IllegalArgumentException("Reserved quantity must be between zero and quantity on hand");

        this.id=id; this.productId=productId; this.lotNumber=lotNumber.trim(); this.receivedQuantity=receivedQuantity;
        this.quantityOnHand=quantityOnHand; this.quantityReserved=quantityReserved;
        this.receivedAt=Objects.requireNonNull(receivedAt, "Received date is required");
        this.expiresOn=expiresOn;
        this.createdAt=Objects.requireNonNull(createdAt, "Creation date is required");
        this.updatedAt=Objects.requireNonNull(updatedAt, "Update date is required");
        this.deletedAt=deletedAt;
    }

    /**
     * Creates a newly received batch.
     *
     * @param productId product identifier
     * @param lotNumber lot reference
     * @param quantity received quantity
     * @param receivedAt reception timestamp
     * @param expiresOn optional expiration date
     * @param now creation timestamp
     * @return new batch aggregate
     */
    public static Batch receive(Long productId, String lotNumber, int quantity, Instant receivedAt, LocalDate expiresOn, Instant now) {
        Objects.requireNonNull(now, "Current date is required");
        if (expiresOn != null && expiresOn.isBefore(receivedAt.atZone(java.time.ZoneOffset.UTC).toLocalDate()))
            throw new IllegalArgumentException("Expiration date cannot be before reception date");
        return new Batch(null, productId, lotNumber, quantity, quantity, 0, receivedAt, expiresOn, now, now, null);
    }

    /**
     * Rebuilds a batch from persisted state.
     *
     * @param id persisted identifier
     * @param productId product identifier
     * @param lotNumber lot reference
     * @param receivedQuantity original received quantity
     * @param quantityOnHand current physical quantity
     * @param quantityReserved current reserved quantity
     * @param receivedAt reception timestamp
     * @param expiresOn optional expiration date
     * @param createdAt creation timestamp
     * @param updatedAt last modification timestamp
     * @param deletedAt soft-delete timestamp, or {@code null}
     * @return rehydrated batch
     */
    public static Batch rehydrate(Long id, Long productId, String lotNumber, int receivedQuantity, int quantityOnHand,
                                  int quantityReserved, Instant receivedAt, LocalDate expiresOn,
                                  Instant createdAt, Instant updatedAt, Instant deletedAt) {
        return new Batch(id, productId, lotNumber, receivedQuantity, quantityOnHand, quantityReserved,
                receivedAt, expiresOn, createdAt, updatedAt, deletedAt);
    }

    /** Reserves available stock. @param quantity quantity to reserve @param now modification timestamp */
    public void reserve(int quantity, Instant now) {
        ensureNotDeleted(); requirePositive(quantity);
        if (quantity > availableQuantity()) throw new IllegalStateException("Not enough available stock to reserve");
        quantityReserved += quantity; updatedAt = Objects.requireNonNull(now);
    }

    /** Releases reserved stock. @param quantity quantity to release @param now modification timestamp */
    public void release(int quantity, Instant now) {
        ensureNotDeleted(); requirePositive(quantity);
        if (quantity > quantityReserved) throw new IllegalStateException("Cannot release more than reserved quantity");
        quantityReserved -= quantity; updatedAt = Objects.requireNonNull(now);
    }

    /** Ships already reserved stock. @param quantity quantity to ship @param now modification timestamp */
    public void shipReserved(int quantity, Instant now) {
        ensureNotDeleted(); requirePositive(quantity);
        if (quantity > quantityReserved) throw new IllegalStateException("Cannot ship more than reserved quantity");
        quantityReserved -= quantity; quantityOnHand -= quantity; updatedAt = Objects.requireNonNull(now);
    }

    /** Adds physical stock. @param quantity quantity to add @param now modification timestamp */
    public void addStock(int quantity, Instant now) {
        ensureNotDeleted(); requirePositive(quantity);
        quantityOnHand += quantity; updatedAt = Objects.requireNonNull(now);
    }

    /** Removes unreserved physical stock. @param quantity quantity to remove @param now modification timestamp */
    public void removeAvailableStock(int quantity, Instant now) {
        ensureNotDeleted(); requirePositive(quantity);
        if (quantity > availableQuantity()) throw new IllegalStateException("Cannot remove more than available quantity");
        quantityOnHand -= quantity; updatedAt = Objects.requireNonNull(now);
    }

    /** Soft-deletes an empty, unreserved batch. @param now deletion timestamp */
    public void softDelete(Instant now) {
        if (deletedAt != null) return;
        if (quantityOnHand != 0 || quantityReserved != 0)
            throw new IllegalStateException("A batch with stock or reservations cannot be deleted");
        deletedAt = Objects.requireNonNull(now); updatedAt = now;
    }

    /** @return physical quantity not currently reserved */
    public int availableQuantity() { return quantityOnHand - quantityReserved; }

    /** @return {@code true} when the batch has been soft-deleted */
    public boolean isDeleted() { return deletedAt != null; }

    private void ensureNotDeleted() {
        if (isDeleted()) throw new IllegalStateException("Deleted batch cannot be modified");
    }

    private static void requirePositive(int quantity) {
        if (quantity <= 0) throw new IllegalArgumentException("Quantity must be greater than zero");
    }

    /** @return persisted identifier, or {@code null} before persistence */
    public Long id() { return id; }
    /** @return related product identifier */
    public Long productId() { return productId; }
    /** @return lot reference */
    public String lotNumber() { return lotNumber; }
    /** @return original received quantity */
    public int receivedQuantity() { return receivedQuantity; }
    /** @return current physical quantity */
    public int quantityOnHand() { return quantityOnHand; }
    /** @return currently reserved quantity */
    public int quantityReserved() { return quantityReserved; }
    /** @return reception timestamp */
    public Instant receivedAt() { return receivedAt; }
    /** @return expiration date, or {@code null} */
    public LocalDate expiresOn() { return expiresOn; }
    /** @return creation timestamp */
    public Instant createdAt() { return createdAt; }
    /** @return last modification timestamp */
    public Instant updatedAt() { return updatedAt; }
    /** @return soft-delete timestamp, or {@code null} */
    public Instant deletedAt() { return deletedAt; }
}
