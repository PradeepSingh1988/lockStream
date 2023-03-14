import copy


class RequestVoteReply(object):
    __slots__ = ("term", "voted_yes", "reason")

    def __init__(self, term, vote, reason=""):
        self.term = term
        self.voted_yes = vote
        self.reason = reason


class AppendEntriesReply(object):
    __slots__ = ("success", "conflicting_index", "conflicting_term", "term")

    def __init__(self, success, conflicting_index, conflicting_term, term):
        self.success = success
        self.conflicting_index = conflicting_index
        self.conflicting_term = conflicting_term
        self.term = term


class LogAppliedReply(object):
    __slots__ = ("is_valid", "command", "index")

    def __init__(self, is_valid, command, index):
        self.is_valid = is_valid
        self.command = command
        self.index = index

    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "command": copy.deepcopy(self.command),
            "index": self.index,
        }
