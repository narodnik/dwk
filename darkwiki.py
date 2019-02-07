#!/usr/bin/python
import argparse
import darkwiki
import hashlib
import os
import sys
from collections import defaultdict
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
    def _refs_path(self):
        return os.path.join(self._dot_path, 'refs')
    @property
    def _index_filename(self):
        return os.path.join(self._dot_path, 'index')

    def _open(self, ident, flag):
        return open(os.path.join(self._objects_path, ident), flag + 'b')

    def initialize(self):
        os.mkdir(self._objects_path)
        os.mkdir(self._refs_path)

    def _add_data(self, data, data_type):
        ident = hashlib.sha256(data).hexdigest()
        with self._open(ident, 'w') as file_handle:
            header = '%s:' % data_type.name
            file_handle.write(header.encode())
            file_handle.write(data)
        return ident

    def add_blob(self, data):
        return self._add_data(data, DataType.BLOB)

    def list(self):
        return os.listdir(self._objects_path)

    def fuzzy_match(self, ident_prefix):
        match = [ident for ident in self.list()
                 if ident.startswith(ident_prefix)]
        if not match:
            return None
        return match[0]

    def fetch(self, ident):
        data = self._open(ident, 'r').read()
        header = data.split(b':')[0]
        data_type = DataType[header.decode()]
        data = data[len(header) + 1:]
        if data_type == DataType.TREE:
            data = self._deserialize_tree(data)
        return data_type, data

    def _deserialize_tree(self, data):
        # Remove trailing newline
        data = data[:-1]
        data = data.decode().split('\n')
        data = [row.split(' ') for row in data]
        return data

    def object_type(self, ident):
        return self.fetch(ident)[0]

    def update_index(self, mode, ident, filename):
        with open(self._index_filename, 'a') as file_handle:
            file_handle.write('%s %s %s\n' % (mode, ident, filename))

    def clear_index(self):
        open(self._index_filename, 'w').truncate(0)

    def read_index(self):
        with open(self._index_filename, 'r') as file_handle:
            index = []
            for line in file_handle:
                # Strip end newline
                assert line[-1] == '\n'
                line = line[:-1]
                mode, ident, filename = line.split(' ')
                object_type = self.object_type(ident)
                index.append((mode, object_type, ident, filename))
        return index

    def _create_subtrees(self, index):
        index = [(ident, filename) for _, object_type, ident, filename
                 in index if object_type == DataType.BLOB]

        root = darkwiki.build_tree(index)

        for directory in darkwiki.walk_tree(root):
            assert not [subdir for subdir in directory.subdirs
                        if subdir.ident is None]

            for ident, filename in directory.files:
                print('adding:', ident, filename)
            for subdir in directory.subdirs:
                print('adding subdirs:', subdir.full_path)
            # write this index
            # set the ident

        return root.ident

    def write_tree(self):
        # Read index and clear
        index = self.read_index()
        ##self.clear_index()
        # Create subtrees
        root_tree_ident = self._create_subtrees(index)
        return root_tree_ident
        #ident = self._add_data(data, DataType.TREE)
        #return ident

    def add_file(self, filename):
        data = open(filename, 'rb').read()
        ident = self.add_blob(data)
        # filename relative to root
        filename = os.path.relpath(filename, self._root_path)
        self.update_index('644', ident, filename)

    def commit(self):
        # write_tree()
        root_tree_ident = self.write_tree()
        # make commit object
        # ... with pointer to tree
        # ... and timestamp
        # lookup current ref in HEAD
        # update refs/<...>

def main():
    parser = argparse.ArgumentParser(prog='darkwiki')
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers()

    # init
    parser_init = subparsers.add_parser('init')
    parser_init.set_defaults(func=initialize)

    # add-object
    parser_add_object = subparsers.add_parser('add-object')
    parser_add_object.add_argument('filename')
    parser_add_object.set_defaults(func=add_object)

    # add
    parser_add_object = subparsers.add_parser('add')
    parser_add_object.add_argument('filename')
    parser_add_object.set_defaults(func=simple_add)

    # list
    parser_list = subparsers.add_parser('list')
    parser_list.set_defaults(func=list_objects)

    # update-index
    parser_list = subparsers.add_parser('update-index')
    parser_list.add_argument('--clear', action='store_true')
    parser_list.add_argument('--cacheinfo', nargs=3)
    parser_list.set_defaults(func=update_index)

    # read-index
    parser_read_index = subparsers.add_parser('read-index')
    parser_read_index.set_defaults(func=read_index)

    # write-tree
    parser_write_tree = subparsers.add_parser('write-tree')
    parser_write_tree.set_defaults(func=write_tree)

    # show
    parser_show = subparsers.add_parser('show')
    parser_show.add_argument('ident')
    parser_show.set_defaults(func=show_file)

    # type
    parser_show = subparsers.add_parser('type')
    parser_show.add_argument('ident')
    parser_show.set_defaults(func=show_type)

    # commit
    parser_commit = subparsers.add_parser('commit')
    parser_commit.set_defaults(func=commit)

    args = parser.parse_args()

    if args.func is None:
        parser.print_usage()
        return -1

    return args.func(args)

def initialize(parser):
    os.mkdir('.darkwiki')
    db = DiskDatabase()
    db.initialize()

def add_object(parser):
    data = open(parser.filename, 'rb').read()

    db = DiskDatabase()
    ident = db.add_blob(data)
    print(ident)

    return 0

def simple_add(parser):
    db = DiskDatabase()
    db.add_file(parser.filename)
    return 0

def list_objects(parser):
    db = DiskDatabase()

    for ident in db.list():
        print(ident)

    return 0

def update_index(parser):
    db = DiskDatabase()

    if parser.clear:
        db.clear_index()
        return 0

    mode, ident, filename = parser.cacheinfo
    ident = db.fuzzy_match(ident)
    db.update_index(mode, ident, filename)

    return 0

def read_index(parser):
    db = DiskDatabase()
    current_index = db.read_index()
    for mode, object_type, ident, filename in current_index:
        print(mode, object_type.name, ident, filename)
    return 0

def write_tree(parser):
    db = DiskDatabase()
    ident = db.write_tree()
    print(ident)
    return 0

def show_file(parser):
    db = DiskDatabase()

    ident = db.fuzzy_match(parser.ident)
    if not ident:
        print('darkwiki: ident not found', file=sys.stderr)
        return -1

    data_type, data = db.fetch(ident)
    if data_type == DataType.BLOB:
        print(data.decode('utf-8'))
    elif data_type == DataType.TREE:
        for mode, ident, filename in data:
            object_type = db.object_type(ident)
            print(mode, object_type.name, ident, filename)

    return 0

def show_type(parser):
    db = DiskDatabase()

    ident = db.fuzzy_match(parser.ident)
    if not ident:
        print('darkwiki: ident not found', file=sys.stderr)
        return -1

    object_type = db.object_type(ident)
    print(object_type.name)

    return 0

def commit(parser):
    db = DiskDatabase()
    db.commit()

if __name__ == '__main__':
    sys.exit(main())

