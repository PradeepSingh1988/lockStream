# lockStream
A highly consistent distributed lock service based on [raft](https://raft.github.io/) consensus protocol.
It supports two APIs, `acquire` and `release`.

## Running lockStream

### Dependencies
lockStream uses grpc package for communication between client and server as well as its nodes. Please install it using below command.

```
pip install grpcio==1.51.1 grpcio-tools==1.51.1
```

### Starting lockStream server
controller.py module can be used to start the server.

Or we can use `run.sh` script to start the servers as well.
Currently the ports are hardcoded in controller.py.

```
bash lstream/run.sh
```


### Sending client requests

```
from lstream.client import LockServiceClient

client = LockServiceClient([("127.0.0.1", 17000), ("127.0.0.1", 18000), ("127.0.0.1", 19000)])

assert client.acquire("test") == True
assert client.release("test") == True
assert client.acquire("test") == True
assert client.release("test") == True
```


## Note
Implementation is just for education purpose.