import darkwiki
from darkwiki.difference_engine import *

class Interface:

    def __init__(self, db):
        self._db = db

    def _fetch_commit(self, current_commit_ident):
        object_type, commit = self._db.fetch(current_commit_ident)
        commit['ident'] = current_commit_ident
        assert object_type == darkwiki.DataType.COMMIT
        current_commit_ident = commit['previous_commit']
        return current_commit_ident, commit

    def fetch_commits(self):
        results = []
        commit_ident = self._db.last_commit_ident()
        while commit_ident is not None:
            commit_ident, commit = self._fetch_commit(commit_ident)
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
