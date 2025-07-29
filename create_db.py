import sqlite3
import requests
import time
import re
import os


def clean_location_name(name):
    name = name.replace("kanto-", "").replace("-area", "")
    name = name.replace("-", " ").title()
    if "Route" in name:
        name = re.sub(r"Route (\\d+)", r"Route \\1", name)
    return name.strip()


SUPPORTED_VERSIONS = {"red", "blue", "yellow", "firered", "leafgreen"}

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/encounters.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS encounters")
cur.execute("DROP TABLE IF EXISTS routes")
cur.execute("DROP TABLE IF EXISTS regions")

cur.execute(
    """CREATE TABLE regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)"""
)

cur.execute(
    """CREATE TABLE routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    region_id INTEGER,
    completed INTEGER DEFAULT 0,
    FOREIGN KEY(region_id) REFERENCES regions(id)
)"""
)

cur.execute(
    """CREATE TABLE encounters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    pokemon TEXT,
    rate TEXT,
    method TEXT,
    FOREIGN KEY(route_id) REFERENCES routes(id)
)"""
)

cur.execute("INSERT INTO regions (name) VALUES ('Kanto')")
kanto_id = cur.lastrowid

region_data = requests.get("https://pokeapi.co/api/v2/region/1").json()
route_names_seen = set()

for location in region_data["locations"]:
    loc_detail = requests.get(location["url"]).json()
    for area in loc_detail["areas"]:
        area_data = requests.get(area["url"]).json()
        name = clean_location_name(area_data["name"])

        if name in route_names_seen:
            continue
        route_names_seen.add(name)

        cur.execute(
            "INSERT INTO routes (name, region_id) VALUES (?, ?)", (name, kanto_id)
        )
        route_id = cur.lastrowid

        added = False
        seen = set()

        for poke in area_data["pokemon_encounters"]:
            species = poke["pokemon"]["name"].title()
            for v in poke["version_details"]:
                version = v["version"]["name"]
                if version in SUPPORTED_VERSIONS:
                    for d in v["encounter_details"]:
                        chance = d.get("chance")
                        method = d["method"]["name"]
                        key = (species, chance, method)
                        if chance and key not in seen:
                            seen.add(key)
                            cur.execute(
                                "INSERT INTO encounters (route_id, pokemon, rate, method) VALUES (?, ?, ?, ?)",
                                (route_id, species, f"{chance}%", method),
                            )
                            added = True  # ✅ Important fix

        if not added:
            cur.execute("DELETE FROM routes WHERE id = ?", (route_id,))
            route_names_seen.remove(name)

        print(f"Processed: {name}")
        time.sleep(0.5)

conn.commit()
conn.close()
print("✅ Kanto encounter data loaded into data/encounters.db")
