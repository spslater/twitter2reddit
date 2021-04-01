"""
Upload images from twitter status to a subreddit

Classes:
    TwitterToReddit
"""
import logging

from .database import Database
from .imgur import ImgurApiClient
from .reddit import RedditApiClient
from .twitter import TwitterApiClient


class TwitterToReddit:
    """Sending a twitter status to reddit"""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, env_settings: dict):
        self.database = Database(
            filename=env_settings["database"],
            table=env_settings["table"],
            first_time=env_settings.get("first_time"),
        )
        self.settings = self.database.get_settings()

        self.twitter = TwitterApiClient()
        self.imgur = ImgurApiClient(settings=self.settings)
        self.reddit = RedditApiClient()

        if self.settings["imgur"]["deletehash"] is None:
            self.settings = self.database.update_meta(
                {
                    "imgur": {
                        "deletehash": self.imgur.album.deletehash,
                        "album_id": self.imgur.album.album_id,
                    }
                }
            )

        self.number = self.settings["number"]

        self.user = self.database.get_settings()["twitter"]["user_name"]
        self.subreddit = self.database.get_settings()["reddit"]["subreddit"]

    def get_statuses(self) -> tuple[list[dict], list[dict]]:
        """Get recent twitter statuses"""
        logging.info("Getting recent statuses from Twitter for @%s", self.user)
        statuses = self.twitter.get_recent_statuses(user_name=self.user)
        partial = []
        unchecked = []
        for status in statuses:
            if status["twitter"]["media"]:
                document = self.database.check_upload(status["twitter"]["status_id"])
                if document is None:
                    status.update({"comic": {}, "imgur": {}, "reddit": {}})
                    self.database.upsert(status, status["twitter"]["status_id"])
                    unchecked.append(status)
                elif document and not document["comic"]:
                    unchecked.append(status)
                elif document and (
                    document["reddit"].get("post") is None
                    or document["reddit"].get("comment") is None
                ):
                    partial.append(document)
                else:
                    logging.debug(
                        'Status "%d" already uploaded to reddit',
                        status["twitter"]["status_id"],
                    )
        return partial, unchecked

    def to_imgur(self, statuses):
        """Upload twitter images to imgur"""
        logging.info("Uploaded %d tweet images to imgur", len(statuses))
        update_statuses = []
        for status in statuses:
            status.update(
                {
                    "imgur": {
                        "deletehash": self.imgur.album.deletehash,
                        "album_id": self.imgur.album.album_id,
                    },
                    "comic": {
                        "number": self.number,
                        "title": f"#{self.number} - {status['twitter']['text']}",
                    },
                }
            )
            image_id = self.imgur.upload_image(status)
            status["imgur"]["image_id"] = image_id
            status["imgur"]["direct_link"] = f"https://i.imgur.com/{image_id}.jpg"
            self.database.upsert(status, status["twitter"]["status_id"])
            update_statuses.append(status)
            self.number = self.database.increment_number()
        return update_statuses

    def to_reddit(self, statuses: list[dict]) -> list[str]:
        """Upload imgur links to reddit

        :param statuses: list of statuses to upload to reddit
        :type statuses: dict
        :return: list of reddit submission urls
        :rtype: list[str]
        """
        logging.info("Posting %d imgur links to /r/%s", len(statuses), self.subreddit)
        posts = []
        for status in statuses:
            status = self.reddit.upload(self.subreddit, status)
            post = status["reddit"]["post"]
            comment = status["reddit"]["comment"]

            if post is None and comment is None:
                logging.warning("Reddit posting not successful.")
            else:
                self.database.upsert(status, status["twitter"]["status_id"])
                posts.append(post)
                logging.info("Reddit Post: %s", post)
        return posts

    def upload(self) -> list[str]:
        """Get twitter statuses and upload to reddit

        :return: list of reddit submission urls
        :rtype: list[str]
        """
        logging.info(
            "Starting recent status uploads from @%s to post on /r/%s",
            self.user,
            self.subreddit,
        )
        uploaded, unchecked = self.get_statuses()
        if not unchecked and not uploaded:
            logging.info("No new posts need to be made")
            return None
        uploaded.extend(self.to_imgur(unchecked))
        posts = self.to_reddit(uploaded)
        logging.info(
            "Successfully made %d new posts to /r/%s from @%s",
            len(posts),
            self.subreddit,
            self.user,
        )
        logging.debug("New posts on /r/%s: %s", self.subreddit, posts)
        return posts
