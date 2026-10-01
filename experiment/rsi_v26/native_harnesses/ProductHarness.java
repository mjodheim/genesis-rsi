import be.mjodheim.cellar.catalog.internal.domain.Product;
import be.mjodheim.cellar.catalog.internal.domain.ProductType;
import java.math.BigDecimal;
import java.time.Instant;

public final class ProductHarness {
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
        for(String value:new String[]{"0","0.01","1.37","15.90","1000.001"}) {
            BigDecimal p=new BigDecimal(value);
            for(ProductType type:ProductType.values()) {
                check("price-create-"+value+"-"+type,()->Product.create("name",type,null,330,p,NOW).price().compareTo(p)==0);
                check("price-change-"+value+"-"+type,()->{
                    Product product=Product.create("before",type,null,250,BigDecimal.ONE,NOW);
                    product.changeDetails("after",type,null,500,p,NOW.plusSeconds(1));
                    return product.price().compareTo(p)==0;
                });
            }
        }
        for(int quantity:new int[]{1,33,250,330,500,750,1000,33000}) {
            final int q=quantity;
            check("volume-create-"+q,()->Product.create("name",ProductType.BEER,null,q,BigDecimal.ONE,NOW).volumeMl()==q);
            check("volume-rehydrate-"+q,()->Product.rehydrate(1L,"name",ProductType.MEAD,null,q,BigDecimal.ONE,
                    true,NOW,NOW).volumeMl()==q);
        }
        System.out.println("{\"passed\":"+passed+",\"total\":"+total+",\"failed\":["+failed+"]}");
    }
}
