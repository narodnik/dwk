import darkwiki
import os

def filter_one(vector, predicate):
    match = [x for x in vector if predicate(x)]
    if not match:
        return None
    return match[0]

class DifferenceInterfaceDisk:

    def __init__(self, db):
        self._db = db
        self._ident_map = {}
        self._files = self._files_list()

    def _files_list(self):
        # Use filenames from index as list of files
        filenames = [filename for _, _, filename in self._db.read_index()]

        files = []
        for filename in filenames:
            ident = self._db.hash_file(filename)
            files.append(('644', ident, filename))

            self._ident_map[ident] = filename

        return files

    def files_list(self):
        return self._files

    def fetch(self, ident):
        assert ident in self._ident_map
        filename = self._ident_map[ident]
        contents = self._db.open_file(filename, 'r').read()
        contents = contents.decode()
        return contents

class DifferenceInterfaceIndex:

    def __init__(self, db):
        self._db = db

    def files_list(self):
        # Use files from index as list of files
        return self._db.read_index()

    def fetch(self, ident):
        object_type, contents = self._db.fetch(ident)
        assert object_type == darkwiki.DataType.BLOB
        contents = contents.decode()
        return contents

class DifferenceInterfaceCommit:

    def __init__(self, db, commit_ident=None):
        self._db = db
        self._tree = self._load_tree_root(commit_ident)

    def _load_tree_root(self, commit_ident):
        if commit_ident is None:
            commit_ident = self._db.last_commit_ident()
        else:
            commit_ident = self._db.fuzzy_match(commit_ident)

        assert commit_ident is not None

        # Read root tree of commit
        object_type, commit = self._db.fetch(commit_ident)
        assert object_type == darkwiki.DataType.COMMIT

        tree_root_ident = commit['tree']
        return darkwiki.read_tree(self._db, tree_root_ident)

    def files_list(self):
        return [blob.attributes() for blob in darkwiki.all_files(self._tree)]

    def fetch(self, ident):
        object_type, contents = self._db.fetch(ident)
        assert object_type == darkwiki.DataType.BLOB
        contents = contents.decode()
        return contents

class DifferenceEngine:

    def __init__(self, interface_1, interface_2):
        self._interface_1 = interface_1
        self._interface_2 = interface_2

    def results(self):
        results = []

        files_1 = self._interface_1.files_list()
        files_2 = self._interface_2.files_list()

        # Rotates a list of lists
        transpose = lambda list_lists: list(map(list, zip(*list_lists)))

        _, _, filenames_1 = transpose(files_1)
        _, _, filenames_2 = transpose(files_2)

        # Deleted files
        self._exclusion(results, self._interface_1, files_1, filenames_2, -1)
        # Added files
        self._exclusion(results, self._interface_2, files_2, filenames_1, 1)

        shared_files = self._compute_shared_files(
            files_1, filenames_1, files_2, filenames_2)

        # Perform main diff
        for new_mode, new_ident, filename in shared_files:
            result = self._main_diff(new_mode, new_ident, filename, files_1)
            if result is None:
                continue
            results.append(result)

        return results

    def _exclusion(self, results, interface, files_a, filenames_b, sign):
        exclude_items = lambda files_a, filenames_b: \
            [(mode, ident, filename) for mode, ident, filename
             in files_a if filename not in filenames_b]

        files_only_in_a = exclude_items(files_a, filenames_b)

        for mode, ident, filename in files_only_in_a:
            contents = interface.fetch(ident)
            diffs = [(sign, contents)]
            results.append((filename, diffs))

    def _compute_shared_files(self, files_1, filenames_1, files_2, filenames_2):
        intersect = lambda list_1, list_2: \
            [value for value in list_1 if value in list_2]

        shared_filenames = intersect(filenames_1, filenames_2)
        shared_files = [(mode, ident, filename) for mode, ident, filename
                        in files_2 if filename in shared_filenames]
        return shared_files

    def _main_diff(self, new_mode, new_ident, filename, files_1):
        filename_equal = lambda item: item[2] == filename

        previous_file = filter_one(files_1, filename_equal)
        assert previous_file is not None
        _, previous_ident, _ = previous_file

        # Skip unchanged files
        if previous_ident == new_ident:
            return None

        previous_contents = self._interface_1.fetch(previous_ident)
        new_contents = self._interface_2.fetch(new_ident)

        # Perform the diff between both contents
        diffs = darkwiki.difference(previous_contents, new_contents)

        return filename, diffs
