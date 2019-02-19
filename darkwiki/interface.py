import darkwiki
from darkwiki.difference_engine import *

class Interface:

    def __init__(self, db):
        self._db = db

    def fetch_commit(self, current_commit_ident):
        object_type, commit = self._db.fetch(current_commit_ident)
        commit['ident'] = current_commit_ident
        assert object_type == darkwiki.DataType.COMMIT
        current_commit_ident = commit['previous_commit']
        return current_commit_ident, commit

    def fetch_commits(self):
        results = []
        commit_ident = self._db.last_commit_ident()
        while commit_ident is not None:
            commit_ident, commit = self.fetch_commit(commit_ident)
            results.append(commit)
        return results

    def diff_cached(self, commit_ident):
        interface_commit = DifferenceInterfaceCommit(self._db, commit_ident)
        interface_index = DifferenceInterfaceIndex(self._db)

        differentiator = DifferenceEngine(interface_commit, interface_index)

        return differentiator.results()

    def diff_noncached(self, commit_ident):
        if commit_ident is not None:
            interface_previous = \
                DifferenceInterfaceCommit(self._db, commit_ident)
        else:
            interface_previous = DifferenceInterfaceIndex(self._db)

        interface_disk = DifferenceInterfaceDisk(self._db)

        differentiator = DifferenceEngine(interface_previous, interface_disk)
        return differentiator.results()

    def add_changed_files(self):
        # Loop through files in index
        for mode, ident, filename in self._db.read_index():
            file_ident = self._db.hash_file(filename)

            # Skip unchanged files
            if file_ident == ident:
                continue

            # Add changed file
            self._db.add_file(filename)

    def branches_tips(self):
        branches = self._db.fetch_local_branches()
        tips = {}
        for branch_name in branches:
            commit_ident = self._db.branch_last_commit_ident(branch_name)
            tips[branch_name] = commit_ident
        return tips

    def resolve_missing_objects(self, ident):
        missing = []

        if not self._db.exists(ident):
            return [ident]

        type_, object_ = self._db.fetch(ident)
        if type_ == darkwiki.DataType.BLOB:
            return []
        elif type_ == darkwiki.DataType.TREE:
            for mode, type_, ident, filename in object_:
                assert type_ != darkwiki.DataType.COMMIT
                missing += self.resolve_missing_objects(ident)
        else:
            previous_commit_ident = object_['previous_commit']
            if previous_commit_ident is not None:
                missing += self.resolve_missing_objects(previous_commit_ident)

            tree_root_ident = object_['tree']
            missing += self.resolve_missing_objects(tree_root_ident)

        return missing

    def merge(self, local_branch, merge_branch):
        print('Merging', local_branch, merge_branch)

        local_last = self._db.branch_last_commit_ident(local_branch)
        merge_last = self._db.branch_last_commit_ident(merge_branch)

        local_interface = darkwiki.MergeInterface(self._db, self, local_last)
        merge_interface = darkwiki.MergeInterface(self._db, self, merge_last)

        merge_engine = darkwiki.MergeEngine(local_interface, merge_interface)
        commit_ident = merge_engine.merge_3way()

