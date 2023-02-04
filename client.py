import socket
import select
import sys
import threading
import time

import constants

index = int(sys.argv[1]) # Client ID in range(5)
port = constants.CLIENT_PORT_PREFIX + index
soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
soc.setblocking(False)
soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
soc_send = []
for i in range(constants.NUM_CLIENT):
    temp_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc_send.append(temp_soc)

soc.listen(constants.NUM_CLIENT)
inputSockets = [soc.fileno(), sys.stdin.fileno()]
address_list = []
send_list = []
run = 1
snapshot_dict = {}
current_requests_channel  = {}


def handle_input(x, data):
    global lamport
    if data:
        if data[0] == "t":
            if(int(data[4])>lamport):
                lamport = int(data[4])
            lamport = lamport+1
            message = "reply "+str(lamport)
            x.send(message.encode())
            lamport = lamport+1
        else:
            if(int(data[5])>lamport):
                lamport = int(data[5])
            lamport = lamport+1
            chain.release([data[4],data[2],data[3]])
            x.send("reply 0".encode())
    else:
        x.close()
        inputSockets.remove(x)

def snapshot():

# Called after receiving the first marker during a snapshot.
def snapshot_initiate(x, data):
    time.sleep(constants.MESSAGE_DELAY)

# Called after receiving any subsequent marker during a snapshot.
def snapshot_continue(x, data):
    time.sleep(constants.MESSAGE_DELAY)

def token(token_string):

def initiate():

while run:
    inputready, outputready, exceptready = select.select(inputSockets, [], [])

    for x in inputready:
        if x == soc.fileno():
            client, address = soc.accept()
            address_list.append(address)
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
                thread = threading.Thread(target=token, arg=(request[1],), daemon=True)
                thread.start()
        else:
            # "ss {#client_num} {#initial_client_num} {#snapshot_id}"
            # "t {token_string}"
            data = x.recv(1024).decode().split()
            # record message all current channels: append to dictionary
            if data[0] == "ss":
                if snapshot_dict.has_key((data[2],data[3])):
                    thread = threading.Thread(target=snapshot_continue, args=(x, data,), daemon=True)
                    thread.start()
                else:
                    thread = threading.Thread(target=snapshot_initiate, args=(x, data,), daemon=True)
                    thread.start()
            else:


soc.close()
