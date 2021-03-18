from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime
from dotenv import load_dotenv
from json import dumps
from os import getenv, fsync
from sys import stdout
from time import sleep
from tinydb import TinyDB, where, JSONStorage
from yaml import load, Loader

from imgurpython import ImgurClient
from praw import Reddit
from twitter import Api as Twitter

import logging
import re


class PrettyJSONStorage(JSONStorage):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def write(self, data):
		self._handle.seek(0)
		serialized = dumps(data, indent=4, sort_keys=True, **self.kwargs)
		try:
			self._handle.write(serialized)
		except UnsupportedOperation:
			raise IOError(f'Cannot write to the database. Access mode is "{self._mode}"')

		self._handle.flush()
		fsync(self._handle.fileno())

		self._handle.truncate()

class Database:
	''' Document Example
	{
		'sid': "twitter status id",
		'user': "twitter user name, @{user}",
		'tweet': "twitter url of tweet",
		'text': "body of tweet",
		'imgs': ["imgur img ids uploaded from tweet"],
		'album': "imgur album deletehash",
		'aid': "imgur album id",
		'post': "reddit post url",
	}
	'''
	def __init__(self, filename, table):
		self.table = table
		self.db = TinyDB(filename, storage=PrettyJSONStorage).table(table)

	def upsert(self, data, key, val):
		logging.debug(f'Upserting into table "{self.table}" where "{key}" == "{val}" with data: {data}')
		return self.db.upsert(data, where(key) == val)

	def check_upload(self, key, val):
		logging.debug(f'Searching for docs in table "{self.table}" where "{key}" == "{val}"')
		return self.db.search(where(key) == val)

	def get_docs(self, key, vals):
		docs = []
		for val in vals:
			ret = self.db.search(where(key) == val)
			if ret:	docs.extend(ret)
		return docs

class TweetStatus:
	def __init__(self, status):
		self.sid = status.id
		self.date = datetime.fromtimestamp(status.created_at_in_seconds).strftime('%Y-%m-%d %H:%M:%S')
		self.screen_name = status.user.screen_name
		self.name = status.user.name
		self.url = self.tweet_url(self.screen_name, status.id)
		self.text = self.clean_text(status.text)
		self.media = [ self.media_url(m) for m in status.media ]
		logging.debug(f'Generated TweetStatus for tweet {self.sid}')

	def clean_text(self, text):
		return re.sub(r'\s+https://t.co/.*?$', '', text)

	def media_url(self, media):
		size = '?name=large' if 'large' in media.sizes else ''
		return f'{media.media_url_https}{size}'

	def tweet_url(self, screen_name, sid):
		return f'https://twitter.com/{screen_name}/status/{sid}'

class ImgurAlbum:
	def __init__(self, deletehash=None, aid=None, title=None, desc=None, privacy='hidden'):
		self.deletehash = deletehash
		self.aid = aid
		self.url = form_url(aid) if aid else None
		self.config = {
			'title': title,
			'description': desc,
			'privacy': privacy,
		}
		if self.deletehash:
			logging.debug(f'Generated ImgurAlbum for album with deletehash "{self.deletehash}"')
		else:
			logging.debug(f'Generated ImgurAlbum for album with title "{self.config["title"]}", no deletehash provided')

	def form_url(self, album_id):
		return f'https://imgur.com/a/{album_id}'

	def create(self, client):
		if not self.deletehash:
			logging.info(f'Creating new imgur album with config: {self.config}')
			album = client.create_album(self.config)
			self.deletehash = album['deletehash']
			self.aid = album['id']
			self.url = self.form_url(self.aid)
		elif not self.aid:
			logging.info(f'Getting album id and url for album with deletehash: {self.deletehash}')
			self.aid = client.get_album(self.deletehash)
			self.url = self.form_url(self.aid)
		else:
			logging.info(f'Imgur album does not need to be created, it already exists with deletehash "{self.deletehash}"')
			if not self.url:
				self.url = self.form_url(self.aid)
		return self.deletehash

	def add(self, client, img_ids):
		logging.info(f'Adding {len(img_ids)} ids to album with deletehash "{self.deletehash}": {img_ids}')
		if not self.deletehash:
			logging.debug('Creating album to add imgs to.')
			self.create(client)
		return client.album_add_images(self.deletehash, img_ids)

	def url(self, client):
		if not self.url and not self.deletehash:
			self.create(client)
		elif not self.url:
			self.url = self.form_url(self.aid)
		logging.info(f'Getting Imgur album url: {self.url}')
		return self.url

class ImgurImages:
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
		logging.debug(f'Generated new imgur images from tweet {tweet.sid} and putting it in album {self.album}')

	def gen_config(self, album, idx=-1):
		logging.debug(f'Generating imgur image upload config for album "{album}"')
		title = None
		desc = None
		if idx >= 0:
			title = f'#{self.number} - {self.body} - @{self.screen_name} - {idx+1} of {len(self.media)}'
			desc = '{name} (@{screen_name}) - {idx} of {total}\n#{num} - {body}\n\nCreated: {date}\t{link}'.format(
				name=self.name,
				screen_name=self.screen_name,
				body=self.body,
				link=self.url,
				date=self.date,
				idx=idx+1,
				total=len(self.media),
				num=self.number
			)
		else:
			title = f'#{self.number} - {self.body} - @{self.screen_name}'
			desc = '{name} (@{screen_name})\n#{num} - {body}\n\nCreated: {date}\t{link}'.format(
				name=self.name,
				screen_name=self.screen_name,
				body=self.body,
				link=self.url,
				date=self.date,
				num=self.number
			)

		return {
			'album': album,
			'name': title,
			'title': title,
			'description': desc,
		}

	def upload(self, client):
		logging.info(f'Uploading {len(self.media)} images to album "{self.album}"')
		for i, m in enumerate(self.media):
			cfg = self.gen_config(album=self.album, idx=i) if len(self.media) > 1 else self.gen_config(album=self.album)
			ret = client.upload_from_url(m, config=cfg, anon=False)
			self.imgs.append(ret['id'])
		return self.imgs

class RedditPost:
	def __init__(self, subreddit, link, title, post, com):
		self.subreddit = subreddit
		self.link = link
		self.title = title
		self.post = post
		self.com = com
		self.ret = None

	def upload(self, doc):
		comment_text = '{name} (@{user})\n{body}\n\n{link}\n\n&nbsp;\n\n^(I am a bot developed by /u/spsseano. My source code can be found at https://github.com/spslater/twitter2reddit)'.format(
			name=doc['name'],
			user=doc['user'],
			body=doc['raw'],
			link=doc['tweet']
		)

		if not self.post:
			logging.info(f'Submitting Reddit link to subreddit "{self.subreddit}" for images "{self.link}"')
			self.ret = self.subreddit.submit(title=self.title, url=self.link)
			self.ret.disable_inbox_replies()
			self.post = self.ret.permalink
			info = self.ret.reply(comment_text)
			self.com = info.permalink
		elif not self.com:
			logging.info(f'Already submitted Reddit link leaving comment: {self.post}')
			info = self.ret.reply(comment_text)
			self.com = info.permalink
		else:
			logging.info(f'Already submitted Reddit link and commented: {self.post} - {self.com}')
		return self.post, self.com

class TwitterToReddit:
	def __init__(self, settings, twitter_client=None, imgur_client=None, reddit_client=None):
		self.user = settings['user']
		self.all_album = ImgurAlbum(deletehash=settings['all_hash'], title=settings['all_name'], desc=settings['all_desc'])
		self.subreddit = settings['subreddit']

		self.twitter = twitter_client if twitter_client else self.get_twitter()
		self.imgur = imgur_client if imgur_client else self.get_imgur()
		self.reddit = reddit_client if reddit_client else self.get_reddit()

		with open(settings['number'], 'r') as fp:
			self.number = int(fp.read().strip())

		self.database = Database(filename=settings['database'], table=settings['table'])

	def get_twitter(self):
		logging.debug('Generating Twitter Client')
		return Twitter(
			consumer_key=getenv('TWITTER_CONSUMER_KEY'),
			consumer_secret=getenv('TWITTER_CONSUMER_SECRET'),
			access_token_key=getenv('TWITTER_ACCESS_TOKEN_KEY'),
			access_token_secret=getenv('TWITTER_ACCESS_TOKEN_SECRET'),
			request_headers={"Authorization": "Bearer {}".format(getenv('TWITTER_BEARER_TOKEN'))}
		)

	def get_imgur(self):
		logging.debug('Generating Imgur Client')
		return ImgurClient(
			client_id=getenv('IMGUR_CLIENT'),
			client_secret=getenv('IMGUR_SECRET'),
			access_token=getenv('IMGUR_ACCESS_TOKEN'),
			refresh_token=getenv('IMGUR_REFRESH_TOKEN')
		)

	def get_reddit(self):
		logging.debug('Generating Reddit Client')
		return Reddit(
			client_id=getenv('REDDIT_CLIENT_ID'),
			client_secret=getenv('REDDIT_CLIENT_SECRET'),
			username=getenv('REDDIT_USERNAME'),
			password=getenv('REDDIT_PASSWORD'),
			user_agent=getenv('REDDIT_USER_AGENT')
		)

	def single_album(self, tweet):
		logging.debug('Generating ImgurAlbum for single tweet "{tweet.sid}" from @{tweet.name} with multiple media files')
		return ImgurAlbum(
			title=f'@{tweet.name} - {tweet.text}',
			desc=f'Images from @{tweet.name} at {tweet.url}'
		).create(self.imgur)

	def get_statuses(self):
		logging.info(f'Getting recent statuses from Twitter for @{self.user}')
		statuses = self.twitter.GetUserTimeline(screen_name=self.user, exclude_replies=True, include_rts=False)
		unchecked = []
		partial = []
		for status in statuses:
			if status.media:
				doc = self.database.check_upload('sid', status.id)
				if doc and doc[0]['post'] == None:
					partial.append(status)
				elif not doc:
					unchecked.append(status)
		return [TweetStatus(s) for s in unchecked], [TweetStatus(s) for s in partial]

	def to_imgur(self, statuses):
		logging.info(f'Uploaded {len(statuses)} tweet images to imgur')
		post_urls = []
		for status in statuses:
			db_entry = {
				'sid': status.sid,
				'name': status.name,
				'user': status.screen_name,
				'tweet': status.url,
				'raw': status.text,
				'title': None,
				'imgs': [],
				'url': None,
				'album': None,
				'aid': None,
				'post': None,
				'number': self.number
			}
			imgs = ImgurImages(status, self.number).upload(self.imgur)
			db_entry['imgs'] = imgs
			db_entry['title'] = f'#{self.number} - {status.text}'
			url = f'https://i.imgur.com/{imgs[0]}.jpg'
			self.all_album.add(self.imgur, imgs)
			if len(status.media) > 1:
				album = self.single_album(status)
				album.add(self.imgur, imgs)
				db_entry['album'] = album.deletehash
				db_entry['aid'] = album.aid
				url = album.url(self.imgur)
			elif len(status.media) == 1:
				db_entry['album'] = self.all_album.deletehash
				db_entry['aid'] = self.all_album.aid
			db_entry['url'] = url
			self.database.upsert(db_entry, 'sid', status.sid)
			post_urls.append(db_entry)
			self.number += 1
			with open(settings['number'], 'w') as fp:
				fp.write(str(self.number))
		return post_urls

	def already_uploaded(self, statuses):
		sids = [ s.sid for s in statuses ]
		return self.database.get_docs('sid', sids)

	def to_reddit(self, posts):
		logging.info(f'Posting {len(posts)} imgur links to /r/{self.subreddit}')
		post_urls = []
		for post in posts:
			sid = post['sid']
			link = post['url']
			title = post['title']
			screen_name = post['user']
			name = post['name']
			raw = post['raw']
			twt = post['tweet']
			red = post.get('post')
			com = post.get('com')

			sub = self.reddit.subreddit(self.subreddit)
			res, com = RedditPost(subreddit=sub, link=link, title=title, post=red, com=com).upload(post)

			if res is not None and com is not None:
				logging.warning(f'Reddit posting not successful.')
			else:
				self.database.upsert({'post': res, 'url': link, 'comment': com}, 'sid', sid)
				post_urls.append(res)
				logging.info(f'Reddit Post: {res}')
		return post_urls

	def upload(self):
		logging.info(f'Starting recent status uploads from @{self.user} to post on /r/{self.subreddit}')
		unchecked, partial = self.get_statuses()
		uploaded = self.to_imgur(unchecked)
		posts = self.to_reddit(uploaded)
		partial_imgur = self.already_uploaded(partial)
		partial_posts = self.to_reddit(partial_imgur)
		posts.extend(partial_posts)
		logging.info(f'Successfully made {len(posts)} new posts to /r/{self.subreddit} from @{self.user}')
		logging.debug(f'New posts on /r/{self.subreddit}: {posts}')
		return posts


if __name__ == "__main__":
	load_dotenv()

	parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
	parser.add_argument('-l', '--log', dest='logfile',
		help="Log file.", metavar="LOGFILE")
	parser.add_argument('-q', '--quite', dest='quite', default=False, action='store_true',
		help="Quite output")
	parser.add_argument('filename',
		help="File to load archive info from.", metavar='YAMLFILE')
	parser.add_argument('-d', '--database', dest='database', default='database.db',
		help='tinydb file.', metavar='DB')

	args = parser.parse_args()
	handler_list = [
		logging.StreamHandler(stdout),
		logging.FileHandler(args.logfile)
	] if args.logfile else [
		logging.StreamHandler(stdout)
	]

	logging.basicConfig(
		format='%(asctime)s\t[%(levelname)s]\t{%(module)s}\t%(message)s',
		datefmt='%Y-%m-%d %H:%M:%S',
		level=logging.INFO,
		handlers=handler_list
	)

	with open(args.filename, 'r') as fp:
		settings = load(fp, Loader=Loader)

	attemps = 1
	t2r = TwitterToReddit(settings)
	posts = t2r.upload()
	while not posts and attemps < 60:
		logging.warning(f'No posts were made, sleeping for 1 min to try again. Will attempt {60-attemps} more times before exiting.')
		sleep(60)
		posts = t2r.upload()
		attemps += 1

	if not posts:
		logging.error(f'No posts made successfully')
