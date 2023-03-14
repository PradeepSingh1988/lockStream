from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AppendEntriesReply(_message.Message):
    __slots__ = ["conflicting_index", "conflicting_term", "success", "term"]
    CONFLICTING_INDEX_FIELD_NUMBER: _ClassVar[int]
    CONFLICTING_TERM_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    conflicting_index: int
    conflicting_term: int
    success: bool
    term: int
    def __init__(self, success: bool = ..., conflicting_term: _Optional[int] = ..., conflicting_index: _Optional[int] = ..., term: _Optional[int] = ...) -> None: ...

class AppendEntriesRequest(_message.Message):
    __slots__ = ["commit_index", "entries", "leader_id", "prev_log_index", "prev_log_term", "term"]
    COMMIT_INDEX_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    commit_index: int
    entries: _containers.RepeatedCompositeFieldContainer[LogEntry]
    leader_id: int
    prev_log_index: int
    prev_log_term: int
    term: int
    def __init__(self, term: _Optional[int] = ..., leader_id: _Optional[int] = ..., prev_log_index: _Optional[int] = ..., prev_log_term: _Optional[int] = ..., commit_index: _Optional[int] = ..., entries: _Optional[_Iterable[_Union[LogEntry, _Mapping]]] = ...) -> None: ...

class AskForVoteReply(_message.Message):
    __slots__ = ["term", "voted_yes"]
    TERM_FIELD_NUMBER: _ClassVar[int]
    VOTED_YES_FIELD_NUMBER: _ClassVar[int]
    term: int
    voted_yes: bool
    def __init__(self, term: _Optional[int] = ..., voted_yes: bool = ...) -> None: ...

class AskForVoteRequest(_message.Message):
    __slots__ = ["c_id", "c_last_log_index", "c_last_log_term", "c_term"]
    C_ID_FIELD_NUMBER: _ClassVar[int]
    C_LAST_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    C_LAST_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    C_TERM_FIELD_NUMBER: _ClassVar[int]
    c_id: int
    c_last_log_index: int
    c_last_log_term: int
    c_term: int
    def __init__(self, c_term: _Optional[int] = ..., c_id: _Optional[int] = ..., c_last_log_index: _Optional[int] = ..., c_last_log_term: _Optional[int] = ...) -> None: ...

class LogEntry(_message.Message):
    __slots__ = ["command", "term"]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    TERM_FIELD_NUMBER: _ClassVar[int]
    command: _struct_pb2.Struct
    term: int
    def __init__(self, term: _Optional[int] = ..., command: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...
