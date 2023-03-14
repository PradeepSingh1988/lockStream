# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from lstream.proto import lstream_pb2 as lstream__pb2


class LockStreamStub(object):
    """Raft Consensus Service Definition.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.acquire = channel.unary_unary(
                '/LockStream/acquire',
                request_serializer=lstream__pb2.LockOpRequest.SerializeToString,
                response_deserializer=lstream__pb2.LockOpReply.FromString,
                )
        self.release = channel.unary_unary(
                '/LockStream/release',
                request_serializer=lstream__pb2.LockOpRequest.SerializeToString,
                response_deserializer=lstream__pb2.LockOpReply.FromString,
                )


class LockStreamServicer(object):
    """Raft Consensus Service Definition.
    """

    def acquire(self, request, context):
        """RequestVote handler
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def release(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_LockStreamServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'acquire': grpc.unary_unary_rpc_method_handler(
                    servicer.acquire,
                    request_deserializer=lstream__pb2.LockOpRequest.FromString,
                    response_serializer=lstream__pb2.LockOpReply.SerializeToString,
            ),
            'release': grpc.unary_unary_rpc_method_handler(
                    servicer.release,
                    request_deserializer=lstream__pb2.LockOpRequest.FromString,
                    response_serializer=lstream__pb2.LockOpReply.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'LockStream', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class LockStream(object):
    """Raft Consensus Service Definition.
    """

    @staticmethod
    def acquire(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/LockStream/acquire',
            lstream__pb2.LockOpRequest.SerializeToString,
            lstream__pb2.LockOpReply.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def release(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/LockStream/release',
            lstream__pb2.LockOpRequest.SerializeToString,
            lstream__pb2.LockOpReply.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
