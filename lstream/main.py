from collections import defaultdict
import copy
import logging
from queue import Empty, Queue
import random
from threading import Condition, Lock, Thread
import time

from lstream.common.logger import CustomAdapter
from lstream.proto import lstream_pb2,lstream_pb2_grpc

STATEMACHINE_QUEUE_WAIT_TIME = 2


class LockServer(lstream_pb2_grpc.LockStreamServicer):
    def __init__(self, raft_consensus, statemachine_q, me):
        self._raft = raft_consensus
        self._sm_queue = statemachine_q
        self._last_applied = {}
        self._result = defaultdict(Queue)
        self._lock = Lock()
        self._lock_store = {}
        self._me = me
        self.logger = CustomAdapter(
            logging.getLogger(__name__),
            {"logger": "{}:{}".format("LOCKSVC", self._me)},
        )
        Thread(target=self._read_state_machine_queue).start()

    def _dump_state(self):
        self.logger.debug(
            "last_applied {}, store {}".format(self._last_applied, self._lock_store)
        )

    def _apply_to_state_machine(self, command):
        self.logger.debug("Apply command {} to state machine".format(command))
        lock_id = command["lock_id"]
        release_status = False
        acquired_status = False
        if command["op"] == "release":
            if lock_id in self._lock_store and self._lock_store[lock_id]["status"]:
                self._lock_store[lock_id]["status"] = False
                release_status = True
                with self._lock_store[lock_id]["condition"]:
                    self._lock_store[lock_id]["condition"].notify_all()
            command.update(
                {
                    "status": release_status,
                    "condition": self._lock_store[lock_id]["condition"],
                }
            )
        elif command["op"] == "acquire":

            if lock_id in self._lock_store:
                if not self._lock_store[lock_id]["status"]:
                    self._lock_store[lock_id]["status"] = True
                    acquired_status = True
                else:
                    acquired_status = False
            else:
                self._lock_store[lock_id] = {}
                self._lock_store[lock_id]["status"] = True
                self._lock_store[lock_id]["condition"] = Condition()
                acquired_status = True
            command.update(
                {
                    "status": acquired_status,
                    "condition": self._lock_store[lock_id]["condition"],
                }
            )
        self._dump_state()

    def _read_state_machine_queue(self):
        while True:
            try:
                message = self._sm_queue.get()
                if message.is_valid:
                    index = message.index
                    command = message.command
                    # Setting status to True, return True in case
                    # command has already been executed by SM
                    command.update(
                        {
                            "status": True,
                            "condition": None,
                        }
                    )
                    self.logger.debug(
                        "message {}, index {}, command {}".format(
                            message, index, command
                        )
                    )
                    with self._lock:
                        last_request_id = self._last_applied.get(command["client_id"])
                        if (
                            last_request_id is None
                            or command["request_id"] > last_request_id
                        ):
                            self._apply_to_state_machine(command)
                            self._last_applied[command["client_id"]] = command[
                                "request_id"
                            ]

                        self._result[index].put(command)
                        self._dump_state()
            except Exception as ex:
                self.logger.debug(
                    "Exception {} in state machine reader thread", format(ex)
                )

    def _wait_till_applied(self, cmd):
        index, term, is_leader = self._raft._handle_command(cmd)
        self.logger.debug(
            "Result of handle_command index {}, term {}, is_leader {}".format(
                index, term, is_leader
            )
        )
        if not is_leader:
            return lstream_pb2.LockOpReply(
                lock_id=cmd["lock_id"],
                is_leader=False,
                is_timedout=False,
                is_successful=False,
                client_id=cmd["client_id"],
                request_id=int(cmd["request_id"]),
                is_valid=False,
            )
        command, queue = None, None
        with self._lock:
            queue = self._result[index]

        def _is_valid(command):
            return (
                cmd["client_id"] == command["client_id"]
                and cmd["request_id"] == command["request_id"]
            )

        try:
            command = queue.get(timeout=STATEMACHINE_QUEUE_WAIT_TIME)
            # 2 minute Lock acquire timeout
            lock_wait_until = round(time.time() * 1000) + 2 * 60 * 1000
            self.logger.debug("cmd {} command {}".format(cmd, command))
            if command["op"] == "acquire" and command["status"]:
                self.logger.debug(
                    "Lock {} has been acquired".format(command["lock_id"])
                )
                return lstream_pb2.LockOpReply(
                    lock_id=command["lock_id"],
                    is_leader=True,
                    is_timedout=False,
                    is_successful=True,
                    client_id=command["client_id"],
                    request_id=int(command["request_id"]),
                    is_valid=_is_valid(command),
                )
            elif command["op"] == "acquire" and not command["status"]:
                self.logger.debug(
                    "Lock {} is in acquired state, waiting for it to be released".format(
                        command["lock_id"]
                    )
                )
                while round(time.time() * 1000) < lock_wait_until:
                    with self._lock:
                        lock_status = self._lock_store[command["lock_id"]]["status"]
                        if not lock_status:
                            self._lock_store[command["lock_id"]]["status"] = True
                            self.logger.debug(
                                "Lock {} has been acquired".format(command["lock_id"])
                            )
                            return lstream_pb2.LockOpReply(
                                lock_id=command["lock_id"],
                                is_leader=True,
                                is_timedout=False,
                                is_successful=True,
                                client_id=command["client_id"],
                                request_id=int(command["request_id"]),
                                is_valid=_is_valid(command),
                            )
                    with command["condition"]:
                        command["condition"].wait(random.uniform(100, 200) / 1000)
                self.logger.debug("Lock {} acquire timedout".format(command["lock_id"]))
                return lstream_pb2.LockOpReply(
                    lock_id=command["lock_id"],
                    is_leader=True,
                    is_timedout=True,
                    is_successful=False,
                    client_id=command["client_id"],
                    request_id=int(command["request_id"]),
                    is_valid=_is_valid(command),
                )
            elif command["op"] == "release" and command["status"]:
                self.logger.debug(
                    "Lock {} has been released".format(command["lock_id"])
                )
                return lstream_pb2.LockOpReply(
                    lock_id=command["lock_id"],
                    is_leader=True,
                    is_timedout=False,
                    is_successful=True,
                    client_id=command["client_id"],
                    request_id=int(command["request_id"]),
                    is_valid=_is_valid(command),
                )
            elif command["op"] == "release" and not command["status"]:
                self.logger.debug(
                    "Lock {} has not been acquired earlier, invalid release ops".format(
                        command["lock_id"]
                    )
                )
                return lstream_pb2.LockOpReply(
                    lock_id=command["lock_id"],
                    is_leader=True,
                    is_timedout=False,
                    is_successful=False,
                    client_id=command["client_id"],
                    request_id=int(command["request_id"]),
                    is_valid=_is_valid(command),
                )

        except Empty:
            # This Might not be leader as it is not able to reply back
            # which might happen when it can not communicate to majority of
            # nodes and did not commit the entry.
            self.logger.debug("CMD {} timedout".format(cmd))
            return lstream_pb2.LockOpReply(
                lock_id=command["lock_id"],
                is_leader=False,
                is_timedout=True,
                is_successful=False,
                client_id=command["client_id"],
                request_id=int(command["request_id"]),
                is_valid=False,
            )

    def acquire(self, request, context):
        cmd = {
            "op": "acquire",
            "lock_id": request.lock_id,
            "client_id": str(request.client_id),
            "request_id": str(request.request_id),
        }
        result = self._wait_till_applied(cmd)
        return result

    def release(self, request, context):
        cmd = {
            "op": "release",
            "lock_id": request.lock_id,
            "client_id": str(request.client_id),
            "request_id": str(request.request_id),
        }
        result = self._wait_till_applied(cmd)
        return result
