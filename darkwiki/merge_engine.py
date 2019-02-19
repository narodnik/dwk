import darkwiki

def get_first_common_element(x, y):
    ''' Fetches first element from x that is common for both lists
        or return None if no such an element is found.
    '''
    for i in x:
        if i in y:
            return i

    return None

class MergeInterface:

    def __init__(self, db, interface, commit_ident):
        self.db = db
        self.interface = interface

        self._commit_ident = commit_ident
        self.tree = self._load_tree_root()

    def simple_log(self):
        commit_ident = self._commit_ident
        results = []
        while commit_ident is not None:
            results.append(commit_ident)
            commit_ident, commit = self.interface.fetch_commit(commit_ident)
        return results

    def _load_tree_root(self):
        assert self._commit_ident is not None

        # Read root tree of commit
        object_type, commit = self.db.fetch(self._commit_ident)
        assert object_type == darkwiki.DataType.COMMIT

        tree_root_ident = commit['tree']
        return darkwiki.read_tree(self.db, tree_root_ident)

    def files_list(self):
        return [blob.attributes_fullpath()
                for blob in darkwiki.all_files(self.tree)]

    def fetch(self, ident):
        object_type, contents = self.db.fetch(ident)
        assert object_type == darkwiki.DataType.BLOB
        contents = contents.decode()
        return contents

def make_origin_interface(interface_1, interface_2):
    log_1 = interface_1.simple_log()
    log_2 = interface_2.simple_log()

    origin_ident = get_first_common_element(log_1, log_2)

    return MergeInterface(interface_1.db, interface_1.interface, origin_ident)

class MergeEngine:

    def __init__(self, local_interface, merge_interface):
        self.local_interface = local_interface
        self.merge_interface = merge_interface

    def merge_3way(self):
        origin_interface = make_origin_interface(self.local_interface,
                                                 self.merge_interface)

        # Accept files only in #1 and only in #2
        # Prefer updated files over origin
        # Only use origin when #1 and #2 change the same files

        local_files = self.local_interface.files_list()
        merge_files = self.merge_interface.files_list()
        origin_files = origin_interface.files_list()

        #print('Local files:')
        #[print(file_[2]) for file_ in local_files]
        #print()
        #print('Merge files:')
        #[print(file_[2]) for file_ in merge_files]
        #print()
        #print('Origin files:')
        #[print(file_[2]) for file_ in origin_files]
        #print()
        #print('---------------------')
        #print()

        origin_files_map = dict((filename, (mode, ident, filename))
                                for mode, ident, filename in origin_files)
        local_files_map = dict((filename, (mode, ident, filename))
                               for mode, ident, filename in local_files)
        merge_files_map = dict((filename, (mode, ident, filename))
                               for mode, ident, filename in merge_files)

        # Local files changed since origin
        local_changed_files = \
            self.compare_with_origin(local_files, origin_files_map)

        #print('Local changed files:')
        #[print(file_[2]) for file_ in local_changed_files]
        #print()
        #print('---------------------')
        #print()

        # Merge files changed since origin
        merge_changed_files = \
            self.compare_with_origin(merge_files, origin_files_map)

        #print('Merge changed files:')
        #[print(file_[2]) for file_ in merge_changed_files]
        #print()
        #print('---------------------')
        #print()

        # Duplicate local tree
        new_index = []

        # Combine everything
        for local_file in self.local_interface.files_list():
            local_mode, local_ident, local_filename = local_file

            # Conflicts: perform 3 way merge and apply to local tree
            if (local_filename in merge_files_map and
                merge_files_map[local_filename][1] != local_ident):

                merge_ident = merge_files_map[local_filename][1]

                if local_filename in origin_files_map:
                    origin_ident = origin_files_map[local_filename][1]

                    ident = self._merge_3(origin_ident, local_ident,
                                          merge_ident)

                    print('3way merge:', local_filename)
                    new_index.append((local_mode, ident, local_filename))
                else:
                    print('Rebasing:', local_filename)
                    # Unimplemented
                    # Weaker algorithm, just rebase against local
                    assert False
            else:
                new_index.append(local_file)

        for merge_file in merge_files:
            merge_mode, merge_ident, merge_filename = merge_file

            if merge_filename not in local_files_map:
                new_index.append(merge_file)
                print('Adding file:', merge_filename)

        root = darkwiki.build_tree(new_index)
        #print()
        #print('New tree:')
        #[print(index) for index in darkwiki.all_files(root)]
        #print()
        #print('---------------------')
        #print()
        db = self.local_interface.db
        tree_ident = db.write_dirtree(root)
        ident = db.commit(root_tree_ident=tree_ident)
        return ident

    def _merge_3(self, origin_ident, local_ident, merge_ident):
        origin_contents = self._fetch_blob(origin_ident)
        local_contents = self._fetch_blob(local_ident)
        merge_contents = self._fetch_blob(merge_ident)
        diffs = darkwiki.three_way_merge(origin_contents, local_contents,
                                         merge_contents)
        data = ''
        for index, text in diffs:
            if index == 0 or index == 1:
                data += text

        db = self.local_interface.db
        ident = db.add_object(data.encode(), darkwiki.DataType.BLOB)
        return ident

    def _fetch_blob(self, ident):
        db = self.local_interface.db
        type_, object_ = db.fetch(ident)
        assert type_ == darkwiki.DataType.BLOB
        return object_.decode()

    def compare_with_origin(self, files, origin_files_map):
        changed_files = []

        for file_ in files:
            mode, ident, filename = file_

            if filename not in origin_files_map:
                changed_files.append(file_)
                continue

            _, origin_file_ident, _ = origin_files_map[filename]
            if ident != origin_file_ident:
                changed_files.append(file_)

        return changed_files

