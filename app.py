from flask import Flask, render_template, jsonify, request
import sqlite3

app = Flask(__name__)


def get_routes():
    conn = sqlite3.connect("data/encounters.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, completed FROM routes")
    routes = cur.fetchall()
    result = []
    for r in routes:
        cur.execute("SELECT pokemon, rate FROM encounters WHERE route_id = ?", (r[0],))
        encounters = cur.fetchall()
        result.append(
            {
                "id": r[0],
                "name": r[1],
                "completed": bool(r[2]),
                "pokemon": [{"name": p[0], "rate": p[1]} for p in encounters],
            }
        )
    conn.close()
    return result


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/routes")
def api_routes():
    return jsonify(get_routes())


@app.route("/api/complete", methods=["POST"])
def mark_complete():
    route_id = request.json["route_id"]
    conn = sqlite3.connect("data/encounters.db")
    cur = conn.cursor()
    cur.execute("UPDATE routes SET completed = 1 WHERE id = ?", (route_id,))
    conn.commit()
    conn.close()
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
