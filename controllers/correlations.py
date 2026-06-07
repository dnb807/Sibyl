from flask import Blueprint, render_template, request, redirect, url_for
from database import DEFAULT_CORRELATION_THRESHOLD_PCT, DEFAULT_CORRELATION_WINDOW_HOURS
from controllers.tweets import date_to_unix
from models.user import list_users
from models.correlation import list_correlations, recalculate_correlations

bp = Blueprint("correlations", __name__, url_prefix="/")


@bp.route("/correlations")
def correlation_list():
    username = request.args.get("username", "")
    from_date = request.args.get("from_date", "")
    to_date = request.args.get("to_date", "")
    pattern = request.args.get("pattern", "")

    limit_value = request.args.get("limit", "100")
    if limit_value == "":
        limit = 100 
    else:
        limit = int(limit_value)

    correlations = list_correlations(
        username,
        date_to_unix(from_date, end_of_day=False),
        date_to_unix(to_date, end_of_day=True),
        pattern,
        limit,
    )

    return render_template(
        "correlations.html",
        users=list_users(),
        correlations=correlations,
        selected_username=username,
        from_date=from_date,
        to_date=to_date,
        pattern=pattern,
        limit=limit,
    )


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        window = float(request.form.get("window", 3) or 3)
        threshold = float(request.form.get("threshold", 5) or 5)

        recalculate_correlations(window, threshold)

        return redirect(url_for("correlations.settings"))
    else:
        return render_template(
            "settings.html",
            window=DEFAULT_CORRELATION_WINDOW_HOURS,
            threshold=DEFAULT_CORRELATION_THRESHOLD_PCT,
        )
