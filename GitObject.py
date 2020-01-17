import hashlib
import zlib


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


class GitBlob(GitObject):

    fmt = b"blob"

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data
