CLIENT_PORT_PREFIX = 6540
HOST = "localhost"
NUM_CLIENT = 5
CONNECTION_GRAPH = [[1], [0, 3], [1], [0, 1, 2, 4], [1, 3]]
INCOMING_GRAPH = [[1,3], [0, 2, 3, 4], [3], [1, 4], [3]]
MESSAGE_DELAY = 3   # seconds of delay when receiving a message
MESSAGE_SIZE = 2048 # message size in bytes
HEADER_SIZE = 4