"""
Manage twitter statuses

Classes:
    TwitterStatus
"""
import logging
import re
from datetime import datetime


class TweetStatus:
    """
    Access Twitter Status info easily
    """

    def __init__(self, status):
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
    def clean_text(text):
        """
        Remove the image short url from the text of the status
        """
        return re.sub(r"\s+https://t.co/.*?$", "", text)

    @staticmethod
    def media_url(media):
        """
        Get the url for the image in the tweet
        """
        size = "?name=large" if "large" in media.sizes else ""
        return f"{media.media_url_https}{size}"

    @staticmethod
    def tweet_url(screen_name, sid):
        """
        Craft a full URL for status
        """
        return f"https://twitter.com/{screen_name}/status/{sid}"
