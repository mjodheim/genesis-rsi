import be.mjodheim.cellar.inventory.internal.domain.Batch;
import java.time.Instant;

public final class BatchHarness {
    static int passed = 0, total = 0;
    static StringBuilder failed = new StringBuilder();
    static final Instant NOW = Instant.parse("2026-01-01T00:00:00Z");
    interface Check { boolean run(); }
    static void check(String id, Check test) {
        total++;
        try { if (test.run()) { passed++; return; } } catch (RuntimeException e) {}
        if (failed.length() > 0) failed.append(',');
        failed.append('"').append(id).append('"');
    }
    public static void main(String[] args) {
        for (int quantity : new int[]{1, 2, 7, 19, 53, 101}) {
            final int q = quantity;
            for (int reserved : new int[]{0, 1, quantity}) {
                final int r = reserved;
                check("available-" + q + "-" + r, () -> {
                    Batch b = Batch.rehydrate(1L, 1L, " lot ", q, q, r, NOW, null, NOW, NOW, null);
                    return b.availableQuantity() == q - r;
                });
            }
            for (int shipped : new int[]{1, quantity}) {
                final int ship = shipped;
                check("ship-" + q + "-" + ship, () -> {
                    Batch b = Batch.rehydrate(1L, 1L, "lot", q, q, q, NOW, null, NOW, NOW, null);
                    b.shipReserved(ship, NOW.plusSeconds(1));
                    return b.quantityOnHand() == q - ship && b.quantityReserved() == q - ship;
                });
            }
            check("reserve-release-" + q, () -> {
                Batch b = Batch.receive(1L, "lot", q, NOW, null, NOW);
                b.reserve(q, NOW); b.release(q, NOW);
                return b.availableQuantity() == q && b.quantityReserved() == 0;
            });
        }
        System.out.println("{\"passed\":" + passed + ",\"total\":" + total + ",\"failed\":[" + failed + "]}");
    }
}
