from GitRepository import GitRepository

class Handlers:
    def init(args):
        GitRepository.create(args.path)
