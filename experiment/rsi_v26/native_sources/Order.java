package be.mjodheim.cellar.ordering.internal.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * Ordering aggregate controlling the lifecycle of a customer order.
 *
 * <p>The aggregate owns its lines, status transitions and soft-delete rules.
 * Stock allocation itself is delegated to the Inventory module through its
 * public module API.</p>
 */
public final class Order {

    private final Long id;
    private final String orderNumber;
    private final String customerReference;
    private final List<OrderLine> lines;
    private final Instant createdAt;

    private OrderStatus status;
    private Instant updatedAt;
    private Instant deletedAt;

    private Order(Long id, String orderNumber, String customerReference, OrderStatus status,
                  List<OrderLine> lines, Instant createdAt, Instant updatedAt, Instant deletedAt) {
        if (orderNumber == null || orderNumber.isBlank()) throw new IllegalArgumentException("Order number is required");
        this.id=id; this.orderNumber=orderNumber.trim(); this.customerReference=normalize(customerReference);
        this.status=Objects.requireNonNull(status); this.lines=new ArrayList<>(Objects.requireNonNull(lines));
        this.createdAt=Objects.requireNonNull(createdAt); this.updatedAt=Objects.requireNonNull(updatedAt);
        this.deletedAt=deletedAt;
    }

    /**
     * Creates a new draft order.
     *
     * @param orderNumber generated business order number
     * @param customerReference optional external customer reference
     * @param now creation timestamp
     * @return new draft order
     */
    public static Order create(String orderNumber, String customerReference, Instant now) {
        return new Order(null, orderNumber, customerReference, OrderStatus.DRAFT, List.of(), now, now, null);
    }

    /**
     * Rebuilds an order aggregate from persisted state.
     *
     * @param id persisted identifier
     * @param orderNumber business order number
     * @param customerReference optional customer reference
     * @param status current lifecycle status
     * @param lines persisted lines
     * @param createdAt creation timestamp
     * @param updatedAt last modification timestamp
     * @param deletedAt soft-delete timestamp, or {@code null}
     * @return rehydrated order
     */
    public static Order rehydrate(Long id, String orderNumber, String customerReference, OrderStatus status,
                                  List<OrderLine> lines, Instant createdAt, Instant updatedAt, Instant deletedAt) {
        return new Order(id, orderNumber, customerReference, status, lines, createdAt, updatedAt, deletedAt);
    }

    /**
     * Adds a commercial snapshot line to a draft order.
     *
     * @param productId product identifier
     * @param productName product name snapshot
     * @param quantity ordered quantity
     * @param unitPrice unit price snapshot
     * @param now line creation timestamp
     */
    public void addLine(Long productId, String productName, int quantity, BigDecimal unitPrice, Instant now) {
        ensureNotDeleted();
        requireStatus(OrderStatus.DRAFT);
        lines.add(OrderLine.create(productId, productName, quantity, unitPrice, now));
        updatedAt = Objects.requireNonNull(now);
    }

    /**
     * Confirms a draft order.
     *
     * @param now modification timestamp
     */
    public void confirm(Instant now) {
        ensureNotDeleted();
        requireStatus(OrderStatus.DRAFT);
        if (lines.isEmpty()) throw new IllegalStateException("An order must contain at least one line");
        status = OrderStatus.CONFIRMED;
        updatedAt = Objects.requireNonNull(now);
    }

    /**
     * Moves a confirmed order into preparation.
     *
     * @param now modification timestamp
     */
    public void startPreparation(Instant now) {
        ensureNotDeleted();
        requireStatus(OrderStatus.CONFIRMED);
        status = OrderStatus.PREPARING;
        updatedAt = Objects.requireNonNull(now);
    }

    /**
     * Marks a preparing order as shipped.
     *
     * @param now modification timestamp
     */
    public void ship(Instant now) {
        ensureNotDeleted();
        requireStatus(OrderStatus.PREPARING);
        status = OrderStatus.SHIPPED;
        updatedAt = Objects.requireNonNull(now);
    }

    /**
     * Cancels a non-shipped order when the lifecycle allows it.
     *
     * @param now modification timestamp
     */
    public void cancel(Instant now) {
        ensureNotDeleted();
        if (status == OrderStatus.SHIPPED) throw new IllegalStateException("A shipped order cannot be cancelled");
        if (status == OrderStatus.CANCELLED) return;
        status = OrderStatus.CANCELLED;
        updatedAt = Objects.requireNonNull(now);
    }

    /**
     * Soft-deletes a draft or cancelled order.
     *
     * @param now deletion timestamp
     */
    public void softDelete(Instant now) {
        if (deletedAt != null) return;
        if (status != OrderStatus.DRAFT && status != OrderStatus.CANCELLED)
            throw new IllegalStateException("Only a draft or cancelled order can be deleted");
        deletedAt = Objects.requireNonNull(now);
        updatedAt = now;
    }

    /**
     * Calculates the current commercial total from immutable line snapshots.
     *
     * @return sum of all line totals
     */
    public BigDecimal total() {
        return lines.stream().map(OrderLine::total).reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    /** @return {@code true} when the order has been soft-deleted */
    public boolean isDeleted() { return deletedAt != null; }

    private void ensureNotDeleted() {
        if (isDeleted()) throw new IllegalStateException("Deleted order cannot be modified");
    }

    private void requireStatus(OrderStatus expected) {
        if (status != expected) throw new IllegalStateException("Order must be " + expected);
    }

    private static String normalize(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    /** @return persisted identifier, or {@code null} before persistence */
    public Long id(){ return id; }
    /** @return immutable business order number */
    public String orderNumber(){ return orderNumber; }
    /** @return optional external customer reference */
    public String customerReference(){ return customerReference; }
    /** @return current lifecycle status */
    public OrderStatus status(){ return status; }
    /** @return immutable copy of the order lines */
    public List<OrderLine> lines(){ return List.copyOf(lines); }
    /** @return creation timestamp */
    public Instant createdAt(){ return createdAt; }
    /** @return last modification timestamp */
    public Instant updatedAt(){ return updatedAt; }
    /** @return soft-delete timestamp, or {@code null} */
    public Instant deletedAt(){ return deletedAt; }
}
