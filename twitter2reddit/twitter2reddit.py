"""
Upload images from twitter status to a subreddit

Classes:
    TwitterToReddit
"""
import logging

from .database import Database
from .imgur import ImgurApiClient
from .reddit import RedditApiClient
from .twitter import TwitterApiClient, TweetStatus


class TwitterToReddit:
    """Sending a twitter status to reddit"""

    def __init__(self, settings: dict):
        self.twitter = TwitterApiClient()
        self.imgur = ImgurApiClient(all_uploads=settings)
        self.reddit = RedditApiClient()

        self.database = Database(filename=settings["database"], table=settings["table"])
        self.number = self.database.get_number()

        self.user = settings["user"]
        self.subreddit = settings["subreddit"]

    def get_statuses(self) -> tuple[list[TweetStatus], list[TweetStatus]]:
        """Get recent twitter statuses"""
        logging.info("Getting recent statuses from Twitter for @%s", self.user)
        statuses = self.twitter.get_recent_statuses(user=self.user)
        partial = []
        unchecked = []
        for status in statuses:
            if status.media:
                db_entry = {
                    "sid": status.sid,
                    "name": status.name,
                    "user": status.screen_name,
                    "tweet": status.url,
                    "raw": status.text,
                }
                doc = self.database.check_upload("sid", db_entry["sid"])
                if doc and doc["post"] is None:
                    partial.append(doc)
                else:
                    self.database.upsert(db_entry, "sid", db_entry["sid"])
                    unchecked.append(db_entry)
        return partial, unchecked

    def to_imgur(self, statuses):
        """Upload twitter images to imgur"""
        logging.info("Uploaded %d tweet images to imgur", len(statuses))
        update_statuses = []
        for status in statuses:
            status.update(
                {
                    "album": self.imgur.album.deletehash,
                    "aid": self.imgur.album.aid,
                    "number": self.number,
                    "title": f"#{self.number} - {status['text']}",
                }
            )
            imgs = self.imgur.upload_image(status)
            status["imgs"] = imgs
            status["url"] = f"https://i.imgur.com/{imgs}.jpg"
            self.database.upsert(status, "sid", status["sid"])
            update_statuses.append(status)
            self.number = self.database.increment_number()
        return update_statuses

    def to_reddit(self, posts):
        """Upload imgur links to reddit"""
        logging.info("Posting %d imgur links to /r/%s", len(posts), self.subreddit)
        post_urls = []
        for post in posts:
            res, com = self.reddit.upload(self.subreddit, post)

            if res is None and com is None:
                logging.warning("Reddit posting not successful.")
            else:
                self.database.upsert(
                    {"post": res, "url": post["link"], "comment": com},
                    "sid",
                    post["sid"],
                )
                post_urls.append(res)
                logging.info("Reddit Post: %s", res)
        return post_urls

    def upload(self) -> list[str]:
        """Get twitter statuses and upload to reddit"""
        logging.info(
            "Starting recent status uploads from @%s to post on /r/%s",
            self.user,
            self.subreddit,
        )
        uploaded, unchecked = self.get_statuses()
        if len(unchecked) == 0 and len(uploaded) == 0:
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
