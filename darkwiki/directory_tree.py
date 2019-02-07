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

    def add_file(self, ident, filename):
        assert ident not in [ident for ident, _ in self.files]
        assert filename not in [filename for _, filename in self.files]
        self.files.append((ident, filename))

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

def walk_tree(root_node):
    for child in node.subdirs:
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
    for ident, filename in index:
        prefix = os.path.dirname(filename)
        subdir = root.find_or_create_subdir(prefix)
        subdir.add_file(ident, filename)
    return root

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
    zz.add_file('ident_abc', 'abc.txt')
    zz.add_file('ident_test123', 'test123.txt')
    zz.add_file('ident_zz', 'zz.txt')

    ab = root.find_or_create_subdir('foo/zz/abab')
    ab.add_file('ident_ab', 'ab.txt')

    aha = root.find_or_create_subdir('ahafoo/zz/abab')
    aha.add_file('aha_id', 'aha.jpg')
    aha.add_file('aha_id1', 'aha1.jpg')
    aha.add_file('aha_id2', 'aha2.jpg')

    for directory in walk_tree(root):
        print(directory.full_path)
        print(directory.files)

