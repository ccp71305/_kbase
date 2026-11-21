import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CopyObjectRequest;
import software.amazon.awssdk.services.s3.model.MetadataDirective;
import java.util.HashMap;
import java.util.Map;

/** As cloud-sdk S3StorageClient.copyObject(..., replacedMetadata, contentType): the same metadata with null values. */
public class NullMetaV2 {
    public static void main(String[] a) {
        Map<String, String> m = new HashMap<>();
        m.put("workflowId", "wi01124532-rt-dist-nullmeta");
        m.put("contextCode", null);
        m.put("outboundEdiId", null);
        try (S3Client s3 = S3Client.builder().region(Region.US_EAST_1).build()) {
            s3.copyObject(CopyObjectRequest.builder().sourceBucket(a[0]).sourceKey(a[1])
                    .destinationBucket(a[0]).destinationKey(a[2])
                    .metadataDirective(MetadataDirective.REPLACE).metadata(m)
                    .contentType("application/octet-stream").build());
            System.out.println("v2 copy done");
        } catch (Exception e) {
            System.out.println("v2 copy failed: " + e);
        }
    }
}
