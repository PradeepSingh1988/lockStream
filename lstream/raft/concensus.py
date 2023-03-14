import copy
import datetime
import logging
import random
from threading import Condition, Event, Lock, Thread
import time

from google.protobuf import json_format

from lstream.raft.consts import (
    CANDIDATE,
    ELECTION_TIMEOUT_RANGE_START,
    ELECTION_TIMEOUT_RANGE_END,
    FOLLOWER,
    HEARTBEAT_PERIOD,
    LEADER,
)
from lstream.common.logger import CustomAdapter
from lstream.common.rpc_client import ConnectionFailedException, RPCFailedError
from lstream.proto import raft_pb2, raft_pb2_grpc
from lstream.raft.raft_log import NO_OP_COMMAND, RaftLogEntry
from lstream.raft.reponse import LogAppliedReply
from lstream.raft.rpc_client import RaftNodeClient
from lstream.raft.state import RaftState


class RaftConsensus(raft_pb2_grpc.RaftConsensusServiceServicer):
    def __init__(self, peers, me, output_queue, persister):
        self._state = RaftState()
        self._persister = persister
        # List of all nodes, this list will be same for all nodes.
        self._peers = peers
        self._op_queue = output_queue

        # My index in peers list
        self._me = me

        # in memory state for all servers
        self.commit_index = 0
        self.last_applied = 0

        # in memory state for leaders
        self.next_index = [self._state.logs.get_last_log_index() + 1] * len(self._peers)
        self.match_index = [0] * len(self._peers)

        # other in memory states
        self.node_state = FOLLOWER
        self.vote_count = 0

        # A TCP Keep ALIVE connection MAP for all nodes except me
        # Connection will be opened only when first RPC call is made.
        self._connection_map = {
            peer: RaftNodeClient(peer[0], peer[1])
            for index, peer in enumerate(peers)
            if index != self._me
        }
        self._exit = Event()
        self._state_lock = Lock()
        self._max_time = round(time.time() * 1000) + round(
            (datetime.timedelta(days=20 * 365).total_seconds() * 1000)
        )
        self.logger = CustomAdapter(
            logging.getLogger(__name__),
            {"logger": "{}:{}".format("RAFTNODE", self._me)},
        )
        self._start_election_at = self._max_time
        self._send_heartbeat_at = self._max_time
        self._election_condition = Condition()
        self._heartbeat_condition = Condition()
        self._leader_id = -1
        self._read_persisted_state()
        self._become_follower(self._state.term)
        self._persist_metadata()
        if self._state.logs.is_empty():
            self._state.logs.add([RaftLogEntry(0, NO_OP_COMMAND)])
            self._persist_log_entries()
        self._election_thread = Thread(target=self._start_election_thread).start()
        self._leader_thread = Thread(target=self._start_leader_thread).start()

    def _am_i_single(self):
        return len(self._peers) == 1

    def _persist_metadata(self):
        self._persister.update_metadata(self._state.term, self._state.voted_for)

    def _persist_log_entries(self):
        # Not efiicient. overwriting every log.
        self.logger.debug(
            "Persisting {} log entries".format(
                self._state.logs.get_last_log_index() + 1
            )
        )
        self._persister.write_logs(self._state.logs.get_entries(0))

    def _read_persisted_state(self):
        metadata = self._persister.read_metadata()
        self._state.term, self._state.voted_for = metadata[0], metadata[1]
        for log in self._persister.read_logs():
            self.logger.debug("Log during read is {}".format(log))
            self._state.logs.add([log])

    def _set_heartbeat_timer(self):
        self._send_heartbeat_at = round(time.time() * 1000) + HEARTBEAT_PERIOD
        self.logger.debug(
            "Send next heartbeat at {} i.e. after {} milisececonds".format(
                datetime.datetime.fromtimestamp(
                    self._send_heartbeat_at / 1000
                ).strftime("%H:%M:%S,%f")[:-3],
                HEARTBEAT_PERIOD,
            )
        )
        with self._heartbeat_condition:
            self._heartbeat_condition.notify_all()

    def _set_election_timer(self):
        random_millisecond = random.uniform(
            ELECTION_TIMEOUT_RANGE_START, ELECTION_TIMEOUT_RANGE_END
        )
        self._start_election_at = round(time.time() * 1000) + random_millisecond
        self.logger.debug(
            "Set next election at {} i.e. after {} milisececonds".format(
                datetime.datetime.fromtimestamp(
                    self._start_election_at / 1000
                ).strftime("%H:%M:%S,%f")[:-3],
                random_millisecond,
            )
        )
        with self._election_condition:
            self._election_condition.notify_all()

    def _get_peer_index(self, peer):
        return self._peers.index(peer)

    def _dump_log_data(self):
        self.logger.debug(
            "next_index {}, match_index {}, commit_index {}".format(
                self.next_index, self.match_index, self.commit_index
            )
        )
        self.logger.debug("Logs {}".format(self._state.logs))

    def _start_new_election(self):
        with self._state_lock:
            if self.node_state == CANDIDATE:
                self.logger.debug(
                    "Running for election for term {}, previous candidacy for term {} timed out".format(
                        self._state.term + 1, self._state.term
                    )
                )
            elif self._leader_id > -1:
                self.logger.debug(
                    "Running for election again in term {}, Havent heard anything from leader".format(
                        self._state.term + 1
                    )
                )
            else:
                self.logger.debug(
                    "Running for election in term {}".format(self._state.term)
                )

            self._become_candidate()

    def _start_election_thread(self):
        self.logger.debug(
            "STARTING with term {}, voted for {} and logs len {}".format(
                self._state.term,
                self._state.voted_for,
                self._state.logs.get_last_log_index() + 1,
            )
        )
        # Execute Become Follower before this
        while not self._exit.is_set():
            with self._election_condition:
                if round(time.time() * 1000) > self._start_election_at:
                    self._start_new_election()
                self._election_condition.wait(
                    (self._start_election_at - round(time.time() * 1000)) / 1000
                )

    def _start_leader_thread(self):
        while not self._exit.is_set():
            with self._state_lock:
                self.logger.debug(
                    "{} {}".format(round(time.time() * 1000), self._send_heartbeat_at)
                )
                if (
                    self.node_state == LEADER
                    and round(time.time() * 1000) > self._send_heartbeat_at
                ):
                    self._broadcast_append_entries()
            with self._heartbeat_condition:
                self._heartbeat_condition.wait(
                    (self._send_heartbeat_at - round(time.time() * 1000)) / 1000
                )

    def _become_follower(self, term):
        assert self._state.term <= term
        if self._state.term < term:
            self.logger.debug("Stepping down for term {}".format(term))
            self.node_state = FOLLOWER
            self._state.term = term
            self._state.voted_for = -1
            self._leader_id = -1
        else:
            if self.node_state != FOLLOWER:
                self.logger.debug(
                    "Stepping down for term {} as peer's and mine terms are equal".format(
                        term
                    )
                )
                self.node_state = FOLLOWER
        self._send_heartbeat_at = self._max_time
        with self._heartbeat_condition:
            self._heartbeat_condition.notify_all()
        self._log_election_state()
        # Its Begining or It was leader earlier
        if self._start_election_at == self._max_time:
            self._set_election_timer()

    def _log_election_state(self):
        self.logger.debug(
            "server={}, term={}, state={}, leader={}, vote={}".format(
                self._me,
                self._state.term,
                self.node_state,
                self._leader_id,
                self._state.voted_for,
            )
        )

    def _become_candidate(self):
        self._state.term += 1
        self.node_state = CANDIDATE
        self._leader_id = -1
        self.vote_count = 1
        self._state.voted_for = self._me
        self._persist_metadata()
        self._log_election_state()
        self._set_election_timer()
        # Become leader in case if I am the only server
        if self.vote_count == len(self._peers) // 2 + 1:
            self.logger.debug("Becoming LEADER")
            self._become_leader()
        else:
            self._broadcast_request_vote()

    def _become_leader(self):
        if self.node_state != CANDIDATE:
            return
        self.logger.debug("Becoming leader for term {}".format(self._state.term))
        self.node_state = LEADER
        self._leader_id = self._me
        self._start_election_at = self._max_time
        last_index = self._state.logs.get_last_log_index() + 1
        for index, _ in enumerate(self._peers):
            self.next_index[index] = last_index
        self.match_index = [0] * len(self._peers)
        self._state.logs.add([RaftLogEntry(self._state.term, NO_OP_COMMAND)])
        self._persist_log_entries()
        if self._am_i_single():
            self.commit_index = self._state.logs.get_last_log_index()
            self._apply_logs()
        else:
            self._broadcast_append_entries()

    def _broadcast_request_vote(self):
        for peer in self._connection_map.keys():
            self.logger.debug("Connecting to {} for RPC call request_vote".format(peer))
            term = self._state.term
            candidate_id = self._me
            last_log_index = self._state.logs.get_last_log_index()
            last_log_term = self._state.logs.get_last_log_term()
            Thread(
                target=self._send_request_vote,
                args=(peer, term, candidate_id, last_log_index, last_log_term),
            ).start()

    def _send_request_vote(
        self, peer, term, candidate_id, last_log_index, last_log_term
    ):
        self.logger.debug(
            "Sending reuest_vote RPC tp peer {} with term {}, last_log_index {}, last_log_term {}".format(
                peer, term, last_log_index, last_log_term
            )
        )
        try:
            reply = self._connection_map[peer].request_vote(
                term, candidate_id, last_log_index, last_log_term
            )
        except (ConnectionFailedException, RPCFailedError) as ex:
            self.logger.debug("RPC call to peer {} failed due to {} ".format(peer, ex))
            return
        self.logger.debug(
            "Recieved reuest_vote RPC response from peer {} with term {} and vote status {}".format(
                peer, reply.term, reply.voted_yes
            )
        )
        with self._state_lock:
            if self.node_state != CANDIDATE:
                self.logger.debug(
                    "I am not candidate for term {} now, ignoring peer {} vote response ".format(
                        self._state.term, peer
                    )
                )
                return
            if self._state.term != term:
                self.logger.debug(
                    "My term is changed: old-term {}, new-term {}, ignoring peer {} vote response ".format(
                        term, self._state.term, peer
                    )
                )
                return
            if reply.term < self._state.term:
                self.logger.debug(
                    "Peer's {} term is lower than my term {}, ignoring peer {} vote response ".format(
                        reply.term, peer, self._state.term
                    )
                )
                return
            if reply.term > self._state.term:
                self.logger.debug(
                    "Peer's {} term is higher thatn mine, becoming FOLLOWER with term {}".format(
                        peer, reply.term
                    )
                )
                self._become_follower(term)
                self._persist_metadata()
                return
            if reply.voted_yes:
                self.logger.debug(
                    "Vote granted by Peer {} for term {}".format(peer, self._state.term)
                )
                self.vote_count += 1
                if self.vote_count == len(self._peers) // 2 + 1:
                    self.logger.debug("Becoming LEADER")
                    self._become_leader()
            else:
                self.logger.debug(
                    "Vote denied by Peer {} for term {}".format(peer, self._state.term)
                )

    def _broadcast_append_entries(self):
        if self.node_state != LEADER:
            return
        for peer in self._connection_map.keys():
            index = self._get_peer_index(peer)
            term = self._state.term
            leader_id = self._me
            prev_log_index = self.next_index[index] - 1
            prev_log_term = self._state.logs.get_term_at_index(prev_log_index)
            entries = self._state.logs.get_entries(self.next_index[index])
            Thread(
                target=self._send_append_entries,
                args=(
                    peer,
                    term,
                    leader_id,
                    prev_log_index,
                    prev_log_term,
                    self.commit_index,
                    entries,
                ),
            ).start()
        self._set_heartbeat_timer()

    def _send_append_entries(
        self,
        peer,
        term,
        leader_id,
        prev_log_index,
        prev_log_term,
        commit_index,
        entries,
    ):
        self.logger.debug(
            "Sending append_entry RPC to peer {} with trm {}, pli {}, plt {}, ci {}, en {}".format(
                peer, term, prev_log_index, prev_log_term, commit_index, entries
            )
        )
        try:
            reply = self._connection_map[peer].append_entries(
                term, leader_id, prev_log_index, prev_log_term, commit_index, entries
            )
        except (ConnectionFailedException, RPCFailedError) as ex:
            self.logger.debug("RPC call to peer {} failed due to {} ".format(peer, ex))
            return

        self.logger.debug(
            "Recieved append_entry RPC Response from  peer {} with trm {}, ct {}, ci {}, success {}".format(
                peer,
                reply.term,
                reply.conflicting_term,
                reply.conflicting_index,
                reply.success,
            )
        )
        index = self._get_peer_index(peer)
        with self._state_lock:
            if self._state.term != term:
                self.logger(
                    "My old term {} is not same as new term {}, ignoring RPC response".format(
                        term, self._state.term
                    )
                )
                return
            # Since term did not changed and we were leader before,
            # we must be leader now
            assert self.node_state == LEADER
            if reply.term > self._state.term:
                self._become_follower(reply.term)
                self._persist_metadata()
                return
            else:
                # Reply term should be same as my term as i am leader for the term
                assert self._state.term == reply.term

                if reply.success:
                    # Applied Entries
                    peer_match_index = prev_log_index + len(entries)
                    if peer_match_index > self.match_index[index]:
                        self.match_index[index] = peer_match_index
                    self.next_index[index] = self.match_index[index] + 1
                elif reply.conflicting_term < 0:
                    # Followers log is shorter, follower has returned
                    # conflicting index, leader has to resend the missing
                    # logs to follower.
                    self.next_index[index] = reply.conflicting_index
                    self.match_index[index] = self.next_index[index] - 1
                else:
                    # conflicting term and conflicting index are greater than -1.
                    # back track our log to find the first index with conflicting term.
                    # if conflicting term is not found then set FOLLOWER's next_index
                    # to conflicting index. Otherwise set nex_index to found index.
                    peer_next_index = self._state.logs.get_last_log_index()
                    found_index = -1
                    for i in range(peer_next_index, -1, -1):
                        if (
                            self._state.logs.get_term_at_index(i)
                            == reply.conflicting_term
                        ):
                            found_index = i
                            break
                    if found_index == -1:
                        self.next_index[index] = reply.conflicting_index
                    else:
                        self.next_index[index] = found_index
                    self.match_index[index] = self.next_index[index] - 1
                self._dump_log_data()

                # If more than half of nodes has match_index greater than
                # or equal my commit index then apply the log entries to state machine
                for i in range(
                    self._state.logs.get_last_log_index(), self.commit_index - 1, -1
                ):
                    count = 1
                    if self._state.logs.get_term_at_index(i) == self._state.term:
                        for j in range(len(self._peers)):
                            if j != self._me and self.match_index[j] >= i:
                                count += 1
                    if count >= len(self._peers) // 2 + 1:
                        self.commit_index = i
                        self._apply_logs()
                        break

    def _is_log_uptodate(self, c_last_log_index, c_last_log_term):
        my_last_index = self._state.logs.get_last_log_index()
        my_last_term = self._state.logs.get_last_log_term()

        if c_last_log_term > my_last_term:
            return True
        elif c_last_log_term == my_last_term:
            return c_last_log_index >= my_last_index
        else:
            return False

    def handle_request_vote(self, request, context):
        # c_term, candidate_id, c_last_log_index, c_last_log_term
        with self._state_lock:
            self.logger.debug(
                "Recieved request vote from peer {} with term {} for my term {}".format(
                    request.c_id, request.c_term, self._state.term
                )
            )
            # If candidate's term is less then mine, dont vote for this candidate.
            if request.c_term < self._state.term:
                self.logger.debug(
                    "Requesting Vote Server's term {} is less than mine term {}".format(
                        request.c_term, self._state.term
                    )
                )
                return raft_pb2.AskForVoteReply(term=self._state.term, voted_yes=False)

            # If candidate's term is higher then mine, become follower.
            if request.c_term > self._state.term:
                self.logger.debug(
                    "Requesting Vote Server's term {} is higher than mine term {}, becoming follower".format(
                        request.c_term, self._state.term
                    )
                )
                self._become_follower(request.c_term)
                self._persist_metadata()

            # Below two conditions ensures that a server can vote to only
            # one candidate in a given term.

            # if terms are equal and not voted for anyone, check if candidate's
            # logs are upto date, if yes, then vote it.
            if request.c_term == self._state.term:
                if (
                    self._is_log_uptodate(
                        request.c_last_log_index, request.c_last_log_term
                    )
                    and self._state.voted_for == -1
                ):
                    self._become_follower(request.c_term)
                    self._state.voted_for = request.c_id
                    self._persist_metadata()
                    self._set_election_timer()

            # If candidate's term is same as mine and already voted it once
            # in the same term vote it again. This may happen due to
            # duplicate request from same candidate.
            if (
                self._state.term == request.c_term
                and self._state.voted_for == request.c_id
            ):
                self.logger.debug(
                    "Voting for peer {} with term {} for my term {} ".format(
                        request.c_id, request.c_term, self._state.term
                    )
                )
                return raft_pb2.AskForVoteReply(term=self._state.term, voted_yes=True)

            # Else reject the vote
            else:
                self.logger.debug(
                    "Denying Vote for peer {} with term {} for my term {} ".format(
                        request.c_id, request.c_term, self._state.term
                    )
                )
                return raft_pb2.AskForVoteReply(term=self._state.term, voted_yes=False)

    def handle_append_entries(self, request, context):
        with self._state_lock:
            self.logger.debug(
                "Recieved append entries req from peer {} with lt:{}, mt:{}, pli:{}, ci{}".format(
                    request.leader_id,
                    request.term,
                    self._state.term,
                    request.prev_log_index,
                    request.commit_index,
                )
            )

            # If leader's term is less than mine, then leader is not legitmate one.
            # Reject appen entries.
            if request.term < self._state.term:
                self.logger.debug(
                    "Caller's term {} is stale, my term {} is higher than them".format(
                        request.term, self._state.term
                    )
                )
                return raft_pb2.AppendEntriesReply(
                    success=False,
                    conflicting_index=-1,
                    conflicting_term=-1,
                    term=self._state.term,
                )

            # If leader's term is greater than or equal to mine,
            # then become follower.
            if request.term >= self._state.term:
                self._become_follower(request.term)
                self._persist_metadata()
            self._set_election_timer()

            # If no leader, set leader id
            if self._leader_id == -1:
                self._leader_id = request.leader_id
                self.logger.debug(
                    "Peer {} is leader for the term {}".format(
                        request.leader_id, self._state.term
                    )
                )
                self._log_election_state()
            else:
                # Since there can be only one leader in a given term
                # my leader id must be equal to this leader
                assert request.leader_id == self._leader_id

            last_index = self._state.logs.get_last_log_index()
            conflicting_term, conflicting_index, success = -1, -1, False

            # My log is shorter than leader's log, If i commit then there will be holes
            # Reject append entries. Send next log's index i.e. last_index + 1 alongwith
            # current term in response as well.
            if request.prev_log_index > last_index:
                self.logger.debug(
                    "Append entry request denied as leader last index {} is greater than mine {}".format(
                        request.prev_log_index, last_index
                    )
                )
                self._dump_log_data()
                return raft_pb2.AppendEntriesReply(
                    success=False,
                    conflicting_index=last_index + 1,
                    conflicting_term=-1,
                    term=self._state.term,
                )

            # Now two cases,
            # 1) my last index is equal to previous_log_index
            # 2) my last index is greater than previous_log_index

            # if my term at previous_log_index is equal to prevous_log_term
            # Then all log entries upto previous_log_index are in sync.

            # If term at previous_log_index is not equal to prevous_log_term
            # Then trverse back the log to find the first index with the
            # conflicting term. And reply with conflicting term and conflicting index
            if (
                self._state.logs.get_term_at_index(request.prev_log_index)
                != request.prev_log_term
            ):
                conflicting_term = self._state.logs.get_term_at_index(
                    request.prev_log_index
                )
                for index in range(request.prev_log_index, -1, -1):
                    if self._state.logs.get_term_at_index(index) == conflicting_term:
                        conflicting_index = index

                return raft_pb2.AppendEntriesReply(
                    success=success,
                    conflicting_index=conflicting_index,
                    conflicting_term=conflicting_term,
                    term=self._state.term,
                )

            # Term at term at previous_log_index is equal to prevous_log_term
            # If my last index is equal to previous_log_index then logs will be appended
            # If my last index is greater than previous_log_index, logs may be truncated

            # compare entries at prev_log_index + 1 to last_index + 1 with logs in entries
            # find the points in my log and entries from whom the logs atrt to differ
            last_maching_index, last_maching_entry = request.prev_log_index + 1, 0
            for i in range(request.prev_log_index + 1, last_index + 1):
                for j in range(0, len(request.entries)):
                    if self._state.logs.get_term_at_index(i) != request.entries[j].term:
                        last_maching_index, last_maching_entry = i, j
                        break
            self.logger.debug(
                "last_maching_index {}, last_maching_entry {}".format(
                    last_maching_index, last_maching_entry
                )
            )

            # Truncate the non matching logs and append the logs from entries to my log
            self._state.logs.truncate_logs(last_maching_index)
            entries = request.entries[last_maching_entry:]
            self._state.logs.add(
                [
                    RaftLogEntry(entry.term, json_format.MessageToDict(entry.command))
                    for entry in entries
                ]
            )
            success = True
            self.logger.debug(
                "Leader commit index {}, mine commit index {}".format(
                    request.commit_index, self.commit_index
                )
            )
            if entries:
                self._persist_log_entries()
            self._dump_log_data()

            # Commit the logs
            if request.commit_index > self.commit_index:
                last_index = self._state.logs.get_last_log_index()
                if request.commit_index < last_index:
                    self.commit_index = request.commit_index
                else:
                    self.commit_index = last_index
                self._apply_logs()
            return raft_pb2.AppendEntriesReply(
                success=success,
                conflicting_index=conflicting_index,
                conflicting_term=conflicting_term,
                term=self._state.term,
            )

    def _handle_command(self, command):
        with self._state_lock:
            if self.node_state == LEADER and self._leader_id == self._me:
                previous_index = self._state.logs.get_last_log_index() + 1
                self.next_index[self._me] = previous_index + 1
                self.match_index[self._me] = previous_index
                log_entries = [RaftLogEntry(self._state.term, command)]
                self._state.logs.add(log_entries)
                self._persist_log_entries()
                if self._am_i_single():
                    self.commit_index += 1
                    self._apply_logs()
                else:
                    self._broadcast_append_entries()
                return self._state.logs.get_last_log_index(), self._state.term, True
            else:
                return -1, self._state.term, False

    def _apply_logs(self):
        def _apply():
            with self._state_lock:
                for i in range(self.last_applied + 1, self.commit_index + 1):
                    self.logger.debug(
                        "index {}, last_applied {}, commit_index {}".format(
                            i, self.last_applied, self.commit_index
                        )
                    )
                    command = self._state.logs.get_command_at_index(i)
                    if command != NO_OP_COMMAND:
                        self._op_queue.put(
                            copy.deepcopy(LogAppliedReply(True, command, i))
                        )
                    self.last_applied = i

        Thread(target=_apply).start()
