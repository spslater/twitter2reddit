"""
Upload images to Imgur

Classes:
    ImgurAlbum
    ImgurImage
"""
import logging
from os import getenv

from imgurpython import ImgurClient


class ImgurAlbum:
    """Imgur Album Interface"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        deletehash: str = None,
        album_id: str = None,
        title: str = None,
        description: str = None,
        privacy: str = "hidden",
    ):
        self.deletehash = deletehash
        self.album_id = album_id
        self.config = {
            "title": title,
            "description": description,
            "privacy": privacy,
        }
        if self.deletehash:
            logging.debug(
                'Generated ImgurAlbum for album with deletehash "%s"', self.deletehash
            )
        else:
            logging.debug(
                'Generated ImgurAlbum for album with title "%s", no deletehash provided',
                self.config["title"],
            )

    def create(self, client: ImgurClient) -> str:
        """Create new album if it doesn't exist

        :param client: imgur api client
        :type client: ImgurClient
        :return: deletehash of album being uploaded to
        :rtype: str
        """
        if not self.deletehash:
            logging.info("Creating new imgur album with config: %s", self.config)
            album = client.create_album(self.config)
            self.deletehash = album["deletehash"]
            self.album_id = album["id"]
            logging.info(
                'New album created with deletehash "%s" and album_id "%s"',
                self.deletehash,
                self.album_id,
            )
        else:
            logging.info(
                'Imgur album does not need to be created, it already exists with deletehash "%s"',
                self.deletehash,
            )
        return self.deletehash

    def add(self, client: ImgurClient, image_ids: list[int]) -> dict:
        """Add images to an album

        :param client: Imgur Client
        :type client: ImgurClient
        :param image_ids: list of image ids
        :type image_ids: list[int]
        :return: upload response
        :rtype: dict
        """
        logging.info(
            'Adding %d ids to album with deletehash "%s": %s',
            len(image_ids),
            self.deletehash,
            image_ids,
        )
        if not self.deletehash:
            logging.debug("Creating album to add imgs to.")
            self.create(client)
        return client.album_add_images(self.deletehash, image_ids)


class ImgurImage:
    """Imgur Image Interface"""

    def __init__(self, status: dict, deletehash: str = None):
        self.status = status
        self.deletehash = deletehash
        self.image_id = None
        logging.debug(
            "Generated new imgur images from tweet %s and putting it in album %s",
            self.status["twitter"]["status_id"],
            self.deletehash,
        )

    def gen_config(self) -> dict:
        """Generate the upload info for the image

        :return: upload config info
        :rtype: dict
        """
        logging.debug(
            'Generating imgur image upload config for album "%s"', self.deletehash
        )
        twitter = self.status["twitter"]
        comic = self.status["comic"]

        title = (
            f"#{comic['number']} - {twitter['text']} - @{twitter['user_name']}"
        )
        description = (
            f"{twitter['display_name']} (@{twitter['user_name']})\n#{comic['number']} - "
            f"{twitter['text']}\n\nCreated: {twitter['date']}\t{twitter['tweet']}"
        )

        return {
            "album": self.deletehash,
            "name": title,
            "title": title,
            "description": description,
        }

    def upload(self, client: ImgurClient) -> list[int]:
        """Upload images to Imgur

        :param client: imgur api client
        :type client: ImgurClient
        :return: list of uplaoded image ids
        :rtype: list[int]
        """
        if self.image_id is None:
            logging.info('Uploading image to album "%s"', self.deletehash)
            print(self.status["twitter"]["media"], self.gen_config())
            ret = client.upload_from_url(
                self.status["twitter"]["media"], config=self.gen_config(), anon=False
            )
            self.image_id = ret["id"]
        else:
            logging.info(
                'Image already uploaded to album "%s" with id "%s"',
                self.deletehash,
                self.image_id,
            )
        return self.image_id


class ImgurApiClient:
    """Imgur Api Client"""

    def __init__(self, settings: dict = None):
        self.api = self.get_imgur()
        self.album = None
        if settings:
            self.album = self.create_album(
                deletehash=settings["imgur"].get("deletehash"),
                album_id=settings["imgur"].get("album_id"),
                title=settings["imgur"].get("title"),
                user_name=settings["twitter"].get("user_name"),
                user_url=settings["twitter"].get("user_url"),
            )

    @staticmethod
    def get_imgur() -> ImgurClient:
        """Get an imgur api client

        :return: imgur api client
        :rtype: ImgurClient
        """
        logging.debug("Generating Imgur Client")
        return ImgurClient(
            client_id=getenv("IMGUR_CLIENT"),
            client_secret=getenv("IMGUR_SECRET"),
            access_token=getenv("IMGUR_ACCESS_TOKEN"),
            refresh_token=getenv("IMGUR_REFRESH_TOKEN"),
        )

    # pylint: disable=too-many-arguments
    def create_album(
        self,
        user_name: str,
        title: str,
        user_url: str,
        deletehash: str = None,
        album_id: str = None,
        all_album: bool = False,
    ) -> ImgurAlbum:
        """Create a new Imgur album

        :param user_name: user name of twitter user
        :type user_name: str
        :param title: title for image series
        :type title: str
        :param user_url: source url
        :type user_url: str
        :param deletehash: deletehash of imgur album
        :type deletehash: str
        :param album_id: album id of imgur album
        :type album_id: str
        :param all_album: set this album as an album for all uploads
        :type all_album: bool
        :return: newly created album
        :rtype: ImgurAlbum
        """
        album = ImgurAlbum(
            deletehash=deletehash,
            album_id=album_id,
            title=f"@{user_name} - {title}",
            description=f"{title} art by @{user_name} - {user_url}",
        )
        album.create(self.api)
        if all_album:
            logging.debug('Setting "%s" as the all album', album.deletehash)
            self.album = album
        return album

    def upload_image(self, status: dict) -> int:
        """Upload first image from a tweet

        :param status: contains info
        :type status: dict
        :return: imgur image id
        :rtype: int
        """
        return ImgurImage(status, self.album.deletehash).upload(self.api)
