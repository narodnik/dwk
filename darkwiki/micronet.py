import aiozmq
import asyncio
import collections
import darkwiki
import hashlib
import logging
import os
import pickle
import struct
import sys
import traceback
import zmq

def public_to_node_id(public_key):
    hash_data = hashlib.sha256(public_key).digest()[:4]
    return struct.unpack('<I', hash_data)[0]

class Keyring:

    def __init__(self, db):
        self.db = db

    @property
    def keyring_filename(self):
        return os.path.join(self.db.dot_path, 'keyring')

    def add_public_key(self, public_key):
        # Add to keyring file
        keys = self.authorized_keys()
        keys.add(public_key)
        with open(self.keyring_filename, 'w') as keyring_file:
            [keyring_file.write(key.hex() + '\n') for key in keys]

    def authorized_keys(self):
        # Read file and return all keys
        try:
            with open(self.keyring_filename, 'r') as keyring_file:
                return self._read_file(keyring_file)
        except FileNotFoundError:
            return set()

    def _read_file(self, keyring_file):
        return set(bytes.fromhex(line) for line in keyring_file)

class Node:

    def __init__(self, db, interface, id, port, secret):
        self.db = db
        self.interface = interface

        self.id = id
        self.secret = secret
        self.port = port
        self._connect_list = None

    @property
    def seeds_filename(self):
        return os.path.join(self.db.dot_path, 'seeds')

    def schedule(self, coroutine):
        async def report_error(coroutine):
            try:
                return await coroutine
            except:
                logging.error(traceback.format_exc())

        return asyncio.create_task(report_error(coroutine))

    async def sync_seeds(self):
        seed_node_list = await self._fetch_from_seed_node()

        seeds_file_list = self._fetch_from_seeds_file()

        # Merge both lists
        self._connect_list = {**seed_node_list, **seeds_file_list}

        self._update_seeds_file()

    async def _fetch_from_seed_node(self):
        stream = await aiozmq.create_zmq_stream(
            zmq_type=zmq.REQ,
            connect='tcp://127.0.0.1:5577')

        our_address = '127.0.0.1:%d' % self.port
        public_key = darkwiki.secret_to_public(self.secret)

        serial = darkwiki.Serializer()
        serial.write_string(our_address)
        serial.write_data(public_key)
        data = serial.result()

        stream.write([data])

        connect_list = {}

        data = await stream.read()
        if len(data) != 1:
            return
        deserial = darkwiki.Deserializer(data[0])
        try:
            size = deserial.read_2_bytes()
            for _ in range(size):
                address = deserial.read_string()
                public_key = deserial.read_data()

                connect_list[address] = public_key
        except darkwiki.DeserialError:
            print('error updating seeds: bad stream', file=sys.stderr)
            return

        # Skip ourselves
        del connect_list[our_address]

        return connect_list

    def _fetch_from_seeds_file(self):
        try:
            with open(self.seeds_filename, 'rb') as seeds:
                connects = pickle.load(seeds)
        except FileNotFoundError:
            connects = {}

        return connects

    def _update_seeds_file(self):
        with open(self.seeds_filename, 'wb') as seeds:
            pickle.dump(self._connect_list, seeds)

    async def start(self):
        await self.sync_seeds()

        self._publish = await aiozmq.create_zmq_stream(
            zmq_type=zmq.PUB,
            bind='tcp://*:%d' % self.port)

        tasks = []
        for address, public_key in self._connect_list.items():
            channel = Channel(self, address, public_key)
            task = self.schedule(channel.start())
            tasks.append(task)

        await asyncio.gather(*tasks)

    def send(self, message):
        self._publish.write(message)

class Channel:

    def __init__(self, parent, address, public_key):
        self._parent = parent
        self._address = address
        self.public_key = public_key

        self.identity = '%d:%s' % (parent.id, public_key.hex())

    async def _initialize(self):
        self._stream = await aiozmq.create_zmq_stream(
            zmq_type=zmq.SUB,
            connect='tcp://%s' % self._address)
        self._stream.transport.subscribe(b'')

    async def start(self):
        await self._initialize()

        await asyncio.sleep(0.4)

        protocol = Protocol(self)
        await protocol.start()

    async def receive(self):
        while True:
            ciphertext = await self._stream.read()
            if len(ciphertext) != 1:
                continue
            ciphertext = ciphertext[0]

            message = darkwiki.decrypt_verify(
                ciphertext, self.public_key, self._parent.secret)

            if message is not None:
                return message

    def send(self, message):
        ciphertext = darkwiki.encrypt_sign(
            message, self._parent.secret, self.public_key)

        self._parent.send([ciphertext])

class Pool:

    def __init__(self, db, interface):
        self.pool = collections.deque(maxlen=1000)
        self._db = db
        self._interface = interface
        self._object_map = {}

    def exists(self, ident):
        return ident in self._object_map

    def add(self, ident, object_type, object_):
        self.pool.append((ident, (object_type, object_)))
        self._object_map = dict(self.pool)

    def resolve(self):
        chain = self._resolve_commit_chain()

        missing_objects = []
        for commit in chain:
            missing_objects += self._verify_tree(commit['tree'])

        return missing_objects

    def _verify_tree(self, tree_ident):
        tree = self._fetch_tree(tree_ident)
        if tree is None:
            return [tree_ident]

        missing_objects = []
        for mode, type_, ident, filename in tree:
            if type_ == darkwiki.DataType.TREE:
                missing_objects += self._verify_tree(ident)
            elif type_ == darkwiki.DataType.BLOB:
                if not self._blob_exists(ident):
                    missing_objects.append(ident)

        return missing_objects

    def _blob_exists(self, ident):
        if (ident in self._object_map and
            self._object_map[ident][0] == darkwiki.DataType.BLOB):
            return True

        return self._db.exists(ident)

    def _fetch_tree(self, ident):
        return self._fetch(ident, darkwiki.DataType.TREE)

    def _fetch(self, ident, object_type):
        if ident in self._object_map:
            type_, object_ = self._object_map[ident]
        elif self._db.exists(ident):
            type_, object_ = self._db.fetch(ident)
        else:
            return None

        if type_ != object_type:
            return None

        assert object_ is not None
        return object_

    def _resolve_commit_chain(self):
        commits_map = self._filter_commits()

        valid_chain = None
        longest_chain = 0
        # Construct valid chain from origin that we share
        for ident, commit in commits_map.items():
            commit['ident'] = ident
            chain = self._follow(commit, commits_map)
            if chain is None:
                continue
            if len(chain) > longest_chain:
                valid_chain = chain

        # TODO: Currently we have no system to resolve missing
        #       commits in the chain back to the shared origin.
        #       This isn't currently a problem since the protocol
        #       sends all commits in a batch, but we shouldn't
        #       rely on this behaviour.

        return valid_chain

    def _follow(self, commit, commits_map):
        if commit['previous_commit'] is None:
            return [commit]

        previous_commit_ident = commit['previous_commit']
        previous_commit = self._get_commit(previous_commit_ident, commits_map)
        if previous_commit is None:
            return None
        previous_commit['ident'] = previous_commit_ident

        chain = self._follow(previous_commit, commits_map)
        if chain is None:
            return None

        return [commit] + chain

    def _get_commit(self, commit_ident, commits_map):
        type_, commit = self._db.fetch(commit_ident)
        if type_ != darkwiki.DataType.COMMIT:
            return None

        if commit is not None:
            return commit

        # Not found in database, lookup in our pool
        if commit_ident not in commits_map:
            return None

        return commits_map[commit_ident]

    def _filter_commits(self):
        return dict((ident, object_) for ident, (object_type, object_)
                    in self.pool if object_type == darkwiki.DataType.COMMIT)

    def rebase(self):
        # Build against branch
        # branch_name = remote/<pubkey>
        pass

class Protocol:

    def __init__(self, channel):
        self._channel = channel

        self._pool = Pool(self.db, self.interface)

    @property
    def db(self):
        return self._channel._parent.db
    @property
    def interface(self):
        return self._channel._parent.interface

    @property
    def remote_public_key(self):
        return self._channel.public_key

    async def start(self):
        self.send('hello')

        print('connect', self._channel.identity)

        while True:
            message = await self.receive()
            print('got:', message.command, self._channel.identity)

            self._process(message)

    def _process(self, message):
        if message.command == 'hello':
            tips = self.interface.branches_tips()
            self.send('sync', tips)

        elif message.command == 'sync':
            remote_tips = message.tips

            # First write remote tips
            for branch, commit_ident in remote_tips.items():
                self.db.write_remote_ref(self.remote_public_key.hex(),
                                         branch, commit_ident)

            self._request_missing_objects()

        elif message.command == 'fetch':
            ident = message.object_ident
            object_type, object_ = self.db.fetch(ident)
            print('fetch:', ident)

            self.send('object', ident, object_type, object_)

        elif message.command == 'object':
            print('object:', message.ident)
            self.db.add_object(message.object, message.object_type)

            self._request_missing_objects()

    def _request_missing_objects(self):
        local_tips = self.interface.branches_tips()

        remote = self.remote_public_key.hex()
        for branch in self.db.fetch_remote_branches(remote):
            commit_ident = self.db.branch_remote_last_commit_ident(
                remote, branch)

            missing = self.interface.resolve_missing_objects(commit_ident)

            [self.send('fetch', ident) for ident in missing]

            if not missing and branch in local_tips:
                local_last = local_tips[branch]
                if local_last != commit_ident:
                    self._attempt_merge(branch)

    def _attempt_merge(self, branch):
        print('Attempting merge:', branch, self.remote_public_key.hex())

    def _commit_idents(self):
        commits = self.interface.fetch_commits()
        commit_idents = [commit['ident'] for commit in commits]
        return commit_idents

    async def receive(self):
        while True:
            message_data = await self._channel.receive()

            message = MessageFactory.deserialize(message_data)
            if message is not None:
                return message

    def send(self, command, *args):
        message_data = MessageFactory.serialize(command, *args)
        self._channel.send(message_data)

class HelloMessage:

    command = 'hello'

    @classmethod
    def from_data(cls, data):
        return cls()

    def to_data(self):
        return b''

class SyncMessage:

    command = 'sync'

    def __init__(self, tips):
        self.tips = tips

    @classmethod
    def from_data(cls, data):
        deserial = darkwiki.Deserializer(data)

        try:
            tips_size = deserial.read_4_bytes()

            tips = {}
            for _ in range(tips_size):
                branch = deserial.read_string()
                commit_ident = deserial.read_data().hex()

                tips[branch] = commit_ident

        except darkwiki.DeserialError:
            return None

        return cls(tips)

    def to_data(self):
        serial = darkwiki.Serializer()
        serial.write_4_bytes(len(self.tips))
        for branch, commit_ident in self.tips.items():
            serial.write_string(branch)
            commit_ident = bytes.fromhex(commit_ident)
            serial.write_data(commit_ident)
        return serial.result()

class FetchMessage:

    command = 'fetch'

    def __init__(self, object_ident):
        self.object_ident = object_ident

    @classmethod
    def from_data(cls, data):
        object_ident = data.hex()
        return cls(object_ident)

    def to_data(self):
        return bytes.fromhex(self.object_ident)

class ObjectMessage:

    command = 'object'

    def __init__(self, ident, object_type, object_):
        self.ident = ident
        self.object_type = object_type
        self.object = object_

    @classmethod
    def from_data(cls, data):
        deserial = darkwiki.Deserializer(data)
        try:
            ident = deserial.read_data().hex()
            object_type = darkwiki.DataType(deserial.read_byte())
            if object_type == darkwiki.DataType.BLOB:
                object_ = deserial.read_data()
            elif object_type == darkwiki.DataType.TREE:
                object_ = ObjectMessage._read_tree(deserial)
            elif object_type == darkwiki.DataType.COMMIT:
                object_ = ObjectMessage._read_commit(deserial)
        except darkwiki.DeserialError:
            return None
        return cls(ident, object_type, object_)

    @staticmethod
    def _read_tree(deserial):
        rows_size = deserial.read_4_bytes()
        tree = []
        for _ in range(rows_size):
            tree.append((
                deserial.read_string(),                     # mode
                darkwiki.DataType(deserial.read_byte()),    # type
                deserial.read_data().hex(),                 # ident
                deserial.read_string()                      # filename
            ))
        return tree

    @staticmethod
    def _read_commit(deserial):
        return {
            'tree': deserial.read_data().hex(),
            'timestamp': deserial.read_4_bytes(),
            'utc_offset': deserial.read_4_bytes(),
            'previous_commit': deserial.read_data().hex()
        }

    def to_data(self):
        serial = darkwiki.Serializer()
        serial.write_data(bytes.fromhex(self.ident))
        serial.write_byte(self.object_type.value)
        if self.object_type == darkwiki.DataType.BLOB:
            serial.write_data(self.object)
        elif self.object_type == darkwiki.DataType.TREE:
            serial.write_4_bytes(len(self.object))
            for mode, type_, ident, filename in self.object:
                serial.write_string(mode)
                serial.write_byte(type_.value)
                serial.write_data(bytes.fromhex(ident))
                serial.write_string(filename)
        elif self.object_type == darkwiki.DataType.COMMIT:
            tree = bytes.fromhex(self.object['tree'])
            serial.write_data(tree)
            serial.write_4_bytes(self.object['timestamp'])
            serial.write_4_bytes(self.object['utc_offset'])
            previous = bytes.fromhex(self.object['previous_commit'])
            serial.write_data(previous)
        return serial.result()

class MessageFactory:
    message_types = [
        HelloMessage,
        SyncMessage,
        FetchMessage,
        ObjectMessage
    ]
    typemap = dict((cls_type.command, cls_type) for cls_type in message_types)

    @staticmethod
    def deserialize(message_data):
        header = MessageHeader.from_data(message_data)
        if header is None:
            return None

        if header.command not in MessageFactory.typemap:
            return None

        cls_type = MessageFactory.typemap[header.command]

        message = cls_type.from_data(header.payload)
        return message

    @staticmethod
    def serialize(command, *args):
        assert command in MessageFactory.typemap
        cls_type = MessageFactory.typemap[command]

        message = cls_type(*args)

        header = MessageHeader(command, message.to_data())
        return header.to_data()

class MessageHeader:
    # magic_bytes:4 = 1337
    # protocol_version:2
    # command
    # payload
    # checksum:4

    def __init__(self, command, payload):
        self.command = command
        self.payload = payload

    @property
    def magic(self):
        return 1337

    @property
    def protocol_version(self):
        return 1

    @property
    def checksum(self):
        message_data = self._to_data_no_checksum()
        hash_data = hashlib.sha256(message_data).digest()[:4]
        return struct.unpack('<I', hash_data)[0]

    def _to_data_no_checksum(self):
        serial = darkwiki.Serializer()
        serial.write_2_bytes(self.magic)
        serial.write_2_bytes(self.protocol_version)
        serial.write_fixed_string(self.command, 12)
        serial.write_data(self.payload)
        return serial.result()

    def to_data(self):
        serial = darkwiki.Serializer()
        serial.append(self._to_data_no_checksum())
        serial.write_4_bytes(self.checksum)
        return serial.result()

    @classmethod
    def from_data(cls, data):
        deserial = darkwiki.Deserializer(data)
        try:
            magic = deserial.read_2_bytes()
            version = deserial.read_2_bytes()
            command = deserial.read_fixed_string(12)
            payload = deserial.read_data()
            checksum = deserial.read_4_bytes()
        except DeserialError:
            return None

        self = cls(command, payload)
        # check magic_bytes, protocol_version
        # make sure checksum is good too
        if (self.magic != magic or self.protocol_version != version or
            self.checksum != checksum):
            return None

        return self

