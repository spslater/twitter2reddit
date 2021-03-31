"""
Upload images from twitter status to a subreddit

Classes:
    TwitterToReddit
"""
import logging
from os import getenv

from imgurpython import ImgurClient
from praw import Reddit

from .database import Database
from .imgur import ImgurApiClient
from .reddit import RedditPost
from .twitter import TwitterApiClient, TweetStatus


class TwitterToReddit:
    """Sending a twitter status to reddit"""

    def __init__(self, settings: dict):
        self.twitter = TwitterApiClient()
        self.imgur = ImgurApiClient(all_uploads=settings)
        self.reddit = self.get_reddit()

        self.database = Database(filename=settings["database"], table=settings["table"])
        self.number = self.database.get_number()

        self.user = settings["user"]
        self.subreddit = settings["subreddit"]

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

    @staticmethod
    def get_reddit():
        """Get a reddit api client

        :return: reddit api client
        :rtype: Reddit
        """
        logging.debug("Generating Reddit Client")
        return Reddit(
            client_id=getenv("REDDIT_CLIENT_ID"),
            client_secret=getenv("REDDIT_CLIENT_SECRET"),
            username=getenv("REDDIT_USERNAME"),
            password=getenv("REDDIT_PASSWORD"),
            user_agent=getenv("REDDIT_USER_AGENT"),
        )

    def get_statuses(self) -> tuple[list[TweetStatus], list[TweetStatus]]:
        """Get recent twitter statuses
        """
        logging.info("Getting recent statuses from Twitter for @%s", self.user)
        statuses = self.twitter.get_recent_statuses(user=self.user)
        unchecked = []
        partial = []
        for status in statuses:
            if status.media:
                doc = self.database.check_upload("sid", status.sid)
                if doc and doc[0]["post"] is None:
                    partial.append(status)
                elif not doc:
                    unchecked.append(status)
        return unchecked, partial

    def to_imgur(self, statuses):
        """Upload twitter images to imgur
        """
        logging.info("Uploaded %d tweet images to imgur", len(statuses))
        post_urls = []
        for status in statuses:
            db_entry = {
                "sid": status.sid,
                "name": status.name,
                "user": status.screen_name,
                "tweet": status.url,
                "raw": status.text,
                "album": self.imgur.album.deletehash,
                "aid": self.imgur.album.aid,
                "number": self.number,
                "title": None,
                "imgs": None,
                "url": None,
                "post": None,
            }
            imgs = self.imgur.upload_image(status, self.number)
            db_entry["imgs"] = imgs
            db_entry["title"] = f"#{self.number} - {status.text}"
            db_entry["url"] = f"https://i.imgur.com/{imgs}.jpg"
            self.database.upsert(db_entry, "sid", status.sid)
            post_urls.append(db_entry)
            self.number = self.database.increment_number()
        return post_urls

    def already_uploaded(self, statuses):
        """Find statuses that have alread been uploaded to imgur
        """
        sids = [s.sid for s in statuses]
        return self.database.get_docs("sid", sids)

    def to_reddit(self, posts):
        """Upload imgur links to reddit
        """
        logging.info("Posting %d imgur links to /r/%s", len(posts), self.subreddit)
        post_urls = []
        for post in posts:
            sid = post["sid"]
            link = post["url"]
            title = post["title"]
            red = post.get("post")
            com = post.get("com")

            sub = self.reddit.subreddit(self.subreddit)
            res, com = RedditPost(
                subreddit=sub, link=link, title=title, post=red, com=com
            ).upload(post)

            if res is None and com is None:
                logging.warning("Reddit posting not successful.")
            else:
                self.database.upsert(
                    {"post": res, "url": link, "comment": com}, "sid", sid
                )
                post_urls.append(res)
                logging.info("Reddit Post: %s", res)
        return post_urls

    def upload(self) -> list[str]:
        """Get twitter statuses and upload to reddit
        """
        logging.info(
            "Starting recent status uploads from @%s to post on /r/%s",
            self.user,
            self.subreddit,
        )
        unchecked, partial = self.get_statuses()
        if len(unchecked) == 0 and len(partial) == 0:
            logging.info("No new posts need to be made")
            return None
        uploaded = self.to_imgur(unchecked)
        posts = self.to_reddit(uploaded)
        partial_imgur = self.already_uploaded(partial)
        partial_posts = self.to_reddit(partial_imgur)
        posts.extend(partial_posts)
        logging.info(
            "Successfully made %d new posts to /r/%s from @%s",
            len(posts),
            self.subreddit,
            self.user,
        )
        logging.debug("New posts on /r/%s: %s", self.subreddit, posts)
        return posts
