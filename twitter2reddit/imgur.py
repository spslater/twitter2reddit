"""
Upload images to Imgur

Classes:
    ImgurAlbum
    ImgurImage
"""
import logging
from os import getenv

from imgurpython import ImgurClient

from .twitter import TweetStatus


class ImgurAlbum:
    """Imgur Album Interface"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        deletehash: str = None,
        aid: str = None,
        title: str = None,
        desc: str = None,
        privacy: str = "hidden",
    ):
        self.deletehash = deletehash
        self.aid = aid
        self.url = self._get_url(aid) if aid else None
        self.config = {
            "title": title,
            "description": desc,
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

    @staticmethod
    def _get_url(album_id: str) -> str:
        """Get album url

        :param album_id: imgur album id, different from deletehash
        :type album_id: str
        :return: url for the album
        :rtype: str
        """
        return f"https://imgur.com/a/{album_id}"

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
            self.aid = album["id"]
            self.url = self._get_url(self.aid)
            logging.info(
                'New album created with deletehash "%s" and aid "%s"',
                self.deletehash,
                self.aid,
            )
        elif not self.aid:
            logging.info(
                "Getting album id and url for album with deletehash: %s",
                self.deletehash,
            )
            self.aid = client.get_album(self.deletehash)
            self.url = self._get_url(self.aid)
        else:
            logging.info(
                'Imgur album does not need to be created, it already exists with deletehash "%s"',
                self.deletehash,
            )
            if not self.url:
                self.url = self._get_url(self.aid)
        return self.deletehash

    def add(self, client: ImgurClient, img_ids: list[int]) -> dict:
        """Add images to an album

        :param client: Imgur Client
        :type client: ImgurClient
        :param img_ids: list of image ids
        :type img_ids: list[int]
        :return: upload response
        :rtype: dict
        """
        logging.info(
            'Adding %d ids to album with deletehash "%s": %s',
            len(img_ids),
            self.deletehash,
            img_ids,
        )
        if not self.deletehash:
            logging.debug("Creating album to add imgs to.")
            self.create(client)
        return client.album_add_images(self.deletehash, img_ids)


class ImgurImage:
    """Imgur Image Interface"""

    def __init__(self, status: TweetStatus, album: ImgurAlbum = None):
        self.status = status
        self.album = album.deletehash if album else None
        self.number = status.number
        self.imgs = None
        logging.debug(
            "Generated new imgur images from tweet %s and putting it in album %s",
            self.status.sid,
            self.album,
        )

    def gen_config(self, album: str) -> dict:
        """Generate the upload info for the image

        :param album: album deletehash
        :type album: str
        :return: upload config info
        :rtype: dict
        """
        logging.debug('Generating imgur image upload config for album "%s"', album)
        title = (
            f"#{self.status.number} - {self.status.text} - @{self.status.screen_name}"
        )
        desc = (
            f"{self.status.name} (@{self.status.screen_name})\n#{self.status.number} - "
            f"{self.status.text}\n\nCreated: {self.status.date}\t{self.status.url}"
        )

        return {
            "album": album,
            "name": title,
            "title": title,
            "description": desc,
        }

    def upload(self, client: ImgurClient) -> list[int]:
        """Upload images to Imgur

        :param client: imgur api client
        :type client: ImgurClient
        :return: list of uplaoded image ids
        :rtype: list[int]
        """
        if self.imgs is None:
            logging.info('Uploading image to album "%s"', self.album)
            cfg = self.gen_config(album=self.album)
            ret = client.upload_from_url(self.status.media, config=cfg, anon=False)
            self.imgs = ret["id"]
        else:
            logging.info(
                'Image already uploaded to album "%s" with id "%s"',
                self.album,
                self.imgs,
            )
        return self.imgs


class ImgurApiClient:
    """Imgur Api Client"""

    def __init__(self, all_uploads: dict = None):
        self.api = self.get_imgur()
        if all_uploads:
            self.create_album(
                deletehash=all_uploads.get("all_hash"),
                name=all_uploads.get("all_name"),
                title=all_uploads.get("all_title"),
                url=all_uploads.get("all_url"),
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
        name: str,
        title: str,
        url: str,
        deletehash: str = None,
        all_album: bool = False,
    ) -> ImgurAlbum:
        """Create a new Imgur album

        :param name: user name of twitter user
        :type name: str
        :param title: title for image series
        :type title: str
        :param url: source url
        :type url: str
        :param deletehash: deletehash of imgur album
        :type deletehash: str
        :param all_album: set this album as an album for all uploads
        :type all_album: bool
        :return: newly created album
        :rtype: ImgurAlbum
        """
        album = ImgurAlbum(
            deletehash=deletehash,
            title=f"@{name} - {title}",
            desc=f"{title} art by @{name} - {url}",
        ).create(self.api)
        if all_album:
            logging.debug('Setting "%s" as the all album', album.deletehash)
            self.album = album
        return album

    def upload_image(self, status: TweetStatus) -> int:
        """Upload first image from a tweet

        :param status: tweet to get media from
        :type status: TweetStatus
        :return: imgur image id
        :rtype: int
        """
        return ImgurImage(status, self.album).upload(self.api)
