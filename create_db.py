import sqlite3
import requests
import time
import re
import os

CHECKPOINT_FILE = "data/checkpoint.txt"

REGIONS = {
    1: "Kanto",
    2: "Johto",
    3: "Hoenn",
    4: "Sinnoh",
    5: "Unova",
    6: "Kalos",
    7: "Alola",
    8: "Galar",
    9: "Paldea",
}

VERSIONS_PER_REGION = {
    "kanto": {"red", "blue", "yellow", "firered", "leafgreen"},
    "johto": {"gold", "silver", "crystal", "heartgold", "soulsilver"},
    "hoenn": {"ruby", "sapphire", "emerald", "omegaruby", "alphasapphire"},
    "sinnoh": {"diamond", "pearl", "platinum", "brilliant-diamond", "shining-pearl"},
    "unova": {"black", "white", "black-2", "white-2"},
    "kalos": {"x", "y"},
    "alola": {"sun", "moon", "ultra-sun", "ultra-moon"},
    "galar": {"sword", "shield"},
    "paldea": {"scarlet", "violet"},
}


def load_checkpoint() -> int:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE) as f:
                return int(f.read().strip())
        except Exception:
            return 0
    return 0


def clean_location_name(name: str) -> str:
    # remove region prefix and -area suffix then prettify
    name = re.sub(r"^(kanto|johto|hoenn|sinnoh|unova|kalos|alola|galar|paldea)-", "", name)
    name = name.replace("-area", "")
    name = name.replace("-", " ").title()
    if "Route" in name:
        name = re.sub(r"Route (\d+)", r"Route \1", name)
    return name.strip()


os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/encounters.db")
cur = conn.cursor()

start_index = load_checkpoint()

if start_index == 0:
    cur.execute("DROP TABLE IF EXISTS encounters")
    cur.execute("DROP TABLE IF EXISTS routes")
    cur.execute("DROP TABLE IF EXISTS regions")

cur.execute(
    """CREATE TABLE IF NOT EXISTS regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)"""
)

cur.execute(
    """CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    region_id INTEGER,
    completed INTEGER DEFAULT 0,
    FOREIGN KEY(region_id) REFERENCES regions(id)
)"""
)

cur.execute(
    """CREATE TABLE IF NOT EXISTS encounters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    pokemon TEXT,
    rate TEXT,
    method TEXT,
    FOREIGN KEY(route_id) REFERENCES routes(id)
)"""
)

counter = 0

for region_id, region_name in REGIONS.items():
    cur.execute("SELECT id FROM regions WHERE name = ?", (region_name,))
    row = cur.fetchone()
    if row:
        region_db_id = row[0]
    else:
        cur.execute("INSERT INTO regions (name) VALUES (?)", (region_name,))
        region_db_id = cur.lastrowid
        conn.commit()

    cur.execute("SELECT name FROM routes WHERE region_id = ?", (region_db_id,))
    route_names_seen = {r[0] for r in cur.fetchall()}

    try:
        region_data = requests.get(f"https://pokeapi.co/api/v2/region/{region_id}").json()
    except Exception:
        print(f"Failed to fetch data for {region_name}")
        continue

    for location in region_data["locations"]:
        if counter < start_index:
            counter += 1
            continue
        try:
            loc_detail = requests.get(location["url"]).json()
        except Exception:
            print(f"Failed to fetch location {location['name']} in {region_name}")
            continue
        for area in loc_detail["areas"]:
            try:
                area_data = requests.get(area["url"]).json()
            except Exception:
                print(f"Failed to fetch area {area['name']} in {region_name}")
                continue
            name = clean_location_name(area_data["name"])

            if name in route_names_seen:
                continue
            route_names_seen.add(name)

            cur.execute(
                "INSERT INTO routes (name, region_id) VALUES (?, ?)",
                (name, region_db_id),
            )
            route_id = cur.lastrowid

            added = False
            seen = set()

            allowed_versions = VERSIONS_PER_REGION.get(region_name.lower(), set())

            for poke in area_data["pokemon_encounters"]:
                species = poke["pokemon"]["name"].title()
                for v in poke["version_details"]:
                    version = v["version"]["name"]
                    if allowed_versions and version not in allowed_versions:
                        continue
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
                            added = True

            if not added:
                cur.execute("DELETE FROM routes WHERE id = ?", (route_id,))
                route_names_seen.remove(name)


            print(f"Processed {region_name}: {name}")
            time.sleep(0.5)

        with open(CHECKPOINT_FILE, "w") as f:
            f.write(str(counter + 1))
        conn.commit()
        counter += 1

    conn.commit()

conn.close()
print("✅ Encounter data loaded into data/encounters.db")

