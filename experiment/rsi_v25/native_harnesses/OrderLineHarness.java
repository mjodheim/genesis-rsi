import be.mjodheim.cellar.ordering.internal.domain.OrderLine;
import java.math.BigDecimal;
import java.time.Instant;

public final class OrderLineHarness {
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
        for (String price : new String[]{"0", "0.01", "1.37", "15.90", "1000.001"}) {
            for (int quantity : new int[]{1, 2, 7, 31}) {
                final int q = quantity;
                final BigDecimal p = new BigDecimal(price);
                check("total-" + price + "-" + q, () ->
                    OrderLine.create(1L, "name", q, p, NOW).total().compareTo(p.multiply(BigDecimal.valueOf(q))) == 0);
            }
        }
        for (String name : new String[]{"  Amber ale  ", "\tSaison\n", "  wine", "Stout  ", "MiXeD", " 0 "}) {
            check("snapshot-create-" + total, () ->
                OrderLine.create(1L, name, 1, BigDecimal.ONE, NOW).productName().equals(name.trim()));
            check("snapshot-rehydrate-" + total, () ->
                OrderLine.rehydrate(7L, 1L, name, 2, BigDecimal.ONE, NOW).productName().equals(name.trim()));
        }
        System.out.println("{\"passed\":" + passed + ",\"total\":" + total + ",\"failed\":[" + failed + "]}");
    }
}
