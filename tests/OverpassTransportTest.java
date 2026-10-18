package com.ramsoc2.nzarevived.places;

import java.io.*;
import java.net.*;
import java.util.*;

/** Deterministic offline tests: fake connections, never sockets or location data. */
public final class OverpassTransportTest {
    static final class Reply extends HttpURLConnection {
        final int status;final byte[] bytes;boolean closed;
        final ByteArrayOutputStream posted=new ByteArrayOutputStream();
        Reply(URL url,int status,byte[] bytes){super(url);this.status=status;this.bytes=bytes;}
        public void connect(){}public boolean usingProxy(){return false;}
        public void disconnect(){closed=true;}
        public OutputStream getOutputStream(){return posted;}
        public int getResponseCode(){return status;}
        public InputStream getInputStream(){return new ByteArrayInputStream(bytes);}
    }
    public static void main(String[] args)throws Exception {
        List<Reply> calls=new ArrayList<>();
        String result=NzaOverpassTransport.fetch("public fixture only",(url,proxy)->{
            if(proxy!=Proxy.NO_PROXY)throw new AssertionError("Proxy used");
            Reply reply=new Reply(url,calls.isEmpty()?500:200,"{\"elements\":[]}".getBytes("UTF-8"));
            calls.add(reply);return reply;
        });
        if(calls.size()!=2||!result.equals("{\"elements\":[]}"))throw new AssertionError("Failover failed");
        if(!calls.get(0).getURL().getHost().equals("overpass.private.coffee"))throw new AssertionError();
        if(!calls.get(1).getURL().getHost().equals("overpass-api.de"))throw new AssertionError();
        for(Reply reply:calls)if(!reply.closed||reply.getInstanceFollowRedirects()||!"POST".equals(reply.getRequestMethod())
            ||reply.getReadTimeout()!=22000||reply.getConnectTimeout()!=12000)throw new AssertionError("Connection contract broken");
        if(!Arrays.equals(calls.get(0).posted.toByteArray(),calls.get(1).posted.toByteArray()))throw new AssertionError("Different payload");
        for(int status:new int[]{400,302}){
            int[] count={0};
            try{NzaOverpassTransport.fetch("fixture",(url,proxy)->{count[0]++;return new Reply(url,status,new byte[0]);});throw new AssertionError("Status accepted");}
            catch(IOException expected){if(count[0]!=1)throw new AssertionError("Invalid request retried");}
        }
        int[] count={0};
        try{NzaOverpassTransport.fetch("fixture",(url,proxy)->{count[0]++;return new Reply(url,200,new byte[2*1024*1024+1]);});throw new AssertionError("Oversize accepted");}
        catch(IOException expected){if(count[0]!=1)throw new AssertionError("Oversize retried");}
        count[0]=0;
        try{NzaOverpassTransport.fetch("fixture",(url,proxy)->{count[0]++;throw new IOException("offline");});throw new AssertionError("Offline accepted");}
        catch(IOException expected){if(count[0]!=2)throw new AssertionError("Unbounded/offline retry");}
        System.out.println("500 failover, destination allowlist, same payload, no redirects/proxy, response bound, bounded failures: PASS");
    }
}
