import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'encounters.db')


def test_can_connect_to_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()
    assert {'routes', 'encounters', 'regions'}.issubset(tables)


def test_routes_have_encounters():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM routes LIMIT 1")
    route_id = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM encounters WHERE route_id = ?", (route_id,))
    count = cur.fetchone()[0]
    conn.close()
    assert count > 0


def test_get_routes_function():
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from app import get_routes

    routes = get_routes()
    assert routes, "No routes returned"
    first = routes[0]
    assert 'pokemon' in first and isinstance(first['pokemon'], list)
    assert len(first['pokemon']) > 0
    for entry in first['pokemon']:
        assert 'name' in entry and 'rate' in entry
