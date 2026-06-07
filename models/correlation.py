import re
from datetime import datetime
from zoneinfo import ZoneInfo
from database import db_connection


# regexes for the "tweet contains" dropdown: a hashtag, a mention or a cashtag ($TSLA)
HASHTAG_RE = re.compile(r"#\w+")
MENTION_RE = re.compile(r"@\w+")
CASHTAG_RE = re.compile(r"\$[A-Z]{1,6}")

PATTERNS = {
    "hashtag": HASHTAG_RE,
    "mention": MENTION_RE,
    "cashtag": CASHTAG_RE,
}


class Correlation:
    def __init__(self, row):
        (self.tweet_id, original_tweet_id, self.username, self.author, self.content, tweet_timestamp, self.topic, slug, correlation_timestamp, self.delta_pct) = row

        when = datetime.fromtimestamp(tweet_timestamp, ZoneInfo("Europe/Copenhagen"))

        self.tweet_time = when.strftime("%Y-%m-%d %H:%M")
        self.minutes_after = round((correlation_timestamp - tweet_timestamp) / 60)
        self.tweet_url = f"https://x.com/i/status/{original_tweet_id}"
        if slug:
            self.market_url = f"https://polymarket.com/event/{slug}"
        else:
            self.market_url = None


def list_correlations(username="", min_time=None, max_time=None,
                      pattern="", limit=100):
    conn = db_connection()
    cur = conn.cursor()

    statement = ""

    # Select the markets and tweets based on constraints
    statement += """
        SELECT
            tweet.id,
            tweet.original_tweet_id,
            tweet.username,
            politician.name,
            tweet.content,
            tweet.tweet_timestamp,
            market.topic,
            market.slug,
            correlation_event.timestamp,
            correlation_event.delta_pct
        FROM correlation_event
        JOIN tweet ON correlation_event.tweet_id = tweet.id
        JOIN politician ON tweet.username = politician.username
        JOIN market ON correlation_event.market_id = market.market_id
        WHERE
            (%(username)s = '' OR tweet.username = %(username)s)
            AND (%(min_time)s IS NULL OR tweet.tweet_timestamp >= %(min_time)s)
            AND (%(max_time)s IS NULL OR tweet.tweet_timestamp <= %(max_time)s)
    """

    # sort
    statement += """
        ORDER BY
            tweet.tweet_timestamp DESC,
            ABS(correlation_event.delta_pct) DESC
    """

    cur.execute(statement, {
        "username": username or "",
        "min_time": min_time,
        "max_time": max_time,
    })

    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Build the correlations array
    correlations = []
    for row in rows:
        correlation = Correlation(row)
        correlations.append(correlation)


    # Only keep the tweets that match regex (if chosen)
    regex = PATTERNS.get(pattern)

    if regex is not None:
        filtered_correlations = []

        for correlation in correlations:
            content = correlation.content
            match = regex.search(content)

            if match:
                filtered_correlations.append(correlation)

        correlations = filtered_correlations

    # Cut off by limit
    if limit is not None:
        correlations = correlations[:limit]

    return correlations


# Build the correlation rows.
#
# We use JOIN LATERAL here. We did not know how this worked beforehand, 
# but found this resource to be very helpful:
# https://www.crunchydata.com/developers/playground/lateral-join
#
# We needed something faster than NOT EXISTS because this is an expensive
# calculation, and thus found JOIN LATERAL. It finds the closest baseline
# price and the strongest later movement efficiently.
def compute_correlation_rows(cur, window_seconds, threshold_pct):
    statement = ""

    statement += """
        SELECT
            tweet.id,
            market.market_id,
            later_price.timestamp,
            (later_price.price - baseline_price.price)
                / baseline_price.price * 100.0
    """

    # The real matching happens inside the LATERAL.
    # baseline_price is the last price at the time or just before the tweet,
    # later_price is the strongest move within the window after it.
    statement += """
        FROM
            tweet
            JOIN market ON TRUE
            JOIN LATERAL (
                SELECT
                    price_observation.market_id,
                    price_observation.price
                FROM
                    price_observation
                WHERE
                    price_observation.market_id = market.market_id
                    AND price_observation.timestamp <= tweet.tweet_timestamp
                    AND price_observation.price > 0
                ORDER BY
                    price_observation.timestamp DESC
                LIMIT 1
            ) baseline_price ON baseline_price.market_id = market.market_id
            JOIN LATERAL (
                SELECT
                    price_observation.market_id,
                    price_observation.timestamp,
                    price_observation.price
                FROM
                    price_observation
                WHERE
                    price_observation.market_id = market.market_id
                    AND price_observation.timestamp > tweet.tweet_timestamp
                    AND price_observation.timestamp
                        <= tweet.tweet_timestamp + %(window)s
                ORDER BY
                    ABS(
                        (price_observation.price - baseline_price.price)
                        / baseline_price.price * 100.0
                    ) DESC,
                    price_observation.timestamp
                LIMIT 1
            ) later_price ON later_price.market_id = market.market_id
    """

    # only keep the ones that are above the threshold
    statement += """
        WHERE
            ABS(
                (later_price.price - baseline_price.price)
                / baseline_price.price * 100.0
            ) >= %(threshold)s
    """

    # Sort again
    statement += """
        ORDER BY
            tweet.tweet_timestamp DESC,
            ABS(
                (later_price.price - baseline_price.price)
                / baseline_price.price * 100.0
            ) DESC
    """

    cur.execute(statement, {
        "window": window_seconds,
        "threshold": threshold_pct,
    })

    return cur.fetchall()


def recompute_cache(cur, window_seconds, threshold_pct):
    cur.execute("DELETE FROM correlation_event")

    rows = compute_correlation_rows(
        cur,
        window_seconds,
        threshold_pct,
    )

    correlation_id = 1
    for row in rows:
        tweet_id, market_id, timestamp, delta_pct = row

        cur.execute("""
            INSERT INTO correlation_event (
                correlation_id,
                tweet_id,
                market_id,
                timestamp,
                delta_pct
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            correlation_id,
            tweet_id,
            market_id,
            timestamp,
            delta_pct,
        ))

        correlation_id += 1


# called at startup with the defaults, and again from the settings page
def recalculate_correlations(window_hours=3, threshold_pct=5.0):
    conn = db_connection()
    cur = conn.cursor()

    recompute_cache(
        cur,
        int(window_hours * 3600),
        threshold_pct,
    )

    conn.commit()
    cur.close()
    conn.close()
