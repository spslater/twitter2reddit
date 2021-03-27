"""
TinyDB Interface

Classes:
    Database
"""
import logging
from io import UnsupportedOperation
from json import dumps
from os import fsync
from tinydb import TinyDB, where, JSONStorage
from tinydb.operations import increment


class PrettyJSONStorage(JSONStorage):
    """
    Store the TinyDB with pretty json
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, data):
        """
        Write data to database in a pretty format
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
    """

    def __init__(self, filename, table):
        self.table = table
        self.database = TinyDB(filename, storage=PrettyJSONStorage)
        self.table = self.database.table(table)
        self.number_id = None

    def upsert(self, data, key, val):
        """
        Upsert data into database
        """
        logging.debug(
            'Upserting into table "%s" where "%s" == "%s" with data: %s',
            self.table,
            key,
            val,
            data,
        )
        return self.table.upsert(data, where(key) == val)

    def check_upload(self, key, val):
        """
        Doc documents where key has value of val
        """
        logging.debug(
            'Searching for docs in table "%s" where "%s" == "%s"', self.table, key, val
        )
        return self.table.search(where(key) == val)

    def get_docs(self, key, vals):
        """
        Get documents where key equals vals
        """
        docs = []
        for val in vals:
            ret = self.table.search(where(key) == val)
            if ret:
                docs.extend(ret)
        return docs

    def get_number(self):
        """
        Get current comic number
        """
        if self.number_id is None:
            # pylint: disable=singleton-comparison
            results = self.table.search(where("number_counter") == True)
            self.number_id = results[0].doc_id
        return self.table.get(doc_id=self.number_id)["number"]

    def increment_number(self):
        """
        Incrament current comic number by one
        """
        self.table.update(increment("number"), doc_ids=[self.number_id])
        return self.get_number()
