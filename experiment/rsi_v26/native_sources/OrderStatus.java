package be.mjodheim.cellar.ordering.internal.domain;

/**
 * Supported lifecycle states of a customer order.
 */
public enum OrderStatus {
    /** Editable order that has not yet reserved stock. */
    DRAFT,

    /** Validated order whose stock has been reserved. */
    CONFIRMED,

    /** Confirmed order currently being prepared for shipment. */
    PREPARING,

    /** Final state reached after stock consumption and shipment. */
    SHIPPED,

    /** Final state for an order cancelled before shipment. */
    CANCELLED
}
