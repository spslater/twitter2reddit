"""
Upload images from twitter status to a subreddit

Classes:
    TwitterToReddit
"""
import logging
from os import getenv

from imgurpython import ImgurClient
from praw import Reddit
from twitter import Api as Twitter

from .database import Database
from .imgur import ImgurAlbum, ImgurImages
from .reddit import RedditPost
from .twitter import TweetStatus


class TwitterToReddit:
    """Sending a twitter status to reddit"""

    def __init__(
        self,
        settings: dict,
        twitter_client: Twitter = None,
        imgur_client: ImgurClient = None,
        reddit_client: Reddit = None,
    ):
        self.twitter = twitter_client if twitter_client else self.get_twitter()
        self.imgur = imgur_client if imgur_client else self.get_imgur()
        self.reddit = reddit_client if reddit_client else self.get_reddit()

        self.database = Database(filename=settings["database"], table=settings["table"])
        self.number = self.database.get_number()

        self.user = settings["user"]
        self.all_album = ImgurAlbum(
            deletehash=settings["all_hash"],
            title=settings["all_name"],
            desc=settings["all_desc"],
        )
        if not settings["all_hash"]:
            self.all_album.create(self.imgur)
            logging.info(
                'No hash given for imgur album. New album created with hash id "%s" and aid "%s"',
                self.all_album.deletehash,
                self.all_album.aid,
            )
        self.subreddit = settings["subreddit"]

    @staticmethod
    def get_twitter() -> Twitter:
        """Get a twitter api client

        :return: twitter api client
        :rtype: Twitter
        """
        logging.debug("Generating Twitter Client")
        return Twitter(
            consumer_key=getenv("TWITTER_CONSUMER_KEY"),
            consumer_secret=getenv("TWITTER_CONSUMER_SECRET"),
            access_token_key=getenv("TWITTER_ACCESS_TOKEN_KEY"),
            access_token_secret=getenv("TWITTER_ACCESS_TOKEN_SECRET"),
            request_headers={
                "Authorization": "Bearer {}".format(getenv("TWITTER_BEARER_TOKEN"))
            },
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

    def single_album(self, tweet):
        """Create a single imgur album
        """
        logging.debug(
            (
                'Generating ImgurAlbum for single tweet "%s" from '
                "@%s with multiple media files"
            ),
            tweet.sid,
            tweet.name,
        )
        return ImgurAlbum(
            title=f"@{tweet.name} - {tweet.text}",
            desc=f"Images from @{tweet.name} at {tweet.url}",
        ).create(self.imgur)

    def get_statuses(self):
        """Get recent twitter statuses
        """
        logging.info("Getting recent statuses from Twitter for @%s", self.user)
        statuses = self.twitter.GetUserTimeline(
            screen_name=self.user, exclude_replies=True, include_rts=False
        )
        unchecked = []
        partial = []
        for status in statuses:
            if status.media:
                doc = self.database.check_upload("sid", status.id)
                if doc and doc[0]["post"] is None:
                    partial.append(status)
                elif not doc:
                    unchecked.append(status)
        return [TweetStatus(s) for s in unchecked], [TweetStatus(s) for s in partial]

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
                "title": None,
                "imgs": [],
                "url": None,
                "album": None,
                "aid": None,
                "post": None,
                "number": self.number,
            }
            imgs = ImgurImages(status, self.number).upload(self.imgur)
            db_entry["imgs"] = imgs
            db_entry["title"] = f"#{self.number} - {status.text}"
            url = f"https://i.imgur.com/{imgs[0]}.jpg"
            self.all_album.add(self.imgur, imgs)
            if len(status.media) > 1:
                album = self.single_album(status)
                album.add(self.imgur, imgs)
                db_entry["album"] = album.deletehash
                db_entry["aid"] = album.aid
                url = album.url(self.imgur)
            elif len(status.media) == 1:
                db_entry["album"] = self.all_album.deletehash
                db_entry["aid"] = self.all_album.aid
            db_entry["url"] = url
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

    def upload(self):
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
