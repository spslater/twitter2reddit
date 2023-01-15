# Twitter 2 Reddit
Install package requirements from `requirements.txt`

Can then run with `python3 main.py settings.yml`

## Yaml Settings File
Required for every run:
``` yaml
database: database to save tweet and post info in
table: table in said database to look for data
```
Optional attribute: `only_recent` boolean value for if only the most recent tweet should be uploaded
to reddit or if all missing ones should be, defaults to `False` if no value given.

First time running for a table the following needs to be added

Verbose Structure:
``` yaml
first_time:
  imgur:
    album_id: album id, if left empty will be filled in by newly created album
    deletehash: album deletehash, if left empty will be filled in by newly created album
    description: album description, optional, defaults to "<title> art by @<user_name> - <user_url>"
    title: album title
  number: 1
  reddit:
    subreddit: subreddit name, no /r/
  table: art table name, needs to match `table` in top level, optional, defaults to top level table name
  twitter:
    user_name: "@ user name"
    user_url: user url, optional defaults to "https://twitter.com/<user_name>"
```
Flat Structure:
``` yaml
first_time:
  album_id: album id, if left empty will be filled in by newly created album
  deletehash: album deletehash, if left empty will be filled in by newly created album
  description: album description, optional, defaults to "<title> art by @<user_name> - <user_url>"
  title: album title
  number: 1
  subreddit: subreddit name, no /r/
  table: art table name, needs to match `table` in top level, optional, defaults to top level table name
  user_name: "@ user name"
  user_url: user url, optional defaults to "https://twitter.com/<user_name>"
```

### Example
Min Overall Structure Example:
``` yaml
database: littlenuns.db
table: littlenuns
first_time:
  title: Little Nuns
  number: 1
  subreddit: LittleNuns
  user_name: "hyxpk"
```

## .env File
Need to have a .env file or these values in the environment to create the clients:
``` ini
TWITTER_CONSUMER_KEY=
TWITTER_CONSUMER_SECRET=
TWITTER_ACCESS_TOKEN_KEY=
TWITTER_ACCESS_TOKEN_SECRET=
TWITTER_BEARER_TOKEN=
TWITTER_TIMEOUT=(optional, defaults to 360 if no value given)

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

## Schedule File
Schedule can be used for non regular posts. Currently needs to be manually updated.
Example file:
``` yaml
2023:
  1: [1,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30]
  2: [1,3,5,7,9,11,12,14,16,18,19,21,23,25,27,29]
2024:
  3: [1,10,20,30]
```