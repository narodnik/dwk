import darkwiki
import os

class DirectoryTree:

    def __init__(self, name=None):
        self.name = name
        self.subdirs = []
        self.files = []
        self.parent = None
        self.ident = None

    @property
    def full_path(self):
        if self.parent is None:
            return self.name
        parent_path = self.parent.full_path
        if parent_path is None:
            return self.name
        return os.path.join(self.parent.full_path, self.name)

    def add_subdir(self, subdir):
        self.subdirs.append(subdir)
        subdir.parent = self

    def add_file(self, mode, ident, filename):
        assert not [blob for blob in self.files if blob.ident == ident]
        assert not [blob for blob in self.files if blob.filename == filename]
        self.files.append(BlobFile(mode, ident, filename, self))

    def _find_or_create_impl(self, path_split):
        if not path_split:
            return self

        current_path = path_split[0]
        match = [subdir for subdir in self.subdirs
                 if subdir.name == current_path]
        if not match:
            parent_directory = self
            for current_path in path_split:
                subdir = DirectoryTree(current_path)
                parent_directory.add_subdir(subdir)
                parent_directory = subdir
            return subdir

        assert len(match) == 1
        match = match[0]
        return match._find_or_create_impl(path_split[1:])

    def find_or_create_subdir(self, path):
        return self._find_or_create_impl(split_path(path))

class BlobFile:

    def __init__(self, mode, ident, filename, parent):
        self.mode = mode
        self.ident = ident
        self.filename = filename
        self.parent_directory = parent

    @property
    def full_filename(self):
        if self.parent_directory.full_path is None:
            return self.filename
        return os.path.join(self.parent_directory.full_path, self.filename)

    @property
    def dirname(self):
        return self.parent_directory.full_path

    def __repr__(self):
        return '<%s %s %s>' % (self.mode, self.ident, self.full_filename)

    def attributes_fullpath(self):
        return (self.mode, self.ident, self.full_filename)

    def attributes(self):
        return (self.mode, self.ident, self.filename)

def walk_tree(root_node):
    for child in root_node.subdirs:
        for node in walk_tree(child):
            yield node
    yield root_node

def split_path(path):
    if not path:
        return []
    path = os.path.normpath(path)
    path = path.lstrip(os.sep)
    return path.split(os.sep)

def build_tree(index):
    root = DirectoryTree()
    for mode, ident, filename in index:
        prefix = os.path.dirname(filename)
        subdir = root.find_or_create_subdir(prefix)
        filename = os.path.basename(filename)
        subdir.add_file(mode, ident, filename)
    return root

def read_tree(db, tree_ident, tree_name=None):
    object_type, tree_contents = db.fetch(tree_ident)
    assert object_type == darkwiki.DataType.TREE

    tree = DirectoryTree(tree_name)

    for mode, object_type, ident, filename in tree_contents:
        if object_type == darkwiki.DataType.BLOB:
            tree.add_file(mode, ident, filename)
        elif object_type == darkwiki.DataType.TREE:
            subtree = read_tree(db, ident, filename)
            tree.add_subdir(subtree)

    return tree

def all_files(tree_root):
    flatten = lambda lists: [item for sublist in lists for item in sublist]
    return flatten(tree.files for tree in walk_tree(tree_root))

if __name__ == '__main__':
    root = DirectoryTree()
    foo = DirectoryTree('foo')
    root.add_subdir(foo)
    zz = DirectoryTree('zz')
    foo.add_subdir(zz)
    bar = DirectoryTree('bar')
    root.add_subdir(bar)

    xyz = DirectoryTree('xyz')
    zz.add_subdir(xyz)

    b2 = DirectoryTree('b2')
    bar.add_subdir(b2)

    zz = root.find_or_create_subdir('foo/zz')
    zz.add_file('644', 'ident_abc', 'abc.txt')
    zz.add_file('644', 'ident_test123', 'test123.txt')
    zz.add_file('644', 'ident_zz', 'zz.txt')

    ab = root.find_or_create_subdir('foo/zz/abab')
    ab.add_file('644', 'ident_ab', 'ab.txt')

    aha = root.find_or_create_subdir('ahafoo/zz/abab')
    aha.add_file('644', 'aha_id', 'aha.jpg')
    aha.add_file('644', 'aha_id1', 'aha1.jpg')
    aha.add_file('644', 'aha_id2', 'aha2.jpg')

    for directory in walk_tree(root):
        print(directory.full_path)
        print(directory.files)

