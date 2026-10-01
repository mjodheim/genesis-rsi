package be.mjodheim.cellar.ordering.internal.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Objects;

/**
 * Immutable commercial snapshot of a product inside an order.
 *
 * <p>The product name and unit price are copied at order creation time so
 * historical orders remain accurate even if the catalogue changes later.</p>
 */
public final class OrderLine {

    private final Long id;
    private final Long productId;
    private final String productName;
    private final int quantity;
    private final BigDecimal unitPrice;
    private final Instant createdAt;

    private OrderLine(Long id, Long productId, String productName, int quantity, BigDecimal unitPrice, Instant createdAt) {
        if (productId == null || productId <= 0) throw new IllegalArgumentException("Product id must be positive");
        if (productName == null || productName.isBlank()) throw new IllegalArgumentException("Product name is required");
        if (quantity <= 0) throw new IllegalArgumentException("Quantity must be greater than zero");
        if (unitPrice == null || unitPrice.signum() < 0) throw new IllegalArgumentException("Unit price cannot be negative");
        this.id=id; this.productId=productId; this.productName=productName.trim(); this.quantity=quantity;
        this.unitPrice=unitPrice; this.createdAt=Objects.requireNonNull(createdAt);
    }

    /**
     * Creates a new commercial snapshot line.
     *
     * @param productId product identifier
     * @param productName product name snapshot
     * @param quantity ordered quantity
     * @param unitPrice unit price snapshot
     * @param now creation timestamp
     * @return new order line
     */
    public static OrderLine create(Long productId, String productName, int quantity, BigDecimal unitPrice, Instant now) {
        return new OrderLine(null, productId, productName, quantity, unitPrice, now);
    }

    /**
     * Rebuilds a persisted order line.
     *
     * @param id persisted identifier
     * @param productId product identifier
     * @param productName product name snapshot
     * @param quantity ordered quantity
     * @param unitPrice unit price snapshot
     * @param createdAt creation timestamp
     * @return rehydrated order line
     */
    public static OrderLine rehydrate(Long id, Long productId, String productName, int quantity,
                                      BigDecimal unitPrice, Instant createdAt) {
        return new OrderLine(id, productId, productName, quantity, unitPrice, createdAt);
    }

    /**
     * Calculates the immutable line total.
     *
     * @return quantity multiplied by unit price
     */
    public BigDecimal total() {
        return unitPrice.multiply(BigDecimal.valueOf(quantity));
    }

    /** @return persisted identifier, or {@code null} before persistence */
    public Long id(){ return id; }
    /** @return product identifier */
    public Long productId(){ return productId; }
    /** @return product name snapshot */
    public String productName(){ return productName; }
    /** @return ordered quantity */
    public int quantity(){ return quantity; }
    /** @return unit price snapshot */
    public BigDecimal unitPrice(){ return unitPrice; }
    /** @return creation timestamp */
    public Instant createdAt(){ return createdAt; }
}
