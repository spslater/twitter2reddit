# Twitter 2 Reddit
Install package requirements from `requirements.txt`

Can then run with `python3 twitter2reddit.py settings.yml`

## Yaml Settings File
The all_* attributes in the doc are where all media from user will be added. If there is multiple media
in the tweet then it'll also get added to it's own album.

``` yaml
user: twitter user handle
all_hash: imgur album deletehash
all_aid: imgur album id (in url)
all_name: name of imgur album
all_desc: description of twitter album
subreddit: subreddit to post to
database: database to save tweet and post info in
table: table in said database to look for data
```

## .env File
Need to have a .env file or these values in the environment to create the clients:

```
TWITTER_CONSUMER_KEY=
TWITTER_CONSUMER_SECRET=
TWITTER_ACCESS_TOKEN_KEY=
TWITTER_ACCESS_TOKEN_SECRET=
TWITTER_BEARER_TOKEN=

IMGUR_CLIENT=
IMGUR_SECRET=
IMGUR_ACCESS_TOKEN=
IMGUR_REFRESH_TOKEN=

REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USERNAME=
REDDIT_PASSWORD=
REDDIT_USER_AGENT=
```