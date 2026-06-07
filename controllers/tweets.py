from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request

from models.user import list_users
from models.tweet import list_tweets

bp = Blueprint("tweets", __name__, url_prefix="/")


def date_to_unix(value, end_of_day=False):
    if value == "" or value is None:
        return None

    selected_date = date.fromisoformat(value)
    if end_of_day:
        selected_time = time.max
    else:
        selected_time = time.min
    return int(datetime.combine(selected_date, selected_time, ZoneInfo("Europe/Copenhagen")).timestamp())


@bp.route("/tweets")
def tweet_list():
    username = request.args.get("username", "")
    from_date = request.args.get("from_date", "")
    to_date = request.args.get("to_date", "")

    limit_value = request.args.get("limit", "100")
    if limit_value == "":
        limit = 100 
    else:
        limit = int(limit_value)

    min_time = date_to_unix(from_date)
    max_time = date_to_unix(to_date, end_of_day=True)

    users = list_users()
    tweets = list_tweets(username, min_time, max_time, limit)

    if limit is None:
        displayed_limit = ""
    else:
        displayed_limit = limit

    return render_template(
        "tweets.html",
        users=users,
        tweets=tweets,
        selected_username=username,
        from_date=from_date,
        to_date=to_date,
        min_time=min_time,
        max_time=max_time,
        limit=displayed_limit,
    )
