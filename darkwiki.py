#!/usr/bin/python
import argparse
import darkwiki
import json
import os
import sys
from termcolor import colored

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
    parser_commit.add_argument('-a', '--all', action='store_true')
    parser_commit.set_defaults(func=commit)

    # log
    parser_log = subparsers.add_parser('log')
    parser_log.set_defaults(func=log)

    # diff
    parser_diff = subparsers.add_parser('diff')
    parser_diff.add_argument('--cached', action='store_true')
    parser_diff.add_argument('commit_ident', nargs='?', default=None)
    parser_diff.set_defaults(func=diff)

    # branch
    parser_branch = subparsers.add_parser('branch')
    parser_branch.add_argument('branch_name', nargs='?')
    parser_branch.add_argument('commit_ident', nargs='?')
    parser_branch.set_defaults(func=branch)

    args = parser.parse_args()

    if args.func is None:
        parser.print_usage()
        return -1

    return args.func(args)

def initialize(parser):
    os.mkdir('.darkwiki')
    db = darkwiki.DiskDatabase()
    db.initialize()
    return 0

def add_object(parser):
    data = open(parser.filename, 'rb').read()

    db = darkwiki.DiskDatabase()
    ident = db.add_blob(data)
    print(ident)

    return 0

def simple_add(parser):
    db = darkwiki.DiskDatabase()
    # filename relative to root
    filename = db.transform_relative_path(parser.filename)
    db.add_file(filename)
    return 0

def simple_rm(parser):
    db = darkwiki.DiskDatabase()
    # filename relative to root
    filename = db.transform_relative_path(parser.filename)
    db.remove_from_index(filename)
    return 0

def list_objects(parser):
    db = darkwiki.DiskDatabase()

    for ident in db.list():
        print(ident)

    return 0

def update_index(parser):
    db = darkwiki.DiskDatabase()

    if parser.clear:
        db.clear_index()
        return 0

    mode, ident, filename = parser.cacheinfo
    ident = db.fuzzy_match(ident)
    db.update_index(mode, ident, filename)

    return 0

def read_index(parser):
    db = darkwiki.DiskDatabase()
    current_index = db.read_index()
    for mode, ident, filename in current_index:
        print(mode, ident, filename)
    return 0

def write_tree(parser):
    db = darkwiki.DiskDatabase()
    ident = db.write_tree()
    print(ident)
    return 0

def show_file(parser):
    db = darkwiki.DiskDatabase()

    ident = db.fuzzy_match(parser.ident)
    if not ident:
        print('darkwiki: ident not found', file=sys.stderr)
        return -1

    data_type, data = db.fetch(ident)
    if data_type == darkwiki.DataType.BLOB:
        print(data.decode('utf-8'))
    elif data_type == darkwiki.DataType.TREE:
        for mode, object_type, ident, filename in data:
            print(mode, object_type.name, ident, filename)
    elif data_type == darkwiki.DataType.COMMIT:
        print(json.dumps(data, indent=2))

    return 0

def show_type(parser):
    db = darkwiki.DiskDatabase()

    ident = db.fuzzy_match(parser.ident)
    if not ident:
        print('darkwiki: ident not found', file=sys.stderr)
        return -1

    object_type = db.object_type(ident)
    print(object_type.name)

    return 0

def commit(parser):
    db = darkwiki.DiskDatabase()
    if parser.all:
        interface = darkwiki.Interface(db)
        interface.add_changed_files()
    ident = db.commit()
    print(ident)
    return 0

def log(parser):
    db = darkwiki.DiskDatabase()
    interface = darkwiki.Interface(db)
    log = interface.fetch_commits()
    previous = None
    for commit in log:
        if previous is not None:
            assert commit['ident'] == previous
        print(commit['ident'])
        print(commit['timestamp'], '+%s' % commit['utc_offset'])
        previous = commit['previous_commit']
        print()
    return 0

def diff(parser):
    db = darkwiki.DiskDatabase()
    interface = darkwiki.Interface(db)
    if parser.cached:
        diff_result = interface.diff_cached(parser.commit_ident)
    else:
        diff_result = interface.diff_noncached(parser.commit_ident)
    for filename, diffs in diff_result:
        print('---', filename)
        darkwiki.print_diff(diffs)
    return 0

def branch(parser):
    db = darkwiki.DiskDatabase()

    if parser.branch_name is None:
        display_branches(db)
        return 0

    ident = None
    if parser.commit_ident is not None:
        ident = db.fuzzy_match(parser.commit_ident)

    db.switch_branch(parser.branch_name, ident)

    return 0

def display_branches(db):
    branches = db.fetch_local_branches()
    current_branch = db.active_branch()
    for branch in branches:
        if branch == current_branch:
            print('*', colored(branch, 'green'))
        else:
            print(' ', branch)

if __name__ == '__main__':
    sys.exit(main())

