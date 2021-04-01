"""Convert old style (v1.0.0) database to new style (v2.0.0)

:raises IOError: unable to write to database
"""
import logging
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from io import UnsupportedOperation
from json import dumps
from os import fsync
from sys import stdout

from yaml import load, Loader

from tinydb import JSONStorage, TinyDB, where


class PrettyJSONStorage(JSONStorage):
    """Store the TinyDB with pretty json

    Should be passed into a TinyDB constructor as the `storage` argument
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, data: object):
        """Write data to database in a pretty json format

        Indents by 4 spaces and sorts keys

        :param data: data to be saved in json format, needs to be json serializeable
        :type data: object
        :return: none
        :rtype: None
        """
        self._handle.seek(0)
        serialized = dumps(data, indent=4, sort_keys=True, **self.kwargs)
        try:
            self._handle.write(serialized)
        except UnsupportedOperation as e:
            raise IOError(
                f'Cannot write to the database. Access mode is "{self._mode}"'
            ) from e

        self._handle.flush()
        fsync(self._handle.fileno())

        self._handle.truncate()


def main():
    """Convert old style (v1.0.0) database to new style (v2.0.0)"""
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("--log", dest="logfile", help="Log file.", metavar="LOGFILE")
    parser.add_argument(
        "settings", help="env file that has info in it", metavar="yaml"
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

    with open(args.settings, "r") as fp:
        config = load(fp, Loader=Loader)

    database = TinyDB(config.get("database"), storage=PrettyJSONStorage)
    table = database.table(config.get("table"))
    meta = database.table("meta")
    if not meta.search(where("table") == config.get("table")):
        logging.info("Getting meta info")
        number = table.search(where("number_counter").exists())[0]["number"]
        meta_document = {
            "imgur": {
                "album_id": config.get("all_aid"),
                "deletehash": config.get("all_hash"),
                "title": config.get("all_name"),
                "description": config.get("all_desc"),
            },
            "number": number,
            "reddit": {"subreddit": config.get("subreddit")},
            "table": config.get("table"),
            "twitter": {
                "user_name": config.get("user"),
                "user_url": f"https://twitter.com/{config.get('user')}",
            },
        }
        logging.info("Adding meta info")
        meta.upsert(meta_document, where("table") == config.get("table"))
        try:
            counter = table.search(where("number_counter").exists())[0]
            logging.info(
                "Removing number counter from main table, current value is %s", counter
            )
            table.remove(doc_ids=[counter.doc_id])
        except IndexError:
            pass
    comics = table.search(where("sid").exists())
    for comic in comics:
        logging.info(
            'Generating new document for doc_id "%d" with sid "%d"',
            comic.doc_id,
            comic["sid"],
        )
        new_document = {
            "comic": {
                "number": comic["number"],
                "title": comic["title"]
                if "title" in comic
                else f"#{comic['number']} - {comic['raw']}",
            },
            "imgur": {
                "album_id": comic["aid"]
                if comic["aid"] is not None
                else (
                    config.get("all_aid")
                    if (
                        comic["album"] is None
                        or config.get("all_hash") == comic["album"]
                    )
                    else None
                ),
                "deletehash": comic["album"]
                if comic["album"]
                else config.get("all_hash"),
                "direct_link": comic["url"],
                "image_id": comic["imgs"][0],
            },
            "reddit": {"comment": comic["comment"], "post": comic["post"]},
            "twitter": {
                "date": None,
                "display_name": comic["name"],
                "media": None,
                "status_id": comic["sid"],
                "text": comic["raw"],
                "tweet": comic["tweet"],
                "user_name": comic["user"],
            },
        }
        new_doc_id = table.insert(new_document)
        logging.info('Inserted new document with id "%d"', new_doc_id)
        logging.info('Removing old doc_id of "%d"', comic.doc_id)
        table.remove(doc_ids=[comic.doc_id])
    logging.info("Update %d comics into new format", len(comics))


if __name__ == "__main__":
    main()
