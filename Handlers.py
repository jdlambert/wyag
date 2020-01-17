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
