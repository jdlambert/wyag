import argparse

from Handlers import Handlers

argparser = argparse.ArgumentParser(description="The stupid content tracker")

argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")
argsp.add_argument(
    "path",
    metavar="directory",
    nargs="?",
    default=".",
    help="Where to create the repository.",
)

argsp = argsubparsers.add_parser(
    "cat-file", help="Provide content of repository objects"
)
argsp.add_argument(
    "type",
    metavar="type",
    choices=["blob", "commit", "tag", "tree"],
    help="Specify the type",
)
argsp.add_argument("object", metavar="object", help="The object to display")

argsp = argsubparsers.add_parser(
    "hash-object", help="Compute object ID and optionally creates a blob from a file"
)
argsp.add_argument(
    "-t",
    metavar="type",
    dest="type",
    choices=["blob", "commit", "tag", "tree"],
    default="blob",
    help="Specify the type",
)
argsp.add_argument(
    "-w",
    dest="write",
    action="store_true",
    help="Actually write the object into the database",
)
argsp.add_argument("path", help="Read object from <file>")

argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit", default="HEAD", nargs="?", help="Commit to start at.")

argsp = argsubparsers.add_parser(
    "checkout", help="Checkout a commit inside of a directory."
)
argsp.add_argument("commit", help="The commit or tree to checkout.")
argsp.add_argument("path", help="The EMPTY directory to checkout on.")

argsp = argsubparsers.add_parser("show-ref", help="List references.")

argsp = argsubparsers.add_parser("tag", help="List and create tags")
argsp.add_argument(
    "-a",
    action="store_true",
    dest="create_tag_object",
    help="Whether to create a tag object",
)
argsp.add_argument("name", nargs="?", help="The new tag's name")
argsp.add_argument(
    "object", default="HEAD", nargs="?", help="The object the new tag will point to"
)

argsp = argsubparsers.add_parser(
    "rev-parse", help="Parse revision (or other object) identifiers"
)
argsp.add_argument(
    "--wyag-type",
    metavar="type",
    dest="type",
    choices=["blob", "commit", "tag", "tree"],
    default=None,
    help="Specify the expected type",
)
argsp.add_argument("name", help="The name to parse")


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)

    handler = getattr(Handlers, args.command.replace("-", "_"))
    handler(args)
