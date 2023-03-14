NO_OP_COMMAND = {"NO_OP": "TRUE"}


class RaftLogEntry(object):
    __slots__ = ("term", "command")

    def __init__(self, term, command) -> None:
        self.term = term
        self.command = command

    def __repr__(self):
        return "(term {}, command {})".format(self.term, self.command)

    def to_dict(self):
        return {"term": self.term, "command": self.command}


class RaftLog(object):
    def __init__(self):
        self._logs = []

    def is_empty(self):
        return len(self._logs) == 0

    def __repr__(self):
        return "Logs: {}".format(self._logs)

    def truncate_logs(self, index):
        self._logs = self._logs[:index]

    def get_last_log_term(self):
        return self._logs[self.get_last_log_index()].term

    def get_term_at_index(self, index):
        return self.get_entry(index).term

    def get_entry(self, index):
        return self._logs[index]

    def get_entries(self, start, end=None):
        return self._logs[start:end] if end else self._logs[start:]

    def get_log_start_index(self):
        pass

    def get_last_log_index(self):
        return len(self._logs) - 1

    def add(self, entries):
        self._logs.extend(entries)

    def get_command_at_index(self, index):
        return self.get_entry(index).command
