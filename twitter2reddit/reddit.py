"""
Post tweets to Reddit

Classes:
    RedditPost
"""
import logging


class RedditPost:
    """Reddit Interface"""

    # pylint: disable=too-many-arguments
    def __init__(self, subreddit, link, title, post, com):
        self.subreddit = subreddit
        self.link = link
        self.title = title
        self.post = post
        self.com = com
        self.ret = None

    def upload(self, doc: dict) -> tuple[str, str]:
        """Upload image to reddit

        :param doc: contains info for comment
        :type doc: dict
        :return: direct url for post and comment
        :rtype: tuple[str, str]
        """
        comment_text = (
            f"{doc['name']} (@{doc['user']})\n{doc['raw']}\n\n{doc['tweet']}\n\n&nbsp;\n"
            "\n^(I am a bot developed by /u/spsseano. My source code can "
            "be found at https://github.com/spslater/twitter2reddit)"
        )

        if not self.post:
            logging.info(
                'Submitting Reddit link to subreddit "%s" for images "%s"',
                self.subreddit,
                self.link,
            )
            self.ret = self.subreddit.submit(title=self.title, url=self.link)
            self.ret.disable_inbox_replies()
            self.post = self.ret.permalink
            info = self.ret.reply(comment_text)
            self.com = info.permalink
        elif not self.com:
            logging.info("Already submitted Reddit link leaving comment: %s", self.post)
            info = self.ret.reply(comment_text)
            self.com = info.permalink
        else:
            logging.info(
                "Already submitted Reddit link and commented: %s - %s",
                self.post,
                self.com,
            )
        return self.post, self.com
