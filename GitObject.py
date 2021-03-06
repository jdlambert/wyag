import hashlib
import zlib
import collections


def kvlm_parse(raw, start=0, kvs=None):
    if not kvs:
        kvs = collections.OrderedDict()

    # We search for the next space and the next newline.
    space = raw.find(b" ", start)
    newline = raw.find(b"\n", start)

    # If space appears before newline, we have a keyword.

    # Base case
    # =========
    # If newline appears first (or there's no space at all, in which
    # case find returns -1), we assume a blank line.  A blank line
    # means the remainder of the data is the message.
    if (space < 0) or (newline < space):
        assert newline == start
        kvs[b""] = [raw[start + 1 :]]
        return kvs

    # Recursive case
    # ==============
    # we read a key-value pair and recurse for the next.
    key = raw[start:space]

    # Find the end of the value.  Continuation lines begin with a
    # space, so we loop until we find a "\n" not followed by a space.
    end = start
    while True:
        end = raw.find(b"\n", end + 1)
        if raw[end + 1] != ord(" "):
            break

    # Grab the value
    # Also, drop the leading space on continuation lines
    value = raw[space + 1 : end].replace(b"\n ", b"\n")

    # Don't overwrite existing data contents
    if key in kvs:
        kvs[key].append(value)
    else:
        kvs[key] = [value]

    return kvlm_parse(raw, start=(end + 1), kvs=kvs)


def kvlm_serialize(kvlm):
    return b"\n".join(
        [
            key + b" " + val.replace(b"\n", b"\n ")
            for key, vals in kvlm.items()
            if key != b""
            for val in vals
        ]
        + kvlm[b""]
    )


class GitObject:

    repo = None

    def __init__(self, repo, data=None):
        self.repo = repo

        if data != None:
            self.deserialize(data)

    def serialize(self):
        """
        This function MUST be implemented by subclasses.
        It must read the object's contents from self.data, a byte string, and do
        whatever it takes to convert it into a meaningful representation.
        What exactly that means depend on each subclass.
        """
        raise Exception("Unimplemented!")

    def deserialize(self, data):
        raise Exception("Unimplemented!")

    def object_write(self, actually_write=True):
        # Serialize object data
        data = self.serialize()
        # Add header
        result = self.fmt + b" " + str(len(data)).encode() + b"\x00" + data
        # Compute hash
        sha = hashlib.sha1(result).hexdigest()

        if actually_write:
            # Compute path
            path = self.repo.repo_file(
                "objects", sha[0:2], sha[2:], mkdir=actually_write
            )

            with open(path, "wb") as f:
                # Compress and write
                f.write(zlib.compress(result))

        return sha

    @staticmethod
    def hash(fd, fmt, repo=None):
        data = fd.read()

        # Choose constructor depending on
        # object type found in header.
        if fmt == b"commit":
            obj = GitCommit(repo, data)
        elif fmt == b"tree":
            obj = GitTree(repo, data)
        elif fmt == b"tag":
            obj = GitTag(repo, data)
        elif fmt == b"blob":
            obj = GitBlob(repo, data)
        else:
            raise Exception(f"Unknown type {fmt}!")

        return obj.object_write(repo)


class GitBlob(GitObject):

    fmt = b"blob"

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data


class GitCommit(GitObject):
    fmt = b"commit"

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)

    def serialize(self):
        return kvlm_serialize(self.kvlm)


class GitTreeLeaf:
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha


def tree_parse_one(raw, start=0):
    # Find the space terminator of the mode
    x = raw.find(b" ", start)
    assert x - start is 5 or x - start is 6

    # Read the mode
    mode = raw[start:x]

    # Find the NULL terminator of the path
    y = raw.find(b"\x00", x)
    # and read the path
    path = raw[x + 1 : y]

    # Read the SHA and convert to an hex string
    # hex() adds 0x in front, we don't want that.
    sha = hex(int.from_bytes(raw[y + 1 : y + 21], "big"))[2:]
    return y + 21, GitTreeLeaf(mode, path, sha)


def tree_parse(raw):
    pos = 0
    ret = list()
    while pos < len(raw):
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)

    return ret


def tree_serialize(obj):
    return "".join(
        [
            item.mode
            + b" "
            + item.path
            + b"\x00"
            + int(item.sha, 16).to_bytes(20, byteorder="big")
            for item in obj.items
        ]
    )


class GitTree(GitObject):
    fmt = b"tree"

    def deserialize(self, data):
        self.items = tree_parse(data)

    def serialize(self):
        return tree_serialize(self)


class GitTag(GitCommit):
    fmt = b"tag"
