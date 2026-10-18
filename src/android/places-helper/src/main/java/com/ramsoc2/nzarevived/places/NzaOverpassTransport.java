package com.ramsoc2.nzarevived.places;

import com.ramsoc2.nzarevived.NzaNetworkPolicy;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

/** Two fixed, authorized destinations; no redirects, custom URLs or TLS bypass. */
public final class NzaOverpassTransport {
    interface Connections { HttpURLConnection open(URL url, Proxy proxy) throws IOException; }
    public static String fetch(String query) throws IOException {
        return fetch(query,(url,proxy)->(HttpURLConnection)url.openConnection(proxy));
    }
    static String fetch(String query,Connections connections) throws IOException {
        byte[] body=("data="+URLEncoder.encode(query,"UTF-8")).getBytes(StandardCharsets.UTF_8);
        IOException last=null;
        for(String address:new String[]{NzaNetworkPolicy.PLACES_ENDPOINT,NzaNetworkPolicy.PLACES_FALLBACK_ENDPOINT}) {
            URL url=new URL(address);
            if(!NzaNetworkPolicy.permits(url))throw new SecurityException("Endpoint refused");
            HttpURLConnection connection=null;
            try {
                connection=connections.open(url,Proxy.NO_PROXY);
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(12000);connection.setReadTimeout(22000);
                connection.setRequestMethod("POST");connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type","application/x-www-form-urlencoded; charset=UTF-8");
                connection.setRequestProperty("User-Agent","NZA-Revival-Preservation-Experimental/0.2.1");
                connection.setFixedLengthStreamingMode(body.length);
                try(OutputStream out=connection.getOutputStream()){out.write(body);}
                int status=connection.getResponseCode();
                if(status!=200)throw new StatusFailure(status);
                ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                try(InputStream in=connection.getInputStream()) {
                    byte[] buffer=new byte[8192];int n;
                    while((n=in.read(buffer))!=-1) {
                        if(bytes.size()+n>2*1024*1024)throw new StatusFailure(-1);
                        bytes.write(buffer,0,n);
                    }
                }
                return bytes.toString("UTF-8");
            } catch(IOException failure) {
                // Bad queries, redirects and oversized responses are not retried.
                if(failure instanceof StatusFailure && !((StatusFailure)failure).retryable)throw failure;
                last=failure;
            } finally {if(connection!=null)connection.disconnect();}
        }
        throw last;
    }
    private static final class StatusFailure extends IOException {
        final boolean retryable;
        StatusFailure(int code){super("http_"+code);retryable=code==429||(code>=500&&code<=599);}
    }
    private NzaOverpassTransport(){}
}
