import json
import os

import psycopg2

user = os.environ.get("PGUSER", "postgres")
password = os.environ.get("PGPASSWORD", "123")
host = os.environ.get("DB_HOST", os.environ.get("HOST", "127.0.0.1"))
dbname = os.environ.get("PGDATABASE", "fortuneteller")
tweets_dir = os.path.join(os.path.dirname(__file__), "data", "tweets")
polymarket_dir = os.path.join(os.path.dirname(__file__), "data", "polymarket")

DEFAULT_CORRELATION_WINDOW_HOURS = 4.0
DEFAULT_CORRELATION_THRESHOLD_PCT = 80.0


def db_connection():
    return psycopg2.connect(
        dbname=dbname,
        user=user,
        host=host,
        password=password,
    )


def init_db():
    print("Initializing database....")
    conn = db_connection()
    cur = conn.cursor()

    # politician: the people we follow, one politician writes many tweets
    cur.execute("""
        CREATE TABLE IF NOT EXISTS politician (
            username TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    # tweet: belongs to one politician. id is the source id, and we keep
    # original_tweet_id so we can open the tweet on X.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tweet (
            id BIGINT PRIMARY KEY,
            original_tweet_id BIGINT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            tweet_timestamp BIGINT NOT NULL,
            content TEXT NOT NULL,

            FOREIGN KEY (username)
                REFERENCES politician(username)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        )
    """)

    # market: one market has many price observations. slug links back to the
    # market on Polymarket, similar to original_tweet_id for tweets.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market (
            market_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            slug TEXT,
            creation_timestamp BIGINT,
            resolution_timestamp BIGINT,
            price_pool REAL,

            CHECK (
                resolution_timestamp IS NULL
                OR creation_timestamp IS NULL
                OR resolution_timestamp >= creation_timestamp
            )
        )
    """)

    # price_observation: a market's price at a point in time. composite key
    # because a market has many observations, but only one per (timestamp, interval).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_observation (
            market_id TEXT NOT NULL,
            timestamp BIGINT NOT NULL,
            interval TEXT NOT NULL,
            price REAL NOT NULL,

            PRIMARY KEY (market_id, timestamp, interval),

            FOREIGN KEY (market_id)
                REFERENCES market(market_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE,

            CHECK (price >= 0 AND price <= 1)
        )
    """)

    # correlation_event: one cached correlation. a tweet, the market that moved
    # after it, when the biggest change happened, and that change as a percent.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS correlation_event (
            correlation_id INTEGER PRIMARY KEY,
            tweet_id BIGINT NOT NULL,
            market_id TEXT NOT NULL,
            timestamp BIGINT NOT NULL,
            delta_pct REAL NOT NULL,

            FOREIGN KEY (tweet_id)
                REFERENCES tweet(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE,

            FOREIGN KEY (market_id)
                REFERENCES market(market_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
    """)

    # start fresh on every run
    cur.execute("DELETE FROM correlation_event")
    cur.execute("DELETE FROM price_observation")
    cur.execute("DELETE FROM tweet")
    cur.execute("DELETE FROM market")
    cur.execute("DELETE FROM politician")

    # load the markets and their price observations
    if os.path.isdir(polymarket_dir):
        for filename in sorted(os.listdir(polymarket_dir)):
            if not filename.endswith(".json"):
                continue

            path = os.path.join(polymarket_dir, filename)

            with open(path, encoding="utf-8") as f:
                market = json.load(f)

            cur.execute(
                """
                INSERT INTO market (
                    market_id,
                    topic,
                    slug,
                    creation_timestamp,
                    resolution_timestamp,
                    price_pool
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    market["market_id"],
                    market["topic"],
                    market.get("slug"),
                    market.get("creation_timestamp"),
                    market.get("resolution_timestamp"),
                    market.get("price_pool"),
                ),
            )

            for observation in market.get("price_observations", []):
                cur.execute(
                    """
                    INSERT INTO price_observation (
                        market_id,
                        timestamp,
                        interval,
                        price
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        market["market_id"],
                        observation["timestamp"],
                        observation["interval"],
                        observation["price"],
                    ),
                )

    # load the politicians and their tweets
    if os.path.isdir(tweets_dir):
        for filename in sorted(os.listdir(tweets_dir)):
            if not filename.endswith(".json"):
                continue

            path = os.path.join(tweets_dir, filename)

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            metadata = data["metadata"]
            username = metadata["username"]
            name = metadata["name"]

            cur.execute(
                """
                INSERT INTO politician (
                    username,
                    name
                )
                VALUES (%s, %s)
                """,
                (
                    username,
                    name,
                ),
            )

            for tweet in data["tweets"]:
                tweet_id = int(tweet["id"])

                cur.execute(
                    """
                    INSERT INTO tweet (
                        id,
                        original_tweet_id,
                        username,
                        tweet_timestamp,
                        content
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        tweet_id,
                        tweet_id,
                        username,
                        tweet["timestamp"],
                        tweet["tweet"],
                    ),
                )

    conn.commit()
    cur.close()
    conn.close()

    # fill the correlation cache once with the default settings
    from models.correlation import recalculate_correlations

    recalculate_correlations(
        DEFAULT_CORRELATION_WINDOW_HOURS,
        DEFAULT_CORRELATION_THRESHOLD_PCT,
    )
    print("Done!")
