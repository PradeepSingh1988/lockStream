from threading import Lock

from lstream.raft.raft_log import RaftLog


class RaftState(object):
    def __init__(self):
        # persistent state on all servers
        self.term = 0
        self.voted_for = -1
        self.logs = RaftLog()

    def load(self):
        return self

    def save(self):
        pass
