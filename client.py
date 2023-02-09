import socket
import select
import sys
import threading
import time
import random

import constants

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

#TODO: Check if needed
# def record_current_state():
#     current_state = has_token
#     enter_log(f'Recording current state: has_token = {has_token}')
#     return current_state


def snapshot():
    global snapshot_dict
    global snapshot_counter
    #TODO: implement snapshot id
    snapshot_dict[(self_id,snapshot_counter)] = SnapshotState((self_id,snapshot_counter))
    snapshot_counter += 1
    data = ["ss",str(self_id),str(self_id),str(0)]
    for i in constants.CONNECTION_GRAPH[self_id]:
        soc_send[i].sendall(' '.join(data).encode())
        print("Sent snapshot {} marker to {}".format(data, i))

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

# Called after receiving the first marker during a snapshot.
def snapshot_initiate(data):
    global snapshot_dict
    sender_id, initiator_id, snapshot_id = data[1:4]
    snapshot_tag = (int(initiator_id), int(snapshot_id))
    if snapshot_tag in snapshot_dict: 
        enter_error('snapshot_initiate called for already initiated snapshot.')
    snapshot_dict[snapshot_tag] = SnapshotState(snapshot_tag)
    snapshot_dict[snapshot_tag].record_channels[str(sender_id)] = False
    time.sleep(constants.MESSAGE_DELAY)
    data[1] = str(self_id)
    for i in constants.CONNECTION_GRAPH[self_id]:
        soc_send[i].sendall(' '.join(data).encode())
        print("Sent snapshot {} marker to {}".format(data,i))

# Called after receiving any subsequent marker during a snapshot.
def snapshot_continue(data):
    global snapshot_dict
    sender_id, initiator_id, snapshot_id = data[1:4]
    snapshot_tag = (int(initiator_id), int(snapshot_id))
    if snapshot_tag not in snapshot_dict: 
        enter_error('snapshot_continue called for uninitiated snapshot.')
    snapshot_dict[snapshot_tag].record_channels[str(sender_id)] = False
    #TODO: Check if snapshot complete
    

def token(token_string):
    print("initiated token {}".format(token_string))
    token_list = ["Token", token_string, str(self_id)]
    handle_token(token_list)

#connect to all clients
def initiate():
    for i in range(constants.NUM_CLIENT):
        if i != self_id:
            soc_send[i].connect((constants.HOST, constants.CLIENT_PORT_PREFIX+i))
            soc_send[i].sendall("Connection request from {}".format(self_id).encode())
            received = soc_send[i].recv(1024)
            print(received)

#pass token
def handle_token(data):
    global has_token
    global token_string
    has_token = True
    token_string = data[1]
    for key in snapshot_dict:
        if snapshot_dict[key].record_channels[data[2]]:
            snapshot_dict[key].incoming_channels[data[2]].append(data)
    time.sleep(constants.MESSAGE_DELAY)
    fail = random.choices([True,False],weights = (prob,1-prob), k=1)
    if fail[0]:
        print(' '.join(data) + " lost")
    else:
        next = random.choice(constants.CONNECTION_GRAPH[self_id])
        print("Sending token to {}".format(next))
        data[2] = str(self_id)
        soc_send[next].sendall(' '.join(data).encode())
    has_token = False

def print_all():
    for key in snapshot_dict:
        snapshot_dict[key].print_ss()

while run:
    inputready, outputready, exceptready = select.select(inputSockets, [], [])

    for x in inputready:
        if x == soc.fileno():
            client, address = soc.accept()
            inputSockets.append(client)
        elif x == sys.stdin.fileno():
            request = sys.stdin.readline().split()
            if request[0] == "exit":
                run = 0
            if request[0] == "i":
                initiate()
            if request[0] == "ss":
                thread = threading.Thread(target=snapshot, daemon=True)
                thread.start()
            if request[0] == "token":
                thread = threading.Thread(target=token, args=(request[1],), daemon=True)
                thread.start()
            if request[0] == "prob":
                prob = float(request[1])
                print("Updated failure probability to {}".format(prob))
            if request[0] == "print":
                thread = threading.Thread(target=print_all, daemon=True)
                thread.start()
        else:
            # "ss {#client_num} {#initial_client_num} {#snapshot_id}"
            # "t {token_string}"
            data = x.recv(1024).decode().split()
            # record message all current channels: append to dictionary
            if data[0] == "ss":
                snapshot_tag = (int(data[2]),int(data[3]))
                if snapshot_tag in snapshot_dict:
                    thread = threading.Thread(target=snapshot_continue, args=(data,), daemon=True)
                    thread.start()
                else:
                    thread = threading.Thread(target=snapshot_initiate, args=(data,), daemon=True)
                    thread.start()
            elif data[0] == "Connection":
                print(' '.join(data))
                x.send("Successfully connected to {}".format(self_id).encode())
            elif data[0] == "Token":
                print("Recieved "+' '.join(data))
                thread = threading.Thread(target=handle_token, args=(data,), daemon=True)
                thread.start()
            else:
                break



# UI methods
def enter_log(string):
    print(string)
    
def enter_error(string):
    print(f'ERROR: {string}')
