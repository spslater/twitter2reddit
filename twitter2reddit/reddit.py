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

    def upload(self, subreddit_name: str, post: dict) -> tuple[str, str]:
        """Upload a post to reddit

        :param subreddit_name: subreddit name to upload to
        :type subreddit_name: str
        :param post: info for upload
        :type post: dict
        :return: post url and comment url
        :rtype: tuple[str, str]
        """
        link = post["url"]
        title = post["title"]
        post_url= post.get("post")
        comment_url = post.get("com")
        subreddit = self.api.subreddit(subreddit_name)

        comment_text = (
            f"{post['name']} (@{post['user']})\n{post['raw']}\n\n{post['tweet']}\n\n&nbsp;\n"
            "\n^(I am a bot developed by /u/spsseano. My source code can "
            "be found at https://github.com/spslater/twitter2reddit)"
        )

        if not post_url:
            logging.info(
                'Submitting Reddit link to subreddit "%s" for images "%s"',
                subreddit_name,
                link,
            )
            submission = subreddit.submit(title=title, url=link)
            submission.disable_inbox_replies()
            post_url = submission.permalink
            info = submission.reply(comment_text)
            comment_url = info.permalink
        elif not comment_url:
            logging.info("Already submitted Reddit link leaving comment: %s", post_url)
            submission = self.api.get(post_url)
            info = submission.reply(comment_text)
            comment_url = info.permalink
        else:
            logging.info(
                "Already submitted Reddit link and commented: %s - %s",
                post_url,
                comment_url,
            )
        return post_url, comment_url
