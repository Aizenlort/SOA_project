import grpc
from concurrent import futures
import logging

from app import flight_pb2_grpc
from app.flight_servicer import FlightServicer
from app.auth_interceptor import AuthInterceptor
from app.config import settings

logging.basicConfig(level=logging.INFO)

def serve():
    auth_interceptor = AuthInterceptor(settings.GRPC_AUTH_KEY)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[auth_interceptor]
    )

    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServicer(), server)
    
    port = "50051"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logging.info(f"gRPC Server started on port {port}")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()