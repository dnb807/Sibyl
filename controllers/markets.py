from flask import Blueprint, render_template, request
from models.market import list_markets

bp = Blueprint("markets", __name__, url_prefix="/")


@bp.route("/markets")
def market_list():
    limit_value = request.args.get("limit", "100")
    if limit_value == "":
        limit = 100 
    else:
        limit = int(limit_value)
    markets = list_markets(limit)

    return render_template(
        "markets.html",
        markets=markets,
        limit=limit,
    )
