"""
Upload images from twitter user to a subreddit

This file is commandline only.
"""
import logging
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from sys import stdout
from time import sleep

from dotenv import load_dotenv
from yaml import Loader, load

from twitter2reddit import TwitterToReddit


def main(arguments: list[str] = None) -> None:
    """
    Process from command line

    Use `--help` argument to get info
    """
    load_dotenv()

    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("--log", dest="logfile", help="log file", metavar="LOGFILE")
    parser.add_argument(
        "--mode",
        dest="mode",
        help="level to log at",
        metavar="MODE",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    parser.add_argument(
        "--quite",
        dest="quite",
        default=False,
        action="store_true",
        help="quite output",
    )
    parser.add_argument(
        "filename", help="file to load archive info from", metavar="YAMLFILE"
    )
    parser.add_argument(
        "-d",
        "--database",
        dest="database",
        default="database.db",
        help="tinydb file",
        metavar="DB",
    )
    parser.add_argument(
        "-a",
        "--attempts",
        dest="attempts",
        default=75,
        type=int,
        help="number of times to check for new comic if none found",
        metavar="NUM",
    )
    parser.add_argument(
        "--delay",
        dest="delay",
        default=60,
        type=int,
        help="number of times to check for a new upload if it gets posted later than normal",
        metavar="NUM",
    )

    args = parser.parse_args(arguments)
    handler_list = (
        [logging.StreamHandler(stdout), logging.FileHandler(args.logfile)]
        if args.logfile
        else [logging.StreamHandler(stdout)]
    )

    logging.basicConfig(
        format="%(asctime)s\t[%(levelname)s]\t{%(module)s}\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
        handlers=handler_list,
    )

    with open(args.filename, "r") as fp:
        settings = load(fp, Loader=Loader)

    attempts = 1
    delay = 1
    t2r = TwitterToReddit(settings)
    posts = None
    while posts is None and delay <= args.delay:
        posts = t2r.upload()
        sleep(60)
        delay += 1

    while posts is not None and len(posts) == 0 and attempts <= args.attempts:
        logging.warning(
            (
                "No posts were made, sleeping for 1 min to try again. "
                "Will attempt %d more times before exiting."
            ),
            args.attempts - attempts,
        )
        sleep(60)
        posts = t2r.upload()
        attempts += 1

    if posts is not None and len(posts) == 0:
        logging.error("No posts made successfully")


if __name__ == "__main__":
    main()
