import be.mjodheim.cellar.ordering.internal.domain.Order;
import be.mjodheim.cellar.ordering.internal.domain.OrderLine;
import be.mjodheim.cellar.ordering.internal.domain.OrderStatus;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public final class OrderHarness {
    static int passed=0,total=0;
    static StringBuilder failed=new StringBuilder();
    static final Instant NOW=Instant.parse("2026-01-01T00:00:00Z");
    interface Check { boolean run(); }
    static void check(String id,Check test) {
        total++;
        try { if(test.run()){passed++;return;} } catch(RuntimeException e){}
        if(failed.length()>0)failed.append(',');
        failed.append('"').append(id).append('"');
    }
    public static void main(String[] args) {
        for(int count:new int[]{0,1,2,5,9}) {
            final int n=count;
            for(String value:new String[]{"0","0.01","1.37","15.90"}) {
                BigDecimal price=new BigDecimal(value);
                check("aggregate-total-"+count+"-"+value,()->{
                    Order order=Order.create("order","customer",NOW);
                    BigDecimal expected=BigDecimal.ZERO;
                    for(int i=1;i<=n;i++){
                        order.addLine((long)i,"line-"+i,i,price,NOW);
                        expected=expected.add(price.multiply(BigDecimal.valueOf(i)));
                    }
                    return order.total().compareTo(expected)==0;
                });
            }
        }
        for(int quantity:new int[]{1,2,7,19,53,101}) {
            final int q=quantity;
            check("preparing-"+q,()->{
                Order order=Order.create("order",null,NOW);
                order.addLine(1L,"name",q,BigDecimal.ONE,NOW);
                order.confirm(NOW);order.startPreparation(NOW.plusSeconds(1));
                return order.status()==OrderStatus.PREPARING;
            });
            check("ship-after-preparation-"+q,()->{
                Order order=Order.rehydrate(1L,"order",null,OrderStatus.CONFIRMED,
                    List.of(OrderLine.create(1L,"name",q,BigDecimal.ONE,NOW)),NOW,NOW,null);
                order.startPreparation(NOW);order.ship(NOW.plusSeconds(1));
                return order.status()==OrderStatus.SHIPPED;
            });
        }
        System.out.println("{\"passed\":"+passed+",\"total\":"+total+",\"failed\":["+failed+"]}");
    }
}
