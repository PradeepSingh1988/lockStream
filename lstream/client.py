from functools import lru_cache
import logging
from threading import Lock
import uuid

import grpc

from common.rpc_client import RPCClient, RPCFailedError
from lstream.proto import lstream_pb2, lstream_pb2_grpc

LOG = logging.getLogger(__name__)


class LockServiceRpcClient(RPCClient):
    def acquire(self, lock_id, client_id, request_id):
        try:
            request = lstream_pb2.LockOpRequest(
                lock_id=lock_id,
                client_id=client_id,
                request_id=request_id,
            )
            stub = lstream_pb2_grpc.LockStreamStub(self._conn())
            response = stub.acquire(request)
            return response
        except grpc.RpcError as rpc_error:
            raise RPCFailedError(
                "RPC Call Lock Acquire failed due to: code={}, message={}".format(
                    rpc_error.code(), rpc_error.details()
                )
            )
        except Exception as ex:
            raise RPCFailedError("RPC Call Lock Acquire failed due to {}".format(ex))

    def release(self, lock_id, client_id, request_id):
        try:
            request = lstream_pb2.LockOpRequest(
                lock_id=lock_id,
                client_id=client_id,
                request_id=request_id,
            )
            stub = lstream_pb2_grpc.LockStreamStub(self._conn())
            response = stub.release(request)
            return response
        except grpc.RpcError as rpc_error:
            raise RPCFailedError(
                "RPC Call Lock Release failed due to: code={}, message={}".format(
                    rpc_error.code(), rpc_error.details()
                )
            )
        except Exception as ex:
            raise RPCFailedError("RPC Call Lock Release failed due to {}".format(ex))


class LockServiceClient(object):
    def __init__(self, servers):
        self._client_id = str(uuid.uuid4())[:8]
        self._request_id = 0
        self._leader = servers[0]
        self._servers = servers
        self._connection_map = {
            server: LockServiceRpcClient(server[0], server[1])
            for server in self._servers
        }
        self._lock = Lock()

    def acquire(self, lock_id):
        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        def _send_request(server):
            try:
                result = self._connection_map[server].acquire(
                    lock_id, self._client_id, request_id
                )
                return result
            except Exception as ex:
                print(ex)
                return lstream_pb2.LockOpReply(
                    lock_id=lock_id,
                    is_leader=True,
                    is_timedout=False,
                    is_successful=True,
                    client_id=self._client_id,
                    request_id=request_id,
                    is_valid=False,
                )

        reply = _send_request(self._leader)
        if not reply.is_leader:
            for server in [
                server for server in self._servers if server != self._leader
            ]:
                reply = _send_request(server)
                if reply.is_leader:
                    with self._lock:
                        self._leader = server
                        break
            return reply.is_successful
        else:
            return reply.is_successful

    def release(self, lock_id):
        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        def _send_request(server):
            try:
                result = self._connection_map[server].release(
                    lock_id, self._client_id, request_id
                )
                return result
            except Exception as ex:
                print(ex)
                return lstream_pb2.LockOpReply(
                    lock_id=lock_id,
                    is_leader=True,
                    is_timedout=False,
                    is_successful=True,
                    client_id=self._client_id,
                    request_id=request_id,
                    is_valid=False,
                )

        reply = _send_request(self._leader)
        if not reply.is_leader:
            for server in [
                server for server in self._servers if server != self._leader
            ]:
                reply = _send_request(server)
                if reply.is_leader:
                    with self._lock:
                        self._leader = server
                        break
            return reply.is_successful
        else:
            return reply.is_successful


if __name__ == "__main__":
    client = LockServiceClient(
        [("127.0.0.1", 17000), ("127.0.0.1", 18000), ("127.0.0.1", 19000)]
    )

    assert client.acquire("test") == True
    assert client.release("test") == True
    assert client.acquire("test") == True
    assert client.release("test") == True
