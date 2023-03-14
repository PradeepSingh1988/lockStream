from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class LockOpReply(_message.Message):
    __slots__ = ["client_id", "is_leader", "is_successful", "is_timedout", "is_valid", "lock_id", "request_id"]
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    IS_LEADER_FIELD_NUMBER: _ClassVar[int]
    IS_SUCCESSFUL_FIELD_NUMBER: _ClassVar[int]
    IS_TIMEDOUT_FIELD_NUMBER: _ClassVar[int]
    IS_VALID_FIELD_NUMBER: _ClassVar[int]
    LOCK_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    client_id: str
    is_leader: bool
    is_successful: bool
    is_timedout: bool
    is_valid: bool
    lock_id: str
    request_id: int
    def __init__(self, lock_id: _Optional[str] = ..., is_leader: bool = ..., is_timedout: bool = ..., is_successful: bool = ..., client_id: _Optional[str] = ..., request_id: _Optional[int] = ..., is_valid: bool = ...) -> None: ...

class LockOpRequest(_message.Message):
    __slots__ = ["client_id", "lock_id", "request_id"]
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    LOCK_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    client_id: str
    lock_id: str
    request_id: int
    def __init__(self, lock_id: _Optional[str] = ..., client_id: _Optional[str] = ..., request_id: _Optional[int] = ...) -> None: ...
