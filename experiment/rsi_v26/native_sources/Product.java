package be.mjodheim.cellar.catalog.internal.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Objects;

/**
 * Business representation of a product offered in the Mjödheim catalogue.
 *
 * <p>This class deliberately contains no JPA or HTTP concerns. It protects the
 * product invariants and is persisted through a dedicated adapter.</p>
 */
public final class Product {

    private final Long id;

    private String name;
    private ProductType type;
    private String description;
    private int volumeMl;
    private BigDecimal price;
    private boolean active;

    private final Instant createdAt;
    private Instant updatedAt;

    private Product(
            Long id,
            String name,
            ProductType type,
            String description,
            int volumeMl,
            BigDecimal price,
            boolean active,
            Instant createdAt,
            Instant updatedAt
    ) {
        this.id = id;
        this.createdAt = Objects.requireNonNull(createdAt);
        this.updatedAt = Objects.requireNonNull(updatedAt);
        this.active = active;

        applyDetails(name, type, description, volumeMl, price);
    }

    /**
     * Creates a new active product that has not yet been persisted.
     *
     * @param name product name
     * @param type product family
     * @param description optional description
     * @param volumeMl container volume in millilitres
     * @param price unit price
     * @param now creation timestamp
     * @return new domain product
     */
    public static Product create(
            String name,
            ProductType type,
            String description,
            int volumeMl,
            BigDecimal price,
            Instant now
    ) {
        Objects.requireNonNull(now);

        return new Product(
                null,
                name,
                type,
                description,
                volumeMl,
                price,
                true,
                now,
                now
        );
    }

    /**
     * Rebuilds a product from persistence without treating it as a new product.
     *
     * @param id persisted identifier
     * @param name product name
     * @param type product family
     * @param description optional description
     * @param volumeMl container volume in millilitres
     * @param price unit price
     * @param active whether the product is currently active
     * @param createdAt original creation timestamp
     * @param updatedAt last modification timestamp
     * @return rehydrated domain product
     */
    public static Product rehydrate(
            Long id,
            String name,
            ProductType type,
            String description,
            int volumeMl,
            BigDecimal price,
            boolean active,
            Instant createdAt,
            Instant updatedAt
    ) {
        return new Product(
                id,
                name,
                type,
                description,
                volumeMl,
                price,
                active,
                createdAt,
                updatedAt
        );
    }

    /**
     * Replaces the editable commercial details while preserving identity and creation time.
     *
     * @param name new product name
     * @param type new product family
     * @param description new optional description
     * @param volumeMl new container volume in millilitres
     * @param price new unit price
     * @param now modification timestamp
     */
    public void changeDetails(
            String name,
            ProductType type,
            String description,
            int volumeMl,
            BigDecimal price,
            Instant now
    ) {
        applyDetails(name, type, description, volumeMl, price);
        this.updatedAt = Objects.requireNonNull(now);
    }

    /**
     * Deactivates the product so it can no longer be used for new orders.
     *
     * <p>The operation is idempotent and intentionally does not delete historical data.</p>
     *
     * @param now modification timestamp
     */
    public void deactivate(Instant now) {
        if (!active) {
            return;
        }

        this.active = false;
        this.updatedAt = Objects.requireNonNull(now);
    }

    private void applyDetails(
            String name,
            ProductType type,
            String description,
            int volumeMl,
            BigDecimal price
    ) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("Product name is required");
        }

        if (type == null) {
            throw new IllegalArgumentException("Product type is required");
        }

        if (volumeMl <= 0) {
            throw new IllegalArgumentException("Product volume must be greater than zero");
        }

        if (price == null || price.signum() < 0) {
            throw new IllegalArgumentException("Product price cannot be negative");
        }

        this.name = name.trim();
        this.type = type;
        this.description = description;
        this.volumeMl = volumeMl;
        this.price = price;
    }

    /** @return persisted identifier, or {@code null} before persistence */
    public Long id() { return id; }

    /** @return normalized product name */
    public String name() { return name; }

    /** @return product family */
    public ProductType type() { return type; }

    /** @return optional description */
    public String description() { return description; }

    /** @return container volume in millilitres */
    public int volumeMl() { return volumeMl; }

    /** @return current unit price */
    public BigDecimal price() { return price; }

    /** @return whether the product is active */
    public boolean active() { return active; }

    /** @return creation timestamp */
    public Instant createdAt() { return createdAt; }

    /** @return last modification timestamp */
    public Instant updatedAt() { return updatedAt; }
}
