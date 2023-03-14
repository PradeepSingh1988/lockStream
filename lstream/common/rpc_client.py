from functools import lru_cache
import logging

import grpc


LOG = logging.getLogger(__name__)


class RPCFailedError(Exception):
    pass


class ConnectionFailedException(Exception):
    pass


class RPCClient(object):
    """
    Top level object to access RPyc API
    """

    def __init__(
        self,
        host="127.0.0.1",
        port=12345,
    ):
        @lru_cache(maxsize=1)
        def c():
            try:
                config = (
                    ("grpc.keepalive_time_ms", 1000),
                    ("grpc.keepalive_timeout_ms", 300),
                )
                channel = grpc.insecure_channel(
                    "{}:{}".format(host, port), options=config
                )
                return channel
            except grpc.RpcError as rpc_error:
                raise ConnectionFailedException(
                    "Connection failed to {}:{} due to: code={}, message={}".format(
                        host, port, rpc_error.code(), rpc_error.details()
                    )
                )

        self._conn = c

    def __del__(self):
        if self._conn.cache_info().hits > 0:
            self._conn().close()
