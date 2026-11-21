import com.amazonaws.auth.DefaultAWSCredentialsProviderChain;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.client.methods.HttpRequestBase;
import org.apache.http.entity.ContentType;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import vc.inreach.aws.request.AWSSigner;
import vc.inreach.aws.request.AWSSigningRequestInterceptor;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.ZoneOffset;

/**
 * Read-only queries to an Elasticsearch domain, signed exactly as ingestor signs (same signer, same HTTP client,
 * credentials from the default chain). Only GET, and POST to _search / _count (queries, no write).
 * Usage: java -cp ingestor.jar EsRead.java <endpoint> <path> [queryFile]
 */
public class EsRead {
    public static void main(String[] args) throws Exception {
        String endpoint = args[0].replaceAll("/$", "");
        String path = args[1];
        if (args.length > 2 && !(path.contains("/_search") || path.contains("/_count"))) {
            throw new IllegalArgumentException("read only: a body is allowed only for _search or _count");
        }
        AWSSigner signer = new AWSSigner(new DefaultAWSCredentialsProviderChain(), "us-east-1", "es",
                () -> LocalDateTime.now(ZoneOffset.UTC));
        try (CloseableHttpClient http = HttpClients.custom()
                .addInterceptorLast(new AWSSigningRequestInterceptor(signer)).build()) {
            HttpRequestBase request;
            if (args.length > 2) {
                HttpPost post = new HttpPost(endpoint + path);
                post.setEntity(new StringEntity(Files.readString(Path.of(args[2])), ContentType.APPLICATION_JSON));
                request = post;
            } else {
                request = new HttpGet(endpoint + path);
            }
            try (CloseableHttpResponse response = http.execute(request)) {
                System.err.println("HTTP " + response.getStatusLine().getStatusCode());
                System.out.println(EntityUtils.toString(response.getEntity()));
            }
        }
    }
}
