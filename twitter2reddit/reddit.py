"""
Post tweets to Reddit

Classes:
    RedditPost
"""
import logging
from os import getenv

from praw import Reddit


class RedditApiClient:
    """Reddit Api Client"""

    def __init__(self):
        self.api = self.get_client()

    @staticmethod
    def get_client():
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

    @staticmethod
    def _get_comment_text(document: dict) -> str:
        """Generate the comment to leave on a new submission

        :param document: dictionary containting information about twitter user
        :type document: dict
        :return: comment text
        :rtype: str
        """
        display_name = document["twitter"]["display_name"]
        user_name = document["twitter"]["user_name"]
        text = document["twitter"]["text"]
        tweet = document["twitter"]["tweet"]

        return (
            f"{display_name} (@{user_name})\n{text}\n\n{tweet}"
            "\n\n&nbsp;\n\n^(I am a bot developed by /u/spsseano. My source code can "
            "be found at https://github.com/spslater/twitter2reddit)"
        )

    def upload(self, subreddit_name: str, document: dict) -> tuple[str, str]:
        """Upload a post to reddit

        :param subreddit_name: subreddit name to upload to
        :type subreddit_name: str
        :param document: info for upload
        :type document: dict
        :return: updated document with submission url and comment url
        :rtype: dict
        """
        image_link = document["imgur"]["direct_link"]
        title = document["comic"]["title"]
        post_url = document["reddit"].get("post")
        comment_url = document["reddit"].get("comment")
        subreddit = self.api.subreddit(subreddit_name)
        comment_text = self._get_comment_text(document)

        if not post_url:
            logging.info(
                'Submitting Reddit link to subreddit "%s" for images "%s"',
                subreddit_name,
                image_link,
            )
            submission = subreddit.submit(title=title, url=image_link)
            submission.disable_inbox_replies()
            document["reddit"]["post"] = submission.permalink
            info = submission.reply(comment_text)
            document["reddit"]["comment"] = info.permalink
        elif not comment_url:
            logging.info("Already submitted Reddit link leaving comment: %s", post_url)
            submission = self.api.get(post_url)
            info = submission.reply(comment_text)
            document["reddit"]["comment"] = info.permalink
        else:
            logging.info(
                "Already submitted Reddit link and commented: %s - %s",
                post_url,
                comment_url,
            )
        return document
