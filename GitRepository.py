import os
import sys
import configparser
import zlib
import collections
import re

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

    def object_resolve(self, name):
        candidates = list()
        hash_re = re.compile(r"^[0-9A-Fa-f]{1,16}$")

        # Empty string?  Abort.
        if not name.strip():
            return None

        # Head is nonambiguous
        if name == "HEAD":
            return [self.ref_resolve("HEAD")]

        if hash_re.match(name):
            if len(name) == 40:
                # This is a complete hash
                return [name.lower()]
            elif len(name) >= 4:
                # This is a small hash 4 seems to be the minimal length
                # for git to consider something a short hash.
                # This limit is documented in man git-rev-parse
                name = name.lower()
                prefix = name[0:2]
                path = self.repo_dir("objects", prefix, mkdir=False)
                if path:
                    rem = name[2:]
                    for f in os.listdir(path):
                        if f.startswith(rem):
                            candidates.append(prefix + f)

        return candidates

    def object_find(self, name, fmt=None, follow=True):
        sha = self.object_resolve(name)

        if not sha:
            raise Exception(f"No such reference {name}.")

        if len(sha) > 1:
            candidates = "\n -".join(sha)
            raise Exception(
                f"Ambiguous reference {name}: Candidates are:\n - {candidates}."
            )

        sha = sha[0]

        if not fmt:
            return sha

        while True:
            obj = self.object_read(sha)

            if obj.fmt == fmt:
                return sha

            if not follow:
                return None

            # Follow tags
            if obj.fmt == b"tag":
                sha = obj.kvlm[b"object"].decode("ascii")
            elif obj.fmt == b"commit" and fmt == b"tree":
                sha = obj.kvlm[b"tree"].decode("ascii")
            else:
                return None
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

    def tag_create(self, name, reference, create_tag_object):
        # get the GitObject from the object reference
        sha = self.object_find(reference)

        if create_tag_object:
            # create tag object (commit)
            tag = GitTag(self)
            tag.kvlm = collections.OrderedDict()
            tag.kvlm[b"object"] = sha.encode()
            tag.kvlm[b"type"] = b"commit"
            tag.kvlm[b"tag"] = name.encode()
            # TODO: add real messages and tagger
            tag.kvlm[b"tagger"] = b"The soul eater <grim@reaper.net>"
            tag.kvlm[
                b""
            ] = b"This is the commit message that should have come from the user\n"
            tag_sha = tag.object_write()
            # create reference
            self.ref_create("tags/" + name, tag_sha)
        else:
            # create lightweight tag (ref)
            self.ref_create("tags/" + name, sha)

    def ref_create(self, ref_name, sha):
        with open(self.repo_file("refs/" + ref_name), "w") as fp:
            fp.write(sha + "\n")

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
