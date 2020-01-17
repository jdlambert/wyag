import os

from GitRepository import GitRepository


class Handlers:
    def init(args):
        GitRepository.create(args.path)

    def cat_file(args):
        GitRepository.find().cat_file(args.object, fmt=args.type.encode())

    def hash_object(args):
        if args.write:
            repo = GitRepository(".")
        else:
            repo = None

        with open(args.path, "rb") as fd:
            sha = object_hash(fd, args.type.encode(), repo)
            print(sha)

    def log(args):
        repo = GitRepository.find()

        print("digraph wyaglog{")
        repo.log_graphviz(repo.object_find(args.commit))
        print("}")

    def checkout(args):
        repo = GitRepository.find()

        obj = repo.object_read(repo.object_find(args.commit))

        # If the object is a commit, we grab its tree
        if obj.fmt == b"commit":
            obj = repo.object_read(obj.kvlm[b"tree"][0].decode("ascii"))

        # Verify that path is an empty directory
        if os.path.exists(args.path):
            if not os.path.isdir(args.path):
                raise Exception(f"Not a directory {args.path}!")
            if os.listdir(args.path):
                raise Exception(f"Not empty {args.path}!")
        else:
            os.makedirs(args.path)

        repo.tree_checkout(obj, os.path.realpath(args.path).encode())

    def show_ref(args):
        repo = GitRepository.find()
        repo.show_ref(repo.ref_list(), prefix="refs")
