import socket
import select
import sys
import threading
import time
import random
import pickle

import constants
    
def enter_error(string):
    print(f'Warning: {string}')

self_id = int(sys.argv[1]) # Client ID in range(5)
port = constants.CLIENT_PORT_PREFIX + self_id
soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
soc.setblocking(False)
soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
soc_send = []
for i in range(constants.NUM_CLIENT):
    temp_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc_send.append(temp_soc)
soc.bind((constants.HOST,port))

soc.listen(constants.NUM_CLIENT)
inputSockets = [soc.fileno(), sys.stdin.fileno()]
send_list = []
run = 1
snapshot_dict = {}
current_requests_channel  = {}
has_token = False # current state of the client
token_string = "" # current state of the client
prob = 0 # probability of losing the token before receiving it
snapshot_counter = 0
local_snapshots = {}

# send a string over socket via padding
def padding(length):
    singlebyte = b'\xff'
    return b''.join([singlebyte for i in range(length)])

def header_s(x):
    s = str(x)
    if len(s) > constants.HEADER_SIZE:
        enter_error('Header too big!')
    while(len(s) < constants.HEADER_SIZE):
        s = '0' + s
    return s.encode()

def send_padded_msg(sock, msg):
    encoded_msg = msg.encode()
    num_bytes = len(encoded_msg)
    header = header_s(num_bytes)
    if num_bytes > constants.MESSAGE_SIZE - len(header):
        enter_error('Message too big!')
    padding_length = constants.MESSAGE_SIZE - num_bytes - len(header)
    padded_msg = b''.join([header, encoded_msg, padding(padding_length)])
    sock.sendall(padded_msg)

def send_padded_msg_ss(sock, msg, snapshot):
    encoded_msg = msg.encode()
    num_bytes = len(encoded_msg)
    num_bytes_ss = len(snapshot)
    header = header_s(num_bytes)
    header_ss = header_s(num_bytes_ss)
    if num_bytes + num_bytes_ss > constants.MESSAGE_SIZE - len(header) - len(header_ss):
        enter_error('Message too big!')
    padding_length = constants.MESSAGE_SIZE - num_bytes - num_bytes_ss - len(header) - len(header_ss)
    padded_msg = b''.join([header, encoded_msg, header_ss, snapshot, padding(padding_length)])
    sock.sendall(padded_msg)

def snapshot():
    global snapshot_dict
    global snapshot_counter
    global local_snapshots
    snapshot_tag = (self_id,snapshot_counter)
    snapshot_dict[snapshot_tag] = SnapshotState(snapshot_tag)
    if snapshot_tag in local_snapshots:
        enter_error('snapshot already started')
    local_snapshots[snapshot_tag] = {}
    data = ["ss",str(self_id),str(self_id),str(snapshot_counter)]
    for i in constants.CONNECTION_GRAPH[self_id]:
        send_padded_msg(soc_send[i], ' '.join(data))
        # soc_send[i].sendall(' '.join(data).encode())
        print("Sent snapshot {} marker to {}".format(data, i))
    snapshot_counter += 1

# Object that keeps the state of a snapshot
class SnapshotState:
    def __init__(self, snapshot_tag):
        self.snapshot_tag = snapshot_tag
        if has_token:
            self.state = token_string
        else:
            self.state = ""
        self.incoming_channels = {str(key): [] for key in constants.INCOMING_GRAPH[self_id]} # state of incoming channels
        self.record_channels = {str(key): True for key in constants.INCOMING_GRAPH[self_id]} # currently recoding incoming channels
    def print_ss(self):
        print("SS tag: {}".format(self.snapshot_tag))
        print("SS state: {}".format(self.state))
        print("SS incoming channels: {}".format(self.incoming_channels))
        print("SS record channels: {}".format(self.record_channels))
    def to_string(self):
        json_obj = pickle.dumps(self)
        return json_obj
    def is_complete(self):
        for key in self.record_channels:
            if self.record_channels[key]:
                return False
        return True
        
# Called after receiving the first marker during a snapshot.
def snapshot_initiate(data):
    time.sleep(constants.MESSAGE_DELAY)
    global snapshot_dict
    sender_id, initiator_id, snapshot_id = data[1:4]
    snapshot_tag = (int(initiator_id), int(snapshot_id))
    if snapshot_tag in snapshot_dict: 
        enter_error('snapshot_initiate called for already initiated snapshot.')
        snapshot_continue(data)
    else:
        print(f'Recording for snapshot {snapshot_tag} started.')
        snapshot_dict[snapshot_tag] = SnapshotState(snapshot_tag)
        data[1] = str(self_id)
        for i in constants.CONNECTION_GRAPH[self_id]:
            send_padded_msg(soc_send[i],' '.join(data))
            # soc_send[i].sendall(' '.join(data).encode())
            print("Sent snapshot {} marker to {}".format(data,i))
        snapshot_dict[snapshot_tag].record_channels[str(sender_id)] = False
        check_completion(snapshot_tag) # check if snapshot is complete


# Called after receiving any subsequent marker during a snapshot.
def snapshot_continue(data):
    time.sleep(constants.MESSAGE_DELAY)
    global snapshot_dict
    sender_id, initiator_id, snapshot_id = data[1:4]
    snapshot_tag = (int(initiator_id), int(snapshot_id))
    if snapshot_tag not in snapshot_dict: 
        enter_error('snapshot_continue called for uninitiated snapshot.')
    snapshot_dict[snapshot_tag].record_channels[str(sender_id)] = False
    check_completion(snapshot_tag) # check if snapshot is complete

def check_completion(snapshot_tag):
    global snapshot_dict
    initiator_id = snapshot_tag[0]
    snapshot_completed = snapshot_dict[snapshot_tag].is_complete()
    if snapshot_completed:
        print(f'Recording for snapshot {snapshot_tag} completed.')
        if initiator_id == self_id:
            local_snapshots[snapshot_tag][self_id] = snapshot_dict[snapshot_tag]
            if len(local_snapshots[snapshot_tag]) == constants.NUM_CLIENT:
                snapshot_print(snapshot_tag)
        else:
            message = "snapshot " + str(self_id)
            snapshot =  snapshot_dict[snapshot_tag].to_string()
            send_padded_msg_ss(soc_send[initiator_id], message, snapshot)
            # snapshot_dict.pop(snapshot_tag)
        #TODO:Delete from dictionary

def token(token_string):
    print("initiated token {}".format(token_string))
    token_list = ["Token", token_string, str(self_id)]
    handle_token(token_list)

#connect to all clients
def initiate():
    for i in range(constants.NUM_CLIENT):
        if i != self_id:
            soc_send[i].connect((constants.HOST, constants.CLIENT_PORT_PREFIX+i))
            send_padded_msg(soc_send[i],"Connection request from {}".format(self_id))
            received = soc_send[i].recv(constants.MESSAGE_SIZE)
            print(received)

def snapshot_print(snapshot_tag):
    print("Printing snapshot {}:".format(snapshot_tag))
    for i in local_snapshots[snapshot_tag]:
        print("Snapshot {} for client {}:".format(snapshot_tag,i))
        local_snapshots[snapshot_tag][i].print_ss()

def recieved_ss(json_obj,client_id):
    snapshot_state = pickle.loads(json_obj)
    # snapshot_state.print_ss()
    snapshot_tag = snapshot_state.snapshot_tag
    local_snapshots[snapshot_tag][client_id] = snapshot_state
    if len(local_snapshots[snapshot_tag]) == constants.NUM_CLIENT:
        snapshot_print(snapshot_tag)

#pass token
def handle_token(data):
    time.sleep(constants.MESSAGE_DELAY)
    global has_token
    global token_string
    print("Received "+' '.join(data))
    has_token = True
    token_string = data[1]
    for key in snapshot_dict:
        if snapshot_dict[key].record_channels[data[2]]:
            snapshot_dict[key].incoming_channels[data[2]].append(data)
    fail = random.choices([True,False],weights = (prob,1-prob), k=1)
    if fail[0]:
        print(' '.join(data) + " lost")
    else:
        next = random.choice(constants.CONNECTION_GRAPH[self_id])
        print("Sending token to {}".format(next))
        data[2] = str(self_id)
        send_padded_msg(soc_send[next],' '.join(data))
    has_token = False
    token_string = ""

def print_all():
    for key in snapshot_dict:
        snapshot_dict[key].print_ss()

while run:
    inputready, outputready, exceptready = select.select(inputSockets, [], [])

    for x in inputready:
        if x == soc.fileno(): # input received via keyboard
            client, address = soc.accept()
            inputSockets.append(client)
        elif x == sys.stdin.fileno(): # input received via keyboard
            request = sys.stdin.readline().split()
            if len(request) == 0:
                continue
            if request[0] == "exit":
                run = 0
            elif request[0] == "i":
                initiate()
            elif request[0] == "ss":
                thread = threading.Thread(target=snapshot, daemon=True)
                thread.start()
            elif request[0] == "token":
                thread = threading.Thread(target=token, args=(request[1],), daemon=True)
                thread.start()
            elif request[0] == "prob":
                prob = float(request[1])
                print("Updated failure probability to {}".format(prob))
            elif request[0] == "print":
                thread = threading.Thread(target=print_all, daemon=True)
                thread.start()
            else:
                print("Invalid command") 
        else:   # data received from socket
            # "ss {#client_num} {#initial_client_num} {#snapshot_id}"
            # "t {token_string}"
            msg_received = x.recv(constants.MESSAGE_SIZE)
            if len(msg_received) != constants.MESSAGE_SIZE:
                enter_error('Incorrectly padded message received.')
            num_bytes = int(msg_received[:constants.HEADER_SIZE].decode())
            msg = msg_received[constants.HEADER_SIZE:constants.HEADER_SIZE + num_bytes].decode()
            # pad every message such that the first constants.HEADER_SIZE bytes is the number of remaining useful bytes,
            # and it is padded to have constants.MESSAGE_SIZE bytes total. 

            if len(msg) >= 8 and msg[:8] == 'snapshot': # completed snapshot
                client_id = int(msg[9])
                num_bytes_ss = int(msg_received[constants.HEADER_SIZE + num_bytes:2*constants.HEADER_SIZE + num_bytes].decode())
                json_obj = msg_received[2*constants.HEADER_SIZE + num_bytes:2*constants.HEADER_SIZE + num_bytes + num_bytes_ss]
                print("Received completed snapshot {} from {}".format(snapshot_tag, client_id))
                thread = threading.Thread(target=recieved_ss, args=(json_obj,client_id,), daemon=True)
                thread.start()


            else:
                data = msg.split()
                # record message all current channels: append to dictionary
                if data[0] == "ss": # snapshot marker
                    snapshot_tag = (int(data[2]),int(data[3]))
                    if snapshot_tag in snapshot_dict:
                        thread = threading.Thread(target=snapshot_continue, args=(data,), daemon=True)
                        thread.start()
                    else:
                        thread = threading.Thread(target=snapshot_initiate, args=(data,), daemon=True)
                        thread.start()
                elif data[0] == "Connection": # socket connection
                    print(' '.join(data))
                    x.send("Successfully connected to {}".format(self_id).encode())
                elif data[0] == "Token": # token
                    thread = threading.Thread(target=handle_token, args=(data,), daemon=True)
                    thread.start()
                else:
                    enter_error('Received message that is incorrectly formatted.')
                    break
