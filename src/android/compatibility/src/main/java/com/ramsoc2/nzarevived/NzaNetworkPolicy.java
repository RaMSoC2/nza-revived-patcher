package com.ramsoc2.nzarevived;

/** Pure Java policy, also tested without Android or internet access. */
public final class NzaNetworkPolicy {
    public static final String PLACES_ENDPOINT="https://overpass.private.coffee/api/interpreter";
    public static final String PLACES_FALLBACK_ENDPOINT="https://overpass-api.de/api/interpreter";
    public static boolean permits(java.net.URL url) {
        return "https".equals(url.getProtocol())
            && ("overpass.private.coffee".equals(url.getHost()) || "overpass-api.de".equals(url.getHost()))
            && url.getPort()==-1 && "/api/interpreter".equals(url.getPath())
            && url.getQuery()==null && url.getRef()==null && url.getUserInfo()==null;
    }
    public static void blockLegacyUrlConnections() {
        java.net.URL.setURLStreamHandlerFactory(protocol->{
            if(!"http".equals(protocol)&&!"https".equals(protocol)&&!"ftp".equals(protocol))return null;
            return new java.net.URLStreamHandler(){
                @Override protected java.net.URLConnection openConnection(java.net.URL url)throws java.io.IOException {
                    throw new java.io.IOException("Legacy client networking is disabled");
                }
                @Override protected java.net.URLConnection openConnection(java.net.URL url,java.net.Proxy proxy)throws java.io.IOException {
                    throw new java.io.IOException("Legacy client networking is disabled");
                }
            };
        });
    }
    private NzaNetworkPolicy() {}
}
