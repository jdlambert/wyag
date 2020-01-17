import os
import sys
import configparser
import zlib
import collections

from GitObject import GitObject, GitBlob, GitCommit, GitTree


class GitRepository:
    """A git repository"""

    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = self.repo_file("config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")

    def repo_path(self, *path):
        """Compute path under repo's gitdir."""
        return os.path.join(self.gitdir, *path)

    def repo_file(self, *path, mkdir=False):
        """Same as repo_path, but create dirname(*path) if absent.  For
          example, repo_file(r, "refs", "remotes", "origin", "HEAD") will create
          .git/refs/remotes/origin."""

        if self.repo_dir(*path[:-1], mkdir=mkdir):
            return self.repo_path(*path)

    def repo_dir(self, *path, mkdir=False):
        """Same as repo_path, but mkdir *path if absent if mkdir."""

        path = self.repo_path(*path)

        if os.path.exists(path):
            if os.path.isdir(path):
                return path
            else:
                raise Exception(f"Not a directory {path}")

        if mkdir:
            os.makedirs(path)
            return path
        else:
            return None

    def object_read(self, sha):
        """Read object object_id from Git repository repo.  Return a
        GitObject whose exact type depends on the object."""

        path = self.repo_file("objects", sha[0:2], sha[2:])

        with open(path, "rb") as f:
            raw = zlib.decompress(f.read())

            # Read object type
            x = raw.find(b" ")
            fmt = raw[0:x]

            # Read and validate object size
            y = raw.find(b"\x00", x)
            size = int(raw[x:y].decode("ascii"))
            if size != len(raw) - y - 1:
                raise Exception(f"Malformed object {sha}: bad length")

            # Pick constructor
            if fmt == b"commit":
                c = GitCommit
            elif fmt == b"tree":
                c = GitTree
            elif fmt == b"tag":
                c = GitTag
            elif fmt == b"blob":
                c = GitBlob
            else:
                raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

            # Call constructor and return object
            return c(self, raw[y + 1 :])

    def object_find(self, name, fmt=None, follow=True):
        return name

    def cat_file(self, obj, fmt=None):
        obj = self.object_read(self.object_find(obj, fmt=fmt))
        sys.stdout.buffer.write(obj.serialize())

    def log_graphviz(self, sha, seen=None):

        seen = seen or set()

        if sha in seen:
            return
        seen.add(sha)

        commit = self.object_read(sha)
        assert commit.fmt == b"commit"

        if b"parent" not in commit.kvlm.keys():
            # Base case: the initial commit.
            return

        parents = commit.kvlm[b"parent"]

        for parent in parents:
            parent = parent.decode("ascii")
            print(f"c_{sha} -> c_{parent};")
            self.log_graphviz(parent, seen)

    def tree_checkout(self, tree, path):
        for item in tree.items:
            obj = self.object_read(item.sha)
            dest = os.path.join(path, item.path)

            if obj.fmt == b"tree":
                os.mkdir(dest)
                self.tree_checkout(obj, dest)
            elif obj.fmt == b"blob":
                with open(dest, "wb") as f:
                    f.write(obj.blobdata)

    def ref_resolve(self, ref):
        with open(self.repo_file(ref), "r") as fp:
            data = fp.read()[:-1]
            # Drop final \n ^^^^^
        if data.startswith("ref: "):
            return self.ref_resolve(data[5:])
        else:
            return data

    def ref_list(self, path=None):
        if path is None:
            path = self.repo_dir("refs")
        ret = collections.OrderedDict()

        for f in sorted(os.listdir(path)):
            can = os.path.join(path, f)
            if os.path.isdir(can):
                ret[f] = self.ref_list(can)
            else:
                ret[f] = self.ref_resolve(can)

        return ret

    def show_ref(self, refs, with_hash=True, prefix=""):
        for k, v in refs.items():
            if type(v) == str:
                print(
                    "{0}{1}{2}".format(
                        v + " " if with_hash else "", prefix + "/" if prefix else "", k,
                    )
                )
            else:
                self.show_ref(
                    v,
                    with_hash=with_hash,
                    prefix="{0}{1}{2}".format(prefix, "/" if prefix else "", k),
                )

    @staticmethod
    def create(path):
        """Create a new repository at path."""

        repo = GitRepository(path, True)

        # First, we make sure the path either doesn't exist or is an
        # empty dir.

        if os.path.exists(repo.worktree):
            if not os.path.isdir(repo.worktree):
                raise Exception(f"{path} is not a directory!")
            if os.listdir(repo.worktree):
                raise Exception(f"{path} is not empty!")
        else:
            os.makedirs(repo.worktree)

        assert repo.repo_dir("branches", mkdir=True)
        assert repo.repo_dir("objects", mkdir=True)
        assert repo.repo_dir("refs", "tags", mkdir=True)
        assert repo.repo_dir("refs", "heads", mkdir=True)

        # .git/description
        with open(repo.repo_file("description"), "w") as f:
            f.write(
                "Unnamed repository; edit this file 'description' to name the repository.\n"
            )

        # .git/HEAD
        with open(repo.repo_file("HEAD"), "w") as f:
            f.write("ref: refs/heads/master\n")

        with open(repo.repo_file("config"), "w") as f:
            config = GitRepository.default_config()
            config.write(f)

        return repo

    @staticmethod
    def default_config():
        ret = configparser.ConfigParser()

        ret.add_section("core")
        ret.set("core", "repositoryformatversion", "0")
        ret.set("core", "filemode", "false")
        ret.set("core", "bare", "false")

        return ret

    @staticmethod
    def find(path=".", required=True):
        path = os.path.realpath(path)

        if os.path.isdir(os.path.join(path, ".git")):
            return GitRepository(path)

        # If we haven't returned, recurse in parent, if w
        parent = os.path.realpath(os.path.join(path, ".."))

        if parent == path:
            # Bottom case
            # os.path.join("/", "..") == "/":
            # If parent==path, then path is root.
            if required:
                raise Exception("No git directory.")
            else:
                return None

        # Recursive case
        return GitRepository.find(parent, required)
