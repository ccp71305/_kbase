import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.CopyObjectRequest;
import com.amazonaws.services.s3.model.ObjectMetadata;
import java.util.HashMap;
import java.util.Map;

/** As distributor's v1 S3WorkspaceService.copyObjectWithMetaDate: REPLACE copy with user metadata holding null values. */
public class NullMetaV1 {
    public static void main(String[] a) {
        AmazonS3 s3 = AmazonS3ClientBuilder.standard().withRegion("us-east-1").build();
        Map<String, String> m = new HashMap<>();
        m.put("workflowId", "wi01124532-rt-dist-nullmeta");
        m.put("contextCode", null);
        m.put("outboundEdiId", null);
        ObjectMetadata metadata = new ObjectMetadata();
        metadata.setUserMetadata(m);
        s3.copyObject(new CopyObjectRequest(a[0], a[1], a[0], a[2]).withNewObjectMetadata(metadata));
        System.out.println("v1 copy done");
    }
}
