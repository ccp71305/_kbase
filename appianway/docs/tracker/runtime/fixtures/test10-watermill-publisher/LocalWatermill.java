import com.e2open.watermill.proto.api.PingAck;
import com.e2open.watermill.proto.api.PingReq;
import com.e2open.watermill.proto.api.PublisherAck;
import com.e2open.watermill.proto.api.PublisherGrpc;
import com.e2open.watermill.proto.logistics.ShipmentStatusChangeEvent;
import com.google.protobuf.TextFormat;
import io.grpc.Metadata;
import io.grpc.Server;
import io.grpc.ServerCall;
import io.grpc.ServerCallHandler;
import io.grpc.ServerInterceptor;
import io.grpc.ServerInterceptors;
import io.grpc.netty.shaded.io.grpc.netty.NettyServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.File;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Runtime test 10: a local stand-in for e2open Watermill's Publisher service, so that nothing is published to the
 * e2open broker. TLS on localhost with a self-signed certificate (the service's channel is TLS, as in production).
 * Records each call's method and metadata (username and password: present or not, never the value; tenant;
 * grpc-encoding), each event in protobuf text format and each ping; acks every event with its message id.
 * Usage: java -cp watermill-publisher-<build>.jar LocalWatermill.java <port> <cert.pem> <key.pem> <record file>
 *        [ack delay ms, default 0; -1 = never ack]
 */
public class LocalWatermill {

    static Path record;
    static final AtomicInteger calls = new AtomicInteger();
    static final AtomicInteger events = new AtomicInteger();
    static final AtomicLong offsets = new AtomicLong(1000);
    static long ackDelayMillis;
    static final java.util.concurrent.ScheduledExecutorService acker =
            java.util.concurrent.Executors.newSingleThreadScheduledExecutor();

    static synchronized void write(String line) {
        try {
            Files.writeString(record, line + "\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE,
                    StandardOpenOption.APPEND);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    static String presence(String value) {
        return value == null ? "absent" : "present";
    }

    public static void main(String[] args) throws Exception {
        int port = Integer.parseInt(args[0]);
        record = Path.of(args[3]);
        ackDelayMillis = args.length > 4 ? Long.parseLong(args[4]) : 0;
        Files.deleteIfExists(record);
        ServerInterceptor headers = new ServerInterceptor() {
            @Override
            public <Q, R> ServerCall.Listener<Q> interceptCall(ServerCall<Q, R> call, Metadata metadata,
                                                              ServerCallHandler<Q, R> next) {
                Metadata.Key<String> username = Metadata.Key.of("username", Metadata.ASCII_STRING_MARSHALLER);
                Metadata.Key<String> password = Metadata.Key.of("password", Metadata.ASCII_STRING_MARSHALLER);
                Metadata.Key<String> tenant = Metadata.Key.of("tenant", Metadata.ASCII_STRING_MARSHALLER);
                Metadata.Key<String> encoding = Metadata.Key.of("grpc-encoding", Metadata.ASCII_STRING_MARSHALLER);
                write("call " + calls.incrementAndGet() + " " + call.getMethodDescriptor().getFullMethodName()
                        + " username=" + presence(metadata.get(username)) + " password=" + presence(metadata.get(password))
                        + " tenant=" + metadata.get(tenant) + " grpc-encoding=" + metadata.get(encoding));
                return next.startCall(call, metadata);
            }
        };
        PublisherGrpc.PublisherImplBase publisher = new PublisherGrpc.PublisherImplBase() {
            @Override
            public void ping(PingReq request, StreamObserver<PingAck> responses) {
                write("  ping entity=" + request.getEntity());
                responses.onNext(PingAck.newBuilder().setErrorCode(PingAck.ErrorCode.OK).build());
                responses.onCompleted();
            }

            @Override
            public StreamObserver<ShipmentStatusChangeEvent> publishShipmentStatusMicroBatch(
                    StreamObserver<PublisherAck> responses) {
                return new StreamObserver<>() {
                    @Override
                    public void onNext(ShipmentStatusChangeEvent event) {
                        write("  event " + events.incrementAndGet() + ": "
                                + TextFormat.printer().escapingNonAscii(false).shortDebugString(event));
                        System.out.println(Instant.now() + " received " + event.getMessageId());
                        if (ackDelayMillis < 0) {
                            return;   // never acks
                        }
                        acker.schedule(() -> {
                            try {
                                responses.onNext(PublisherAck.newBuilder().setCorrelationId(event.getMessageId())
                                        .setOffset(offsets.incrementAndGet()).setSize(event.getSerializedSize()).build());
                                System.out.println(Instant.now() + " acked " + event.getMessageId());
                            } catch (RuntimeException e) {
                                System.out.println(Instant.now() + " could not ack " + event.getMessageId() + ": " + e);
                            }
                        }, ackDelayMillis, java.util.concurrent.TimeUnit.MILLISECONDS);
                    }

                    @Override
                    public void onError(Throwable t) {
                        System.out.println(Instant.now() + " stream ended by the client: " + t);
                    }

                    @Override
                    public void onCompleted() {
                        responses.onCompleted();
                    }
                };
            }
        };
        Server server = NettyServerBuilder.forPort(port)
                .useTransportSecurity(new File(args[1]), new File(args[2]))
                .addService(ServerInterceptors.intercept(publisher, headers))
                .build().start();
        System.out.println(Instant.now() + " local Watermill listening on " + port + " (TLS)");
        server.awaitTermination();
    }
}
