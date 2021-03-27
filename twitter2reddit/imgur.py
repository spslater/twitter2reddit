"""
Upload images to Imgur

Classes:
    ImgurAlbum
    ImgurImages
"""
import logging


class ImgurAlbum:
    """
    Imgur Album Interface
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self, deletehash=None, aid=None, title=None, desc=None, privacy="hidden"
    ):
        self.deletehash = deletehash
        self.aid = aid
        self.url = self.form_url(aid) if aid else None
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
    def form_url(album_id):
        """
        Get album url
        """
        return f"https://imgur.com/a/{album_id}"

    def create(self, client):
        """
        Create new album if it doesn't exist
        """
        if not self.deletehash:
            logging.info("Creating new imgur album with config: %s", self.config)
            album = client.create_album(self.config)
            self.deletehash = album["deletehash"]
            self.aid = album["id"]
            self.url = self.form_url(self.aid)
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
            self.url = self.form_url(self.aid)
        else:
            logging.info(
                'Imgur album does not need to be created, it already exists with deletehash "%s"',
                self.deletehash,
            )
            if not self.url:
                self.url = self.form_url(self.aid)
        return self.deletehash

    def add(self, client, img_ids):
        """
        Add images to an album
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


class ImgurImages:
    """
    Imgur Image Interface
    """

    def __init__(self, tweet, number, album=None):
        self.name = tweet.name
        self.screen_name = tweet.screen_name
        self.body = tweet.text
        self.url = tweet.url
        self.date = tweet.date
        self.media = tweet.media
        self.album = album.deletehash if album else None
        self.number = number
        self.imgs = []
        logging.debug(
            "Generated new imgur images from tweet %s and putting it in album %s",
            tweet.sid,
            self.album,
        )

    def gen_config(self, album, idx=-1):
        """
        Generate the upload info for the image
        """
        logging.debug('Generating imgur image upload config for album "%s"', album)
        title = None
        desc = None
        if idx >= 0:
            title = (
                f"#{self.number} - {self.body} - @{self.screen_name} "
                f"- {idx+1} of {len(self.media)}"
            )
            desc = (
                f"{self.name} (@{self.screen_name}) - {idx+1} of "
                f"{len(self.media)}\n#{self.number} - {self.body}"
                f"\n\nCreated: {self.date}\t{self.url}"
            )
        else:
            title = f"#{self.number} - {self.body} - @{self.screen_name}"
            desc = (
                f"{self.name} (@{self.screen_name})\n#{self.number} - "
                f"{self.body}\n\nCreated: {self.date}\t{self.url}"
            )

        return {
            "album": album,
            "name": title,
            "title": title,
            "description": desc,
        }

    def upload(self, client):
        """
        Upload image to Imgur
        """
        logging.info('Uploading %d images to album "%s"', len(self.media), self.album)
        for i, entry in enumerate(self.media):
            cfg = (
                self.gen_config(album=self.album, idx=i)
                if len(self.media) > 1
                else self.gen_config(album=self.album)
            )
            ret = client.upload_from_url(entry, config=cfg, anon=False)
            self.imgs.append(ret["id"])
        return self.imgs
