from flask import Flask, redirect, url_for

from database import init_db
from controllers import correlations, markets, tweets

init_db()

app = Flask(__name__)


@app.route("/")
def home():
    return redirect(url_for("correlations.correlation_list"))

app.register_blueprint(tweets.bp)
app.register_blueprint(markets.bp)
app.register_blueprint(correlations.bp)
