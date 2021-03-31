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
        self.number_id = None

    def upsert(self, data: dict, key: str, val: object) -> list[int]:
        """Upsert data into database

        Will match all instances where `val` is equal (==) and update all
            of those docs.

        :param data: data to upsert
        :type data: dict
        :param key: key to match value against
        :type key: str
        :param val: value that key should match to update
        :type val: object
        :return: list of updated doc_ids
        :rtype: list[int]
        """
        logging.debug(
            'Upserting into table "%s" where "%s" == "%s" with data: %s',
            self.table_name,
            key,
            val,
            data,
        )
        return self.table.upsert(data, where(key) == val)

    def check_upload(self, key: str, val: object) -> dict:
        """Check if documents exist where key has value of val

        :param key: key to match value against
        :type key: str
        :param val: value that key should match
        :type val: object
        :return: dict of value matches
        :rtype: dict
        """
        logging.debug(
            'Searching for docs in table "%s" where "%s" == "%s"',
            self.table_name,
            key,
            val,
        )
        return self.table.search(where(key) == val)[0]

    def get_number(self) -> int:
        """Get current comic number

        :return: current image number
        :rtype: int
        """
        if self.number_id is None:
            # pylint: disable=singleton-comparison
            results = self.table.search(where("number_counter") == True)
            self.number_id = results[0].doc_id
        return self.table.get(doc_id=self.number_id)["number"]

    def increment_number(self) -> int:
        """Incrament current comic number by one

        :return: increased number
        :rtype: int
        """
        self.table.update(increment("number"), doc_ids=[self.number_id])
        return self.get_number()
