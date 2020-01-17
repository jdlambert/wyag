from GitRepository import GitRepository


class Handlers:
    def init(args):
        GitRepository.create(args.path)

    def cat_file(args):
        GitRepository.find().cat_file(args.object, fmt=args.type.encode())

    def cmd_hash_object(args):
        if args.write:
            repo = GitRepository(".")
        else:
            repo = None

        with open(args.path, "rb") as fd:
            sha = object_hash(fd, args.type.encode(), repo)
            print(sha)
