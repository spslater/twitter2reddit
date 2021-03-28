"""
Upload images from twitter user to a subreddit

This file is commandline only.
"""
import logging
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from sys import stdout
from time import sleep
from yaml import load, Loader

from dotenv import load_dotenv

from twitter2reddit import TwitterToReddit


def main():
    """
    Process from command line

    Use `--help` argument to get info
    """
    load_dotenv()

    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-l", "--log", dest="logfile", help="Log file.", metavar="LOGFILE"
    )
    parser.add_argument(
        "-q",
        "--quite",
        dest="quite",
        default=False,
        action="store_true",
        help="Quite output",
    )
    parser.add_argument(
        "filename", help="File to load archive info from.", metavar="YAMLFILE"
    )
    parser.add_argument(
        "-d",
        "--database",
        dest="database",
        default="database.db",
        help="tinydb file.",
        metavar="DB",
    )

    args = parser.parse_args()
    handler_list = (
        [logging.StreamHandler(stdout), logging.FileHandler(args.logfile)]
        if args.logfile
        else [logging.StreamHandler(stdout)]
    )

    logging.basicConfig(
        format="%(asctime)s\t[%(levelname)s]\t{%(module)s}\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
        handlers=handler_list,
    )

    with open(args.filename, "r") as fp:
        settings = load(fp, Loader=Loader)

    attemps = 1
    t2r = TwitterToReddit(settings)
    posts = t2r.upload()
    while posts is not None and len(posts) == 0 and attemps <= 60:
        logging.warning(
            "No posts were made, sleeping for 1 min to try again. \
                Will attempt %d more times before exiting.",
            60 - attemps,
        )
        sleep(60)
        posts = t2r.upload()
        attemps += 1

    if posts is not None and len(posts) == 0:
        logging.error("No posts made successfully")


if __name__ == "__main__":
    main()
