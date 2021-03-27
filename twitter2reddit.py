"""
Upload images from twitter status to a subreddit

Classes:
    TwitterToReddit
"""
import logging
import re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime
from io import UnsupportedOperation
from json import dumps
from os import getenv, fsync
from sys import stdout
from time import sleep
from tinydb import TinyDB, where, JSONStorage
from tinydb.operations import increment
from yaml import load, Loader

from dotenv import load_dotenv
from imgurpython import ImgurClient
from praw import Reddit
from twitter import Api as Twitter


class PrettyJSONStorage(JSONStorage):
    """
    Store the TinyDB with pretty json
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write(self, data):
        """
        Write data to database in a pretty format
        """
        self._handle.seek(0)
        serialized = dumps(data, indent=4, sort_keys=True, **self.kwargs)
        try:
            self._handle.write(serialized)
        except UnsupportedOperation as e:
            raise IOError(
                f'Cannot write to the database. Access mode is "{self._mode}"'
            ) from e

        self._handle.flush()
        fsync(self._handle.fileno())

        self._handle.truncate()


class Database:
    """
    TinyDB interface
    """

    def __init__(self, filename, table):
        self.table = table
        self.database = TinyDB(filename, storage=PrettyJSONStorage)
        self.table = self.database.table(table)
        self.number_id = None

    def upsert(self, data, key, val):
        """
        Upsert data into database
        """
        logging.debug(
            'Upserting into table "%s" where "%s" == "%s" with data: %s',
            self.table,
            key,
            val,
            data,
        )
        return self.table.upsert(data, where(key) == val)

    def check_upload(self, key, val):
        """
        Doc documents where key has value of val
        """
        logging.debug(
            'Searching for docs in table "%s" where "%s" == "%s"', self.table, key, val
        )
        return self.table.search(where(key) == val)

    def get_docs(self, key, vals):
        """
        Get documents where key equals vals
        """
        docs = []
        for val in vals:
            ret = self.table.search(where(key) == val)
            if ret:
                docs.extend(ret)
        return docs

    def get_number(self):
        """
        Get current comic number
        """
        if self.number_id is None:
            self.number_id = self.table.search(where("number_counter"))[0].doc_id
        return self.table.get(doc_id=self.number_id)["number"]

    def increment_number(self):
        """
        Incrament current comic number by one
        """
        self.table.update(increment("number"), doc_ids=[self.number_id])
        return self.get_number()


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


class ImgurAlbum:
    """
    Imgur Album Interface
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self, deletehash=None, aid=None, title=None, desc=None, privacy="hidden"
    ):
        self.deletehash = deletehash
        self.aid = aid
        self.url = self.form_url(aid) if aid else None
        self.config = {
            "title": title,
            "description": desc,
            "privacy": privacy,
        }
        if self.deletehash:
            logging.debug(
                'Generated ImgurAlbum for album with deletehash "%s"', self.deletehash
            )
        else:
            logging.debug(
                'Generated ImgurAlbum for album with title "%s", no deletehash provided',
                self.config["title"],
            )

    @staticmethod
    def form_url(album_id):
        """
        Get album url
        """
        return f"https://imgur.com/a/{album_id}"

    def create(self, client):
        """
        Create new album if it doesn't exist
        """
        if not self.deletehash:
            logging.info("Creating new imgur album with config: %s", self.config)
            album = client.create_album(self.config)
            self.deletehash = album["deletehash"]
            self.aid = album["id"]
            self.url = self.form_url(self.aid)
        elif not self.aid:
            logging.info(
                "Getting album id and url for album with deletehash: %s",
                self.deletehash,
            )
            self.aid = client.get_album(self.deletehash)
            self.url = self.form_url(self.aid)
        else:
            logging.info(
                'Imgur album does not need to be created, it already exists with deletehash "%s"',
                self.deletehash,
            )
            if not self.url:
                self.url = self.form_url(self.aid)
        return self.deletehash

    def add(self, client, img_ids):
        """
        Add images to an album
        """
        logging.info(
            'Adding %d ids to album with deletehash "%s": %s',
            len(img_ids),
            self.deletehash,
            img_ids,
        )
        if not self.deletehash:
            logging.debug("Creating album to add imgs to.")
            self.create(client)
        return client.album_add_images(self.deletehash, img_ids)


class ImgurImages:
    """
    Imgur Image Interface
    """

    def __init__(self, tweet, number, album=None):
        self.name = tweet.name
        self.screen_name = tweet.screen_name
        self.body = tweet.text
        self.url = tweet.url
        self.date = tweet.date
        self.media = tweet.media
        self.album = album.deletehash if album else None
        self.number = number
        self.imgs = []
        logging.debug(
            "Generated new imgur images from tweet %s and putting it in album %s",
            tweet.sid,
            self.album,
        )

    def gen_config(self, album, idx=-1):
        """
        Generate the upload info for the image
        """
        logging.debug('Generating imgur image upload config for album "%s"', album)
        title = None
        desc = None
        if idx >= 0:
            title = f"#{self.number} - {self.body} - @{self.screen_name} \
                - {idx+1} of {len(self.media)}"
            desc = f"{self.name} (@{self.screen_name}) - {idx+1} of \
                {len(self.media)}\n#{self.number} - {self.body}\
                \n\nCreated: {self.date}\t{self.url}"
        else:
            title = f"#{self.number} - {self.body} - @{self.screen_name}"
            desc = "{self.name} (@{self.screen_name})\n#{self.number} - \
                {self.body}\n\nCreated: {self.date}\t{self.url}"

        return {
            "album": album,
            "name": title,
            "title": title,
            "description": desc,
        }

    def upload(self, client):
        """
        Upload image to Imgur
        """
        logging.info('Uploading %d images to album "%s"', len(self.media), self.album)
        for i, entry in enumerate(self.media):
            cfg = (
                self.gen_config(album=self.album, idx=i)
                if len(self.media) > 1
                else self.gen_config(album=self.album)
            )
            ret = client.upload_from_url(entry, config=cfg, anon=False)
            self.imgs.append(ret["id"])
        return self.imgs


class RedditPost:
    """
    Reddit Interface
    """

    # pylint: disable=too-many-arguments
    def __init__(self, subreddit, link, title, post, com):
        self.subreddit = subreddit
        self.link = link
        self.title = title
        self.post = post
        self.com = com
        self.ret = None

    def upload(self, doc):
        """
        Upload image to reddit
        """
        comment_text = "{name} (@{user})\n{body}\n\n{link}\n\n&nbsp;\n\
                \n^(I am a bot developed by /u/spsseano. My source code can \
                be found at https://github.com/spslater/twitter2reddit)".format(
            name=doc["name"], user=doc["user"], body=doc["raw"], link=doc["tweet"]
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


class TwitterToReddit:
    """
    Sending a twitter status to reddit
    """

    def __init__(
        self, settings, twitter_client=None, imgur_client=None, reddit_client=None
    ):
        self.user = settings["user"]
        self.all_album = ImgurAlbum(
            deletehash=settings["all_hash"],
            title=settings["all_name"],
            desc=settings["all_desc"],
        )
        self.subreddit = settings["subreddit"]

        self.twitter = twitter_client if twitter_client else self.get_twitter()
        self.imgur = imgur_client if imgur_client else self.get_imgur()
        self.reddit = reddit_client if reddit_client else self.get_reddit()

        self.database = Database(filename=settings["database"], table=settings["table"])
        self.number = self.database.get_number()

    @staticmethod
    def get_twitter():
        """
        Get a twitter api client
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
    def get_imgur():
        """
        Get a imgur api client
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
        """
        Get a reddit api client
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
        """
        Create a single imgur album
        """
        logging.debug(
            'Generating ImgurAlbum for single tweet "%s" from \
                @%s with multiple media files',
            tweet.sid,
            tweet.name,
        )
        return ImgurAlbum(
            title=f"@{tweet.name} - {tweet.text}",
            desc=f"Images from @{tweet.name} at {tweet.url}",
        ).create(self.imgur)

    def get_statuses(self):
        """
        Get recent twitter statuses
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
        """
        Upload twitter images to imgur
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
        """
        Find statuses that have alread been uploaded to imgur
        """
        sids = [s.sid for s in statuses]
        return self.database.get_docs("sid", sids)

    def to_reddit(self, posts):
        """
        Upload imgur links to reddit
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
        """
        Get twitter statuses and upload to reddit
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


def main():
    """
    Process from command line
    """
    load_dotenv()

    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-l", "--log", dest="logfile", help="Log file.", metavar="LOGFILE"
    )
    parser.add_argument(
        "-q",
        "--quite",
        dest="quite",
        default=False,
        action="store_true",
        help="Quite output",
    )
    parser.add_argument(
        "filename", help="File to load archive info from.", metavar="YAMLFILE"
    )
    parser.add_argument(
        "-d",
        "--database",
        dest="database",
        default="database.db",
        help="tinydb file.",
        metavar="DB",
    )

    args = parser.parse_args()
    handler_list = (
        [logging.StreamHandler(stdout), logging.FileHandler(args.logfile)]
        if args.logfile
        else [logging.StreamHandler(stdout)]
    )

    logging.basicConfig(
        format="%(asctime)s\t[%(levelname)s]\t{%(module)s}\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
        handlers=handler_list,
    )

    with open(args.filename, "r") as fp:
        settings = load(fp, Loader=Loader)

    attemps = 1
    t2r = TwitterToReddit(settings)
    posts = t2r.upload()
    while posts is not None and len(posts) == 0 and attemps <= 60:
        logging.warning(
            "No posts were made, sleeping for 1 min to try again. \
                Will attempt %d more times before exiting.",
            60 - attemps,
        )
        sleep(60)
        posts = t2r.upload()
        attemps += 1

    if posts is not None and len(posts) == 0:
        logging.error("No posts made successfully")


if __name__ == "__main__":
    main()
