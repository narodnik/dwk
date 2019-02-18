import darkwiki
import threading
import zmq

class SeedNode(threading.Thread):

    def __init__(self):
        threading.Thread.__init__ (self)

        self._addrs = {}

    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind('tcp://*:5577')

        while True:
            self.receive(socket)
            self.reply(socket)

    def receive(self, socket):
        message = socket.recv()

        deserial = darkwiki.Deserializer(message)
        try:
            address = deserial.read_string()
            public_key = deserial.read_data()
        except darkwiki.DeserialError:
            print('Bad message')
            return

        print('Received:', address, public_key.hex())
        self._addrs[address] = public_key

    def reply(self, socket):
        serial = darkwiki.Serializer()
        serial.write_2_bytes(len(self._addrs))
        for address, public_key in self._addrs.items():
            serial.write_string(address)
            serial.write_data(public_key)
        data = serial.result()

        socket.send(data)

def main():
    seed_node = SeedNode()
    seed_node.start()
    seed_node.join()

if __name__ == "__main__":
    main()

