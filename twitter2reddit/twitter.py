"""
Manage twitter statuses

Classes:
    TwitterStatus
"""
import logging
import re
from datetime import datetime
from os import getenv

from twitter import Api as Twitter
from twitter.models import Media, Status


class TwitterClient:
    """Twitter API Client"""

    def __init__(self):
        self.api = self.get_client()

    @staticmethod
    def get_client() -> Twitter:
        """Get a twitter api client

        Gets the values from the environment

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

    def get_recent_statuses(self, user: str, recent: int = 15) -> list[TweetStatus]:
        """Get most recent tweets from user

        :param user: twitter @ username
        :type user: str
        :param recent: number of recent tweet statuses to get, defaults to 15
        :type recent: int, optional
        :return: list of recent statuses
        :rtype: list[TweetStatus]
        """
        statuses = self.api.GetUserTimeline(
            screen_name=user, count=recent, exclude_replies=True, include_rts=False
        )
        return [TweetStatus(status) for status in statuses]

class TweetStatus:
    """Access Twitter Status info easily"""

    def __init__(self, status: Status):
        self.sid = status.id
        self.date = datetime.fromtimestamp(status.created_at_in_seconds).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.screen_name = status.user.screen_name
        self.name = status.user.name
        self.url = self.tweet_url(self.screen_name, status.id)
        self.text = self.clean_text(status.text)
        self.media = [self.media_url(m) for m in status.media]
        logging.debug("Generated TweetStatus for tweet %s", self.sid)

    @staticmethod
    def clean_text(text: str) -> str:
        """Remove the image short url from the text of the status

        :param text: body text of tweet
        :type text: str
        :return: text of tweet without link to media
        :rtype: str
        """
        return re.sub(r"\s+https://t.co/.*?$", "", text)

    @staticmethod
    def media_url(media: Media) -> str:
        """Get the url for the image in the tweet

        :param media: twitter media object with image info
        :type media: Media
        :return: direct url for the image
        :rtype: str
        """
        size = "?name=large" if "large" in media.sizes else ""
        return f"{media.media_url_https}{size}"

    @staticmethod
    def tweet_url(screen_name: str, sid: int):
        """Craft a full URL for status

        :param screen_name: [description]
        :type screen_name: str
        :param sid: [description]
        :type sid: int
        :return: [description]
        :rtype: str
        """
        return f"https://twitter.com/{screen_name}/status/{sid}"
