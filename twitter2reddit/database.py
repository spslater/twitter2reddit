"""
TinyDB Interface

Classes:
    Database
"""
import logging
from io import UnsupportedOperation
from json import dumps
from os import fsync
from tinydb import TinyDB, where, JSONStorage, Table
from tinydb.operations import increment

__all__ = "Database"


class PrettyJSONStorage(JSONStorage):
    """
    Store the TinyDB with pretty json

    Should be passed into a TinyDB constructor as the `storage` argument
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, data):
        """
        Write data to database in a pretty json format

        Indents by 4 spaces and sorts keys
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
        self.table = self.database.table(table_name)
        self.number_id = None

    def upsert(self, data: dict, key: str, val: object) -> list[int]:
        """
        Upsert data into database

        Will match all instances where `val` is equal (==) and update all
            of those docs.

        Args:
            data (dict): data to upsert
            key (str): key to match value against
            val (object): value that key should match to update

        Returns:
            doc_ids (list[int]): list of updated doc_ids
        """
        logging.debug(
            'Upserting into table "%s" where "%s" == "%s" with data: %s',
            self.table_name,
            key,
            val,
            data,
        )
        return self.table.upsert(data, where(key) == val)

    def check_upload(self, key: str, val: object) -> list[int]:
        """
        Check if documents exist where key has value of val

        Args:
            key (str): key to match value against
            val (object): value that key should match

        Returns:
            doc_ids (list[int]): list of doc_ids where value matches
        """
        logging.debug(
            'Searching for docs in table "%s" where "%s" == "%s"',
            self.table_name,
            key,
            val,
        )
        return self.table.search(where(key) == val)

    def get_docs(self, key: str, vals: list[object]) -> list[dict]:
        """
        Get documents where key equals vals

        Args:
            key (str): key to match value against
            vals (list[object]): list of values that key can match

        Returns:
            docs (list[dict]): list of docs where value matches
        """
        docs = []
        for val in vals:
            ret = self.table.search(where(key) == val)
            if ret:
                docs.extend(ret)
        return docs

    def get_number(self) -> int:
        """
        Get current comic number

        Args:
            None

        Returns:
            number (int): current image number
        """
        if self.number_id is None:
            # pylint: disable=singleton-comparison
            results = self.table.search(where("number_counter") == True)
            self.number_id = results[0].doc_id
        return self.table.get(doc_id=self.number_id)["number"]

    def increment_number(self) -> int:
        """
        Incrament current comic number by one

        Args:
            None

        Returns:
            number (int): increased number
        """
        self.table.update(increment("number"), doc_ids=[self.number_id])
        return self.get_number()
