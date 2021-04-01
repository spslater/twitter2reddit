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

    def __init__(self, filename: str, table: str) -> None:
        self.table_name = table
        self.database = TinyDB(filename, storage=PrettyJSONStorage)
        self.table = self.database.table(self.table_name)
        self.meta = self.database.table("meta")
        self.number_id = None

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
