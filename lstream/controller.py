import argparse
import logging
import queue
from concurrent import futures
import os

import grpc

from lstream.common.logger import setup_logger
from lstream.proto import lstream_pb2_grpc
from lstream.main import LockServer
from lstream.proto  import raft_pb2_grpc
from lstream.raft.concensus import RaftConsensus
from lstream.raft.persister import Persister


setup_logger()
LOG = logging.getLogger(__name__)


def serve(index, state_dir):
    ports = {0: 17000, 1: 18000, 2: 19000}
    state_machine_q = queue.Queue()
    raft_log_file = os.path.join(state_dir, "raft_{}.log".format(str(index)))
    raft = RaftConsensus(
        [("127.0.0.1", 17000), ("127.0.0.1", 18000), ("127.0.0.1", 19000)],
        index,
        state_machine_q,
        Persister(raft_log_file),
    )
    lock_svc = LockServer(raft, state_machine_q, index)
    port = str(ports[index])
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    raft_pb2_grpc.add_RaftConsensusServiceServicer_to_server(raft, server)
    lstream_pb2_grpc.add_LockStreamServicer_to_server(lock_svc, server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)
    server.wait_for_termination()


def main():
    parser = argparse.ArgumentParser(
        prog="DistributedLockService",
        description="Distribute lock service",
    )

    parser.add_argument("--index", required=True, help="Index")
    parser.add_argument("--state-dir", required=True, help="State Directory")
    args = parser.parse_args()
    index = int(args.index)

    serve(index, args.state_dir)


if __name__ == "__main__":
    main()
