from functools import lru_cache
import logging

from google.protobuf.struct_pb2 import Struct
import grpc


from lstream.common.rpc_client import RPCClient, RPCFailedError
from lstream.raft.consts import HEARTBEAT_PERIOD
from lstream.proto import raft_pb2, raft_pb2_grpc


LOG = logging.getLogger(__name__)


class RaftNodeClient(RPCClient):
    def request_vote(self, term, candidate_id, last_log_index, last_log_term):
        try:
            request = raft_pb2.AskForVoteRequest(
                c_term=term,
                c_id=candidate_id,
                c_last_log_index=last_log_index,
                c_last_log_term=last_log_term,
            )
            stub = raft_pb2_grpc.RaftConsensusServiceStub(self._conn())
            response = stub.handle_request_vote(
                request, timeout=HEARTBEAT_PERIOD / 1000
            )
            return response
        except grpc.RpcError as rpc_error:
            raise RPCFailedError(
                "RPC Call AskForVoteRequest failed due to: code={}, message={}".format(
                    rpc_error.code(), rpc_error.details()
                )
            )
        except Exception as ex:
            raise RPCFailedError(
                "RPC Call AskForVoteRequest failed due to {}".format(ex)
            )

    def append_entries(
        self, term, leader_id, prev_log_index, prev_log_term, commit_index, entries
    ):
        try:
            # Convert to Log Entry
            marshalled_entries = []
            for entry in entries:
                entry_str = Struct()
                entry_str.update(entry.command)
                marshalled_entries.append(
                    raft_pb2.LogEntry(term=entry.term, command=entry_str)
                )

            request = raft_pb2.AppendEntriesRequest(
                term=term,
                leader_id=leader_id,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                commit_index=commit_index,
                entries=marshalled_entries,
            )
            stub = raft_pb2_grpc.RaftConsensusServiceStub(self._conn())
            response = stub.handle_append_entries(
                request, timeout=HEARTBEAT_PERIOD / 1000
            )
            return response
        except grpc.RpcError as rpc_error:
            raise RPCFailedError(
                "RPC Call AppendEntriesRequest failed due to: code={}, message={}".format(
                    rpc_error.code(), rpc_error.details()
                )
            )
        except Exception as ex:
            raise RPCFailedError(
                "RPC Call AppendEntriesRequest failed due to {}".format(ex)
            )
