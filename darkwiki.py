#!/usr/bin/python
import argparse
import darkwiki
import hashlib
import json
import os
import sys
import time
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

def touch_file(filename):
    open(filename, 'wb').write(b'')

def remove_if(vector, predicate):
    return [x for x in vector if not predicate(x)]

def filter_one(vector, predicate):
    match = [x for x in vector if predicate(x)]
    if not match:
        return None
    return match[0]

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

    def _open(self, ident, flag):
        return open(os.path.join(self._objects_path, ident), flag + 'b')

    def initialize(self):
        os.mkdir(self._objects_path)
        self._write_HEAD('refs/heads/master')
        os.makedirs(self._ref_path('refs/heads/'))
        touch_file(self._index_filename)

    def _add_data(self, data, data_type):
        ident = hashlib.sha256(data).hexdigest()
        with self._open(ident, 'w') as file_handle:
            header = '%s:' % data_type.name
            file_handle.write(header.encode())
            file_handle.write(data)
        return ident

    def add_blob(self, data):
        return self._add_data(data, DataType.BLOB)

    def add_file(self, filename):
        data = open(filename, 'rb').read()
        ident = self.add_blob(data)
        # filename relative to root
        filename = os.path.relpath(filename, self._root_path)

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
        data = self._open(ident, 'r').read()
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
        with open(self._index_filename, 'r') as file_handle:
            index = []
            for line in file_handle:
                # Strip end newline
                assert line[-1] == '\n'
                line = line[:-1]
                mode, ident, filename = line.split(' ')
                index.append((mode, ident, filename))
        return index

    def _create_subtrees(self, index):
        root = darkwiki.build_tree(index)

        for directory in darkwiki.walk_tree(root):
            assert not [subdir for subdir in directory.subdirs
                        if subdir.ident is None]
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
            ident = self._add_data(data, DataType.TREE)
            # Set the ident
            directory.ident = ident

        return root.ident

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

class Interface:

    def __init__(self, db):
        self._db = db

    def fetch_commits(self):
        results = []
        current_commit_ident = self._db.last_commit_ident()
        while current_commit_ident is not None:
            object_type, commit = self._db.fetch(current_commit_ident)
            commit['ident'] = current_commit_ident
            assert object_type == DataType.COMMIT
            results.append(commit)
            current_commit_ident = commit['previous_commit']
        return results

    def _read_tree(self, tree_ident, tree_name=None):
        object_type, tree_contents = self._db.fetch(tree_ident)
        assert object_type == DataType.TREE

        tree = darkwiki.DirectoryTree(tree_name)

        for mode, object_type, ident, filename in tree_contents:
            if object_type == DataType.BLOB:
                tree.add_file(mode, ident, filename)
            elif object_type == DataType.TREE:
                subtree = self._read_tree(ident, filename)
                tree.add_subdir(subtree)

        return tree

    def diff_cached(self, commit_ident):
        # diff current index state and files with commit ident
        if commit_ident is None:
            commit_ident = self._db.last_commit_ident()

            if commit_ident is None:
                return None

        assert commit_ident is not None

        # Read root tree of commit
        object_type, commit = self._db.fetch(commit_ident)
        assert object_type == DataType.COMMIT

        tree_root_ident = commit['tree']
        tree = self._read_tree(tree_root_ident)

        # Read index
        index = self._db.read_index()

        results = []
        # For each file in index
        for mode, ident, filename in index:
            # Lookup in tree
            filespec = lookup_file_in_tree(tree, filename)
            if filespec is None:
                diff = 'foo'
                continue

            # If ident doesn't match, perform diff
            if filespec[1] == ident:
                continue

            print(filename, 'doesnt match')
            diff = 'foo - foo'

            # Add to results
            results.append(diff)

        # Return results
        return results

def lookup_file_in_tree(tree_root, filename):
    file_path = os.path.dirname(filename)
    file_base = os.path.basename(filename)

    match_dir = filter_one(darkwiki.walk_tree(tree_root),
                           lambda directory: directory.full_path == file_path)
    if match_dir is None:
        return None

    match_file = filter_one(match_dir.files,
                            lambda file: file[2] == file_base)
    if match_file is None:
        return None

    return match_file

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
    parser_add = subparsers.add_parser('add')
    parser_add.add_argument('filename')
    parser_add.set_defaults(func=simple_add)

    # rm
    parser_rm = subparsers.add_parser('rm')
    parser_rm.add_argument('filename')
    parser_rm.set_defaults(func=simple_rm)

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

    # log
    parser_log = subparsers.add_parser('log')
    parser_log.set_defaults(func=log)

    # diff
    parser_diff = subparsers.add_parser('diff')
    parser_diff.add_argument('commit_ident', nargs='?', default=None)
    parser_diff.set_defaults(func=diff)

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

def simple_rm(parser):
    db = DiskDatabase()
    db.remove_from_index(parser.filename)
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
    for mode, ident, filename in current_index:
        print(mode, ident, filename)
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
        for mode, object_type, ident, filename in data:
            print(mode, object_type.name, ident, filename)
    elif data_type == DataType.COMMIT:
        print(json.dumps(data, indent=2))

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

def log(parser):
    db = DiskDatabase()
    interface = Interface(db)
    log = interface.fetch_commits()
    previous = None
    for commit in log:
        if previous is not None:
            assert commit['ident'] == previous
        print(commit['ident'])
        print(commit['timestamp'], '+%s' % commit['utc_offset'])
        previous = commit['previous_commit']
        print()
    #print(json.dumps(log, indent=2))

def diff(parser):
    db = DiskDatabase()
    interface = Interface(db)
    diff_result = interface.diff_cached(parser.commit_ident)
    for row in diff_result:
        print(row)

if __name__ == '__main__':
    sys.exit(main())

