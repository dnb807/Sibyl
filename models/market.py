from datetime import datetime
from zoneinfo import ZoneInfo

from database import db_connection


def format_time(unix_timestamp):
    if unix_timestamp is None:
        return ""

    moment = datetime.fromtimestamp(int(unix_timestamp), ZoneInfo("Europe/Copenhagen"))
    return moment.strftime("%Y-%m-%d %H:%M")


class Market:
    def __init__(self, market_id, topic, creation_timestamp, resolution_timestamp, price_pool):
        self.market_id = market_id
        self.topic = topic
        self.creation_timestamp = creation_timestamp
        self.resolution_timestamp = resolution_timestamp
        self.creation_time = format_time(creation_timestamp)
        self.resolution_time = format_time(resolution_timestamp)
        self.price_pool = price_pool


def list_markets(limit=None):
    conn = db_connection()
    cur = conn.cursor()

    query = """
        SELECT
            market_id,
            topic,
            creation_timestamp,
            resolution_timestamp,
            price_pool
        FROM market
        ORDER BY market_id
    """
    values = []

    if limit is not None:
        query += " LIMIT %s"
        values.append(limit)

    cur.execute(query, values)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    markets = []
    for row in rows:
        market = Market(row[0], row[1], row[2], row[3], row[4])
        markets.append(market)

    return markets
