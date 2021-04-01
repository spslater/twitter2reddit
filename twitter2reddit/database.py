"""
TinyDB Interface

Classes:
    Database
"""
import logging
from io import UnsupportedOperation
from json import dumps
from os import fsync

from tinydb import JSONStorage, TinyDB, where
from tinydb.operations import increment


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


class Database:
    """
    TinyDB interface

    Args:
        filename (str): tinyDB file
        table (str): name of table to get data from

    Attributes:
        table_name (str): name of table for data
        database (TinyDB): tinyDB database
        table (Table): table instance from TinyDB database
        number_id (int): doc_id of the number tracker

    Methods:
        upsert: upsert new data to the table
        check_upload: check if a key/value pair exists
        get_docs: get docts where is matches one of multiple vals for key
        get_number: get current image number
        increment_number: increase image number by 1
    """

    def __init__(self, filename: str, table: str, first_time: dict = None) -> None:
        self.table_name = table
        self.database = TinyDB(filename, storage=PrettyJSONStorage)
        self.table = self.database.table(self.table_name)
        self.meta = self.database.table("meta")
        if first_time:
            first_time = self._check_first_time(first_time, table)
            self.meta.upsert(first_time, where("table") == first_time["table"])
        self.number_id = None

    @staticmethod
    def _check_first_time(first_time: dict, table: str) -> dict:
        """Verify first_time settings are valid

        :param first_time: dictionary of first_time setup values
        :type first_time: dict
        :param table: table name to store info
        :param type: str
        :return: validated settings
        :rtype: dict
        """
        if "table" not in first_time:
            first_time["table"] = table
        elif first_time["table"] != table:
            raise KeyError(
                (
                    f"Table does not match settings table name: "
                    f"fist_time ({first_time['table']}) vs settings ({table})"
                )
            )

        if "number" not in first_time:
            first_time["number"] = 1

        if "imgur" not in first_time:
            album_id = first_time.get("album_id")
            deletehash = first_time.get("deletehash")
            title = first_time["title"]
            description = (
                first_time["description"]
                if "description" in first_time
                else (
                    f"{title} art by @{first_time['twitter']['user_name']} "
                    f"- https://twitter.com/{first_time['twitter']['user_name']}"
                )
            )

            first_time["imgur"] = {
                "album_id": album_id,
                "deletehash": deletehash,
                "description": description,
                "title": title,
            }
        first_time.pop("album_id", None)
        first_time.pop("deletehash", None)
        first_time.pop("title", None)
        first_time.pop("description", None)

        if "user_name" in first_time and "twitter" not in first_time:
            first_time["twitter"] = {
                "user_name": first_time["user_name"],
                "user_url": first_time["user_url"]
                if "user_url" in first_time
                else f"https://twitter.com/{first_time['user_name']}",
            }
        elif (
            "user_name" in first_time
            and "user_name" in first_time["twitter"]
            and first_time["user_name"] != first_time["twitter"]["user_name"]
        ):
            raise KeyError(
                (
                    f"Duplicate user names listed at root and in twitter: "
                    f"{first_time['user_name']} vs {first_time['twitter']['user_name']}"
                )
            )
        first_time.pop("user_name", None)
        first_time.pop("user_url", None)

        if "subreddit" in first_time and "reddit" not in first_time:
            first_time["reddit"] = {"subreddit": first_time["subreddit"]}
        elif (
            "subreddit" in first_time
            and "reddit" in first_time
            and "subreddit" not in first_time["reddit"]
        ):
            first_time["reddit"] = {"subreddit": first_time["subreddit"]}
        elif (
            "subreddit" in first_time
            and "reddit" in first_time
            and "subreddit" in first_time["reddit"]
        ):
            if first_time["subreddit"] != first_time["reddit"]["subreddit"]:
                raise KeyError(
                    (
                        f"Duplicate subreddits listed at root and in reddit: "
                        f"{first_time['subreddit']} vs {first_time['reddit']['subreddit']}"
                    )
                )
        first_time.pop("subreddit", None)

        return first_time

    def update_meta(self, update: dict) -> dict:
        """Update meta table info

        :param update: dictionary with updated data
        :type update: dict
        :return: full settings dictionary with updated values
        :rtype: dict
        """
        self.meta.update(update, where("table") == self.table_name)
        return self.get_settings()

    def get_settings(self) -> dict:
        """Get meta settings for the table

        :return: meta dict
        :rtype: dict
        """
        if not self.number_id:
            results = self.meta.search(where("table") == self.table_name)
            self.number_id = results[0].doc_id
        settings = self.meta.get(doc_id=self.number_id)
        return settings

    def upsert(self, data: dict, status_id: str) -> list[int]:
        """Upsert data into database

        :param data: data to upsert
        :type data: dict
        :param status_id: status_id to match against
        :type status_id: str
        :return: list of updated doc_ids
        :rtype: list[int]
        """
        logging.debug(
            'Upserting into table "%s" for status_id "%s" with data: %s',
            self.table_name,
            status_id,
            data,
        )
        return self.table.upsert(data, where("twitter").status_id == status_id)

    def check_upload(self, status_id: str) -> dict:
        """Check if documents exist where key has value of val

        :param status_id: twitter status id to check if uploaded already
        :type status_id: str
        :return: dict of value matches
        :rtype: dict
        """
        logging.debug(
            'Searching for docs in table "%s" for status_id "%s"',
            self.table_name,
            status_id,
        )
        result = self.table.search(where("twitter").status_id == status_id)
        return result[0] if result else None

    def increment_number(self) -> int:
        """Incrament current comic number by one

        :return: increased number
        :rtype: int
        """
        self.meta.update(increment("number"), doc_ids=[self.number_id])
        return self.get_settings()["number"]
