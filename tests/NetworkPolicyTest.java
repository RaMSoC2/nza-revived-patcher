import com.ramsoc2.nzarevived.NzaNetworkPolicy;
import java.net.URL;
import java.nio.file.Files;

/** No network traffic: URL handlers reject requests before a connection exists. */
public final class NetworkPolicyTest {
    public static void main(String[] args)throws Exception {
        if(!NzaNetworkPolicy.permits(new URL(NzaNetworkPolicy.PLACES_ENDPOINT)))throw new AssertionError("Known endpoint refused");
        if(!NzaNetworkPolicy.permits(new URL(NzaNetworkPolicy.PLACES_FALLBACK_ENDPOINT)))throw new AssertionError("Authorized alternative refused");
        String[] refused={
            "http://overpass.private.coffee/api/interpreter",
            "https://overpass.private.coffee.invalid/api/interpreter",
            "https://overpass.private.coffee@legacy.invalid/api/interpreter",
            "https://user@overpass.private.coffee/api/interpreter",
            "https://overpass.private.coffee:444/api/interpreter",
            "https://overpass.private.coffee/api/other",
            "https://overpass.private.coffee/api/interpreter?url=https://legacy.invalid",
            "https://overpass.private.coffee/api/interpreter#other"
        };
        for(String value:refused)for(String host:new String[]{"overpass.private.coffee","overpass-api.de"})
            if(NzaNetworkPolicy.permits(new URL(value.replace("overpass.private.coffee",host))))throw new AssertionError("Unexpected endpoint allowed");
        java.nio.file.Path local=Files.createTempFile("nza-policy-", ".txt");
        try {
            Files.write(local,new byte[]{42});
            NzaNetworkPolicy.blockLegacyUrlConnections();
            for(String value:new String[]{"http://legacy.invalid/","https://legacy.invalid/",NzaNetworkPolicy.PLACES_ENDPOINT,NzaNetworkPolicy.PLACES_FALLBACK_ENDPOINT}) {
                try {new URL(value).openConnection();throw new AssertionError("Legacy URL connection escaped");}
                catch(java.io.IOException expected){}
            }
            try(java.io.InputStream input=local.toUri().toURL().openStream()) {
                if(input.read()!=42)throw new AssertionError("Local resource access broken");
            }
        } finally {Files.delete(local);}
        System.out.println("{\"allowed_endpoints\":2,\"rejected_variants\":16,\"legacy_urls_denied\":4,\"local_file_preserved\":true}");
    }
}
