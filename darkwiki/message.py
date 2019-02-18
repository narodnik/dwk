import darkwiki
import hashlib
import random
from enum import Enum

class MessageType(Enum):

    REQUEST = 1
    REPLY = 2

class MessageHeader:
    # magic_bytes:4 = 1337
    # protocol_version:2
    # checksum:4
    # encrypted_message

    def __init__(self, ciphertext):
        self.ciphertext = ciphertext

    @property
    def magic(self):
        return 1337

    @property
    def protocol_version(self):
        return 1

    @property
    def checksum(self):
        hash_data = hashlib.sha256(self.ciphertext).digest()[:4]
        return struct.unpack('<I', hash_data)[0]

    def to_data(self):
        serial = Serializer()
        serial.write_2_bytes(self.magic)
        serial.write_2_bytes(self.protocol_version)
        serial.write_4_bytes(self.checksum)
        serial.write_data(self.ciphertext)
        return serial.result()

    @classmethod
    def from_data(cls, data):
        deserial = Deserializer(data)
        try:
            magic = deserial.read_2_bytes()
            version = deserial.read_2_bytes()
            checksum = deserial.read_4_bytes()
        except DeserialException:
            return None

        self = cls(deserial.remaining_data())

        if (self.magic != magic or self.protocol_version != version or
            self.checksum != checksum):
            return None

        return self

    def decrypt(self, sender_public, receiver_secret):
        message_data = darkwiki.decrypt_verify(self.ciphertext, sender_public,
                                               receiver_secret)
        if len(message_data) < 1:
            return None
        # message_type:1
        message_type = MessageType(message_data[0])
        message_data = message_data[1:]
        if message_type == MessageType.REQUEST:
            return RequestMessage.from_data(message_data)
        elif message_type == MessageType.REPLY:
            return ReplyMessage.from_data(message_data)

class GetPeersRequest:

    def __init__(self):
        pass

    def command(self):
        return 'get_peers'

    @classmethod
    def from_data(cls, data):
        return cls()

    def to_data(self):
        return b''

class RequestMessage:

    # command:12
    # request_id:4
    # payload

    request_types = {
        'get_peers': GetPeersRequest
    }

    def __init__(self, command, request_id, payload):
        self.command = command
        self.request_id = request_id
        self.payload = payload

    @classmethod
    def from_data(cls, message_data):
        if len(message_data) < 16:
            return None
        deserial = Deserializer(message_data)
        command = deserial.read_fixed_string(12)
        request_id = deserial.read_4_bytes()
        payload = deserial.remaining_data()
        return cls(command, request_id, payload)

    @classmethod
    def make(cls, command, *args):
        request_type = cls.request_types[command]
        request_object = request_type(*args)
        payload = request_object.to_data()
        request_id = random.randint(0, 2**32 - 1)
        self = cls(command, request_id, payload)
        return self

    def to_data(self):
        message_type = MessageType.REQUEST.value

        serial = Serializer()
        serial.write_byte(message_type)
        serial.write_fixed_string(self.command, 12)
        serial.write_4_bytes(self.request_id)
        serial.write_data(self.payload)

        return serial.result()

    def encrypt(self, sender_secret, receiver_public):
        message_data = self.to_data()
        return darkwiki.encrypt_sign(message_data, sender_secret,
                                     receiver_public)

    def get_request(self):
        assert self.command in RequestMessage.request_types
        return RequestMessage.request_types[self.command].from_data(
            self.payload)

class ReplyMessage:

    # reply_id:4
    # payload

    def __init__(self, reply_id, payload):
        self.reply_id = response_id
        self.payload = payload

    @classmethod
    def from_data(cls, message_data):
        if len(message_data) < 4:
            return None
        deserial = Deserializer(message_data)
        reply_id = deserial.read_4_bytes()
        payload = deserial.remaining_data()
        return cls(reply_id, payload)

    def to_data(self):
        message_type = MessageType.REPLY.value

        serial = Serializer()
        serial.write_byte(message_type)
        serial.write_4_bytes(self.reply_id)
        serial.write_data(self.payload)
        return serial.result()

    def encrypt(self, sender_secret, receiver_public):
        message_data = self.to_data()
        return darkwiki.encrypt_sign(message_data, sender_secret,
                                     receiver_public)

class MessageGetPeersReply:

    def __init__(self, addrs):
        self.addrs = addrs

    @classmethod
    def from_data(cls, data):
        addrs = []
        deserial = Deserializer(data)
        addrs_size = deserial.read_2_bytes()
        try:
            for i in range(addrs_size):
                addrs.append((deserial.read_string(), deserial.read_2_bytes()))
        except DeserialException:
            return None
        return cls(addrs)

    def to_data(self):
        serial = Serializer()
        serial.write_2_bytes(len(self.addrs))
        for ip, port in self.addrs:
            serial.write_string(ip)
            serial.write_2_bytes(port)
        return serial.result()

# MultipartRequestMessage / MultipartReplyMessage
#   expected_replies / reply_sequence

class Network:

    def __init__(self, listen_port=91782):
        self._listen_port = listen_port

if __name__ == '__main__':
    sender_secret = darkwiki.random_secret()
    sender_public = darkwiki.secret_to_public(sender_secret)

    receiver_secret = darkwiki.random_secret()
    receiver_public = darkwiki.secret_to_public(receiver_secret)

    #getpeers_request = MessageGetPeersRequest()
    #getpeers_request = MessageGetPeersReply([('127.0.0.1', 12)])
    #payload = getpeers_request.to_data()
    #request_message = RequestMessage('hello', 31337, payload)
    request_message = RequestMessage.make(MessageGetPeersRequest)
    ciphertext = request_message.encrypt(sender_secret, receiver_public)
    message_header = MessageHeader(ciphertext)
    data = message_header.to_data()

    # encrypt_sign: sender_secret, receiver_public

    message_header_2 = MessageHeader.from_data(data)
    assert message_header_2 is not None
    assert message_header_2.ciphertext == message_header.ciphertext

    request_message_2 = message_header_2.decrypt(sender_public, receiver_secret)

    getpeers_2 = MessageGetPeersRequest.from_data(request_message_2.payload)
    #print(getpeers_2.addrs)

    # decrypt_verify: sender_public, receiver_secret

    #secret = darkwiki.random_secret()
    #public = darkwiki.secret_to_public(secret)
    #print(public.hex())

    #message = b'helssdkjsd skslo mdhjdhjsdksddskddsjdkjjk' * 10
    #cipher = darkwiki.encrypt_sign(message, secret, public)
    #message_2 = darkwiki.decrypt_verify(cipher, public, secret)
    #print(message_2)
    #print(len(message), len(cipher))
    #assert message == message_2

