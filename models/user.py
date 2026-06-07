from database import db_connection


class User:
    def __init__(self, username, author):
        self.username = username
        self.author = author


# the politicians we follow, used to fill the user dropdowns
def list_users():
    conn = db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, name FROM politician ORDER BY username")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    users = []
    for row in rows:
        user = User(row[0], row[1])
        users.append(user)

    return users
