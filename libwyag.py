import argparse
import collections
import hashlib
import re
import sys
import zlib

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


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)

    handler = getattr(Handlers, args.command.replace("-", "_"))
    handler(args)
