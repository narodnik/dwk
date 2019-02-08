import darkwiki
import hashlib
import json
import os
import time
from enum import Enum

def move_up(path):
    return os.path.abspath(os.path.join(path, '..'))

def find_root_path():
    path = os.getcwd()
    while True:
        files = os.listdir(path)
        if '.darkwiki' in files:
            return path
        path = move_up(path)

def touch_file(filename):
    open(filename, 'wb').write(b'')

def remove_if(vector, predicate):
    return [x for x in vector if not predicate(x)]

class DataType(Enum):
    BLOB   = 1
    TREE   = 2
    COMMIT = 3

class DiskDatabase:

    def __init__(self):
        self._root_path = find_root_path()

    @property
    def _dot_path(self):
        return os.path.join(self._root_path, '.darkwiki')
    @property
    def _objects_path(self):
        return os.path.join(self._dot_path, 'objects')
    @property
    def _HEAD_path(self):
        return os.path.join(self._dot_path, 'HEAD')
    @property
    def _index_filename(self):
        return os.path.join(self._dot_path, 'index')

    def _ref_path(self, ref):
        return os.path.join(self._dot_path, ref)

    def _open_object(self, ident, flag):
        return open(os.path.join(self._objects_path, ident), flag + 'b')

    def open_file(self, filename, flag):
        return open(os.path.join(self._root_path, filename), flag + 'b')

    def transform_relative_path(self, filename):
        filename = os.path.abspath(filename)
        return os.path.relpath(filename, self._root_path)

    def initialize(self):
        os.mkdir(self._objects_path)
        self._write_HEAD('refs/heads/master')
        os.makedirs(self._ref_path('refs/heads/'))
        touch_file(self._index_filename)

    def _add_data(self, data, data_type):
        ident = hashlib.sha256(data).hexdigest()
        with self._open_object(ident, 'w') as file_handle:
            header = '%s:' % data_type.name
            file_handle.write(header.encode())
            file_handle.write(data)
        return ident

    def add_blob(self, data):
        return self._add_data(data, DataType.BLOB)

    def hash_file(self, filename):
        data = self.open_file(filename, 'r').read()
        ident = hashlib.sha256(data).hexdigest()
        return ident

    def add_file(self, filename):
        data = self.open_file(filename, 'r').read()
        ident = self.add_blob(data)

        self.update_index('644', ident, filename)

    def list(self):
        return os.listdir(self._objects_path)

    def fuzzy_match(self, ident_prefix):
        match = [ident for ident in self.list()
                 if ident.startswith(ident_prefix)]
        if not match:
            return None
        return match[0]

    def fetch(self, ident):
        data = self._open_object(ident, 'r').read()
        header = data.split(b':')[0]
        data_type = DataType[header.decode()]
        data = data[len(header) + 1:]
        if data_type == DataType.TREE:
            data = self._deserialize_tree(data)
        elif data_type == DataType.COMMIT:
            data = self._deserialize_commit(data)
        return data_type, data

    def _deserialize_tree(self, data):
        # Remove trailing newline
        data = data[:-1]
        data = data.decode().split('\n')
        data = [row.split(' ') for row in data]

        result = []
        for row in data:
            mode, object_type, ident, filename = row
            object_type = DataType[object_type]
            result.append((mode, object_type, ident, filename))
        return result

    def _deserialize_commit(self, data):
        return json.loads(data.decode())

    def object_type(self, ident):
        return self.fetch(ident)[0]

    def update_index(self, mode, ident, filename):
        index = self.read_index()
        index = remove_if(index, lambda row: row[2] == filename)
        index.append((mode, ident, filename))

        self._write_to_index(index)

    def remove_from_index(self, filename):
        index = self.read_index()
        index = remove_if(index, lambda row: row[2] == filename)

        self._write_to_index(index)

    def _write_to_index(self, index):
        with open(self._index_filename, 'w') as file_handle:
            for mode, ident, filename in index:
                file_handle.write('%s %s %s\n' % (mode, ident, filename))

    def clear_index(self):
        open(self._index_filename, 'w').truncate(0)

    def read_index(self):
        index = []
        for line in open(self._index_filename, 'r'):
            index.append(self._read_index_line(line))
        return index

    def _read_index_line(self, line):
        # Strip end newline
        assert line[-1] == '\n'
        line = line[:-1]
        mode, ident, filename = line.split(' ')
        return mode, ident, filename

    def _create_subtrees(self, index):
        root = darkwiki.build_tree(index)

        for directory in darkwiki.walk_tree(root):
            assert not [subdir for subdir in directory.subdirs
                        if subdir.ident is None]

            data = self._create_tree(directory)
            ident = self._add_data(data, DataType.TREE)
            # Set the ident
            directory.ident = ident

        return root.ident

    def _create_tree(self, directory):
        description = ''

        for mode, ident, filename in directory.files:
            description += '%s BLOB %s %s\n' % (mode, ident, filename)
        for subdir in directory.subdirs:
            description += '755 TREE %s %s\n' % (subdir.ident, subdir.name)

        #print('==============')
        #print(directory.full_path)
        #print(description)
        #print('==============')
        # Write this index

        data = description.encode()
        return data

    def write_tree(self):
        # Read index and clear
        index = self.read_index()
        # Create subtrees
        root_tree_ident = self._create_subtrees(index)
        return root_tree_ident

    def _write_HEAD(self, ref):
        with open(self._HEAD_path, 'w') as file_handle:
            file_handle.write('ref: %s' % ref)

    def _get_ref_commit_ident(self, reference):
        path = self._ref_path(reference)
        try:
            return open(path).read()
        except FileNotFoundError:
            return None

    def _get_current_ref(self):
        HEAD_data = open(self._HEAD_path).read()
        assert HEAD_data.startswith('ref: ')
        return HEAD_data[len('ref: '):]

    def last_commit_ident(self):
        reference = self._get_current_ref()
        # lookup from ref in HEAD
        return self._get_ref_commit_ident(reference)

    def commit(self):
        # write_tree()
        root_tree_ident = self.write_tree()
        # Make commit object
        utc_offset = time.localtime().tm_gmtoff
        unix_time = int(time.time())
        commit = {
            # ... with pointer to tree
            'tree': root_tree_ident,
            # ... and timestamp
            'timestamp': unix_time,
            'utc_offset': utc_offset,
            # Previous commit
            'previous_commit': self.last_commit_ident()
            # later we will add hash of pubkey for ID
        }
        data = json.dumps(commit).encode()
        commit_ident = self._add_data(data, DataType.COMMIT)
        print('commit:', commit_ident)

        self._write_to_ref(commit_ident)

    def _write_to_ref(self, commit_ident):
        # lookup current ref in HEAD
        reference = self._get_current_ref()
        # update refs/<...>
        path = self._ref_path(reference)
        open(path, 'w').write(commit_ident)

