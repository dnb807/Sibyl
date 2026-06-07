from datetime import datetime
from zoneinfo import ZoneInfo

from database import db_connection


class Tweet:
    def __init__(self, id, original_tweet_id, content, unix_timestamp, username, author):
        self.id = id
        self.original_tweet_id = original_tweet_id
        self.content = content
        self.unix_timestamp = unix_timestamp
        self.username = username
        self.author = author

        # Format time stamp so we can print it 
        copenhagen_time = datetime.fromtimestamp(unix_timestamp, ZoneInfo("Europe/Copenhagen"))
        self.copenhagen_day = copenhagen_time.strftime("%A, %Y-%m-%d")
        self.copenhagen_time = copenhagen_time.strftime("%H:%M:%S %Z")


def list_tweets(username, min_time=None, max_time=None, limit=None):
    conn = db_connection()
    cur = conn.cursor()

    # join to politician to get the display name
    query = """
        SELECT tweet.id, tweet.original_tweet_id, tweet.content, tweet.tweet_timestamp, politician.username, politician.name
        FROM tweet
        JOIN politician ON tweet.username = politician.username
        WHERE 1 = 1
    """
    values = []

    # The filters are only added when given 
    if username:
        query += " AND politician.username = %s"
        values.append(username)

    if min_time is not None:
        query += " AND tweet.tweet_timestamp >= %s"
        values.append(min_time)

    if max_time is not None:
        query += " AND tweet.tweet_timestamp <= %s"
        values.append(max_time)

    query += " ORDER BY tweet.tweet_timestamp DESC"

    if limit is not None:
        query += " LIMIT %s"
        values.append(limit)

    cur.execute(query, values)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    tweets = []
    for row in rows:
        tweet = Tweet(row[0], row[1], row[2], row[3], row[4], row[5])
        tweets.append(tweet)

    return tweets
