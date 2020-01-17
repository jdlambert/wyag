from GitRepository import GitRepository


class Handlers:
    def init(args):
        GitRepository.create(args.path)

    def cat_file(args):
        GitRepository.find().cat_file(args.object, fmt=args.type.encode())
