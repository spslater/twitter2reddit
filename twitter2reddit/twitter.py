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
from twitter.models import Media


class TwitterApiClient:
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
                "Authorization": f"Bearer {getenv('TWITTER_BEARER_TOKEN')}"
            },
        )

    @staticmethod
    def _media_url(media: Media) -> str:
        """Get the url for the image in the tweet

        :param media: twitter media object with image info
        :type media: Media
        :return: direct url for the image
        :rtype: str
        """
        size = "?name=large" if "large" in media.sizes else ""
        return f"{media.media_url_https}{size}"

    def _convert_status(self, status):
        return {
            "twitter": {
                "status_id": status.id,
                "date": datetime.fromtimestamp(status.created_at_in_seconds).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "user_name": status.user.screen_name,
                "display_name": status.user.name,
                "tweet": f"https://twitter.com/{status.user.screen_name}/status/{status.id}",
                "text": re.sub(r"\s+https://t.co/.*?$", "", status.text),
                "media": self._media_url(status.media[0]) if status.media else None,
            }
        }

    def get_recent_statuses(self, user_name: str, recent: int = 15) -> list[dict]:
        """Get most recent tweets from user

        :param user_name: twitter @ username
        :type user_name: str
        :param recent: number of recent tweet statuses to get, defaults to 15
        :type recent: int, optional
        :return: list of recent statuses
        :rtype: list[dict]
        """
        statuses = self.api.GetUserTimeline(
            screen_name=user_name, count=recent, exclude_replies=True, include_rts=False
        )
        return reversed([self._convert_status(status) for status in statuses if status.media])
