import json
import os
import struct
from threading import Lock

from google.protobuf import json_format
from google.protobuf.struct_pb2 import Struct


from lstream.raft.raft_log import NO_OP_COMMAND, RaftLogEntry

METADATA_FORMAT = "li"


class Persister(object):
    def __init__(self, file_path):
        self._lock = Lock()
        self.__create_file(file_path)
        self._metadata_size = struct.calcsize(METADATA_FORMAT)
        self.fh = open(file_path, "rb+")
        self._log_entries = 0

    def __create_file(self, file_path):
        if not os.path.isfile(file_path):
            with open(file_path, "wb"):
                pass

    def update_metadata(self, term, voted_for):
        with self._lock:
            metadata = struct.pack(METADATA_FORMAT, term, voted_for)
            self.fh.seek(0)
            self.fh.write(metadata)
            self.fh.flush()

    def read_metadata(self):
        with self._lock:
            self.fh.seek(0)
            metadata = self.fh.read(self._metadata_size)
            if metadata:
                return struct.unpack(METADATA_FORMAT, metadata)
            else:
                return 0, -1

    def read_logs(self):
        with self._lock:
            self.fh.seek(self._metadata_size)
            for log in self.fh.readlines():
                log = json.loads(log.strip().decode("utf-8"))
                yield RaftLogEntry(log["term"], log["command"])

    def write_logs(self, logs):
        with self._lock:
            self.fh.seek(self._metadata_size)
            for log in logs:
                encoded_logs = (json.dumps(log.to_dict()) + "\n").encode("utf-8")
                self.fh.write(encoded_logs)
                self.fh.flush()
