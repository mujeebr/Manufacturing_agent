"""
database/seed_data.py

Purpose
-------
Since no real manufacturing data exists yet, this script generates a
realistic synthetic dataset for "Northbridge Precision Manufacturing"
and loads it into database/manufacturing.db using the schema defined
in schema.sql.

Run directly to (re)build the database from scratch:

    python database/seed_data.py

Each function below builds and inserts rows for one table, keeping
foreign keys consistent with tables generated earlier in the run.
"""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import MANUFACTURING_DB_PATH  # noqa: E402

fake = Faker()
Faker.seed(42)
random.seed(42)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def reset_database(conn: sqlite3.Connection) -> None:
    """Drop and recreate all tables by executing schema.sql fresh."""
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
    cursor = conn.cursor()
    # Drop tables first so re-running this script is idempotent.
    tables = [
        "quality_checks", "production_runs", "work_orders", "maintenance_logs",
        "inventory", "raw_materials", "employees", "machines",
        "production_lines", "suppliers", "products", "plants",
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    cursor.executescript(schema_sql)
    conn.commit()


def seed_plants(conn: sqlite3.Connection) -> list[int]:
    """Insert 3 manufacturing plants and return their generated IDs."""
    plants = [
        ("Northbridge Ohio Plant", "Dayton", "USA", 1998),
        ("Northbridge Monterrey Plant", "Monterrey", "Mexico", 2007),
        ("Northbridge Katowice Plant", "Katowice", "Poland", 2012),
    ]
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO plants (plant_name, city, country, opened_year) VALUES (?, ?, ?, ?)",
        plants,
    )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT plant_id FROM plants")]


def seed_production_lines(conn: sqlite3.Connection, plant_ids: list[int]) -> list[int]:
    """Insert 2-3 production lines per plant and return their IDs."""
    line_types = ["Assembly", "CNC Machining", "Welding", "Injection Molding", "Painting"]
    cursor = conn.cursor()
    for plant_id in plant_ids:
        for i in range(random.randint(2, 3)):
            line_type = random.choice(line_types)
            cursor.execute(
                "INSERT INTO production_lines (plant_id, line_name, line_type) VALUES (?, ?, ?)",
                (plant_id, f"{line_type} Line {i + 1}", line_type),
            )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT line_id FROM production_lines")]


def seed_machines(conn: sqlite3.Connection, line_ids: list[int]) -> list[int]:
    """Insert 3-5 machines per production line and return their IDs."""
    machine_types = ["CNC Lathe", "Robotic Arm", "Hydraulic Press", "Conveyor System", "Welding Robot"]
    manufacturers = ["Fanuc", "Siemens", "Haas", "ABB", "KUKA", "Mazak"]
    statuses = ["operational", "operational", "operational", "under_maintenance"]
    cursor = conn.cursor()
    for line_id in line_ids:
        for _ in range(random.randint(3, 5)):
            install_date = fake.date_between(start_date="-10y", end_date="-1y")
            cursor.execute(
                """INSERT INTO machines
                   (line_id, machine_name, machine_type, manufacturer, install_date, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (line_id, f"{random.choice(machine_types)}-{fake.bothify('##??')}",
                 random.choice(machine_types), random.choice(manufacturers),
                 install_date.isoformat(), random.choice(statuses)),
            )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT machine_id FROM machines")]


def seed_products(conn: sqlite3.Connection) -> list[int]:
    """Insert 15 manufactured products and return their IDs."""
    categories = ["Automotive Parts", "Industrial Valves", "Hydraulic Fittings",
                  "Precision Gears", "Sheet Metal Components"]
    cursor = conn.cursor()
    for _ in range(15):
        unit_cost = round(random.uniform(5, 250), 2)
        cursor.execute(
            """INSERT INTO products (product_name, product_category, unit_cost, unit_price)
               VALUES (?, ?, ?, ?)""",
            (f"{fake.word().capitalize()} {random.choice(['Bracket', 'Valve', 'Housing', 'Gear', 'Flange'])}",
             random.choice(categories), unit_cost, round(unit_cost * random.uniform(1.3, 2.2), 2)),
        )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT product_id FROM products")]


def seed_suppliers(conn: sqlite3.Connection) -> list[int]:
    """Insert 10 raw-material suppliers and return their IDs."""
    cursor = conn.cursor()
    for _ in range(10):
        cursor.execute(
            "INSERT INTO suppliers (supplier_name, country, reliability_score) VALUES (?, ?, ?)",
            (fake.company(), fake.country(), round(random.uniform(0.75, 0.99), 2)),
        )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT supplier_id FROM suppliers")]


def seed_raw_materials(conn: sqlite3.Connection, supplier_ids: list[int]) -> list[int]:
    """Insert 20 raw materials, each linked to a random supplier."""
    materials = ["Steel Sheet", "Aluminum Billet", "Copper Wire", "Rubber Seal",
                 "Plastic Resin", "Bronze Casting", "Titanium Rod", "Ceramic Coating"]
    units = ["kg", "liter", "unit", "meter"]
    cursor = conn.cursor()
    for _ in range(20):
        cursor.execute(
            """INSERT INTO raw_materials (material_name, supplier_id, unit, unit_cost)
               VALUES (?, ?, ?, ?)""",
            (random.choice(materials), random.choice(supplier_ids),
             random.choice(units), round(random.uniform(1, 80), 2)),
        )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT material_id FROM raw_materials")]


def seed_inventory(conn: sqlite3.Connection, plant_ids: list[int], material_ids: list[int]) -> None:
    """Insert current inventory levels for a subset of materials at each plant."""
    cursor = conn.cursor()
    today = datetime.now().date()
    for plant_id in plant_ids:
        for material_id in random.sample(material_ids, k=min(12, len(material_ids))):
            cursor.execute(
                """INSERT INTO inventory
                   (plant_id, material_id, quantity_on_hand, reorder_level, last_updated)
                   VALUES (?, ?, ?, ?, ?)""",
                (plant_id, material_id, round(random.uniform(50, 5000), 1),
                 round(random.uniform(100, 500), 1), today.isoformat()),
            )
    conn.commit()


def seed_work_orders(conn: sqlite3.Connection, product_ids: list[int], line_ids: list[int],
                      count: int = 200) -> list[int]:
    """Insert work orders spread over the last 12 months and return their IDs."""
    statuses = ["completed", "completed", "completed", "in_progress", "planned", "cancelled"]
    cursor = conn.cursor()
    for _ in range(count):
        created = fake.date_time_between(start_date="-365d", end_date="-2d")
        due = created + timedelta(days=random.randint(3, 30))
        cursor.execute(
            """INSERT INTO work_orders
               (product_id, line_id, quantity_ordered, status, created_date, due_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (random.choice(product_ids), random.choice(line_ids), random.randint(100, 5000),
             random.choice(statuses), created.isoformat(), due.date().isoformat()),
        )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT work_order_id FROM work_orders")]


def seed_production_runs(conn: sqlite3.Connection, work_order_ids: list[int],
                          machine_ids: list[int]) -> list[int]:
    """Insert 1-3 production runs per work order and return their IDs."""
    cursor = conn.cursor()
    for wo_id in work_order_ids:
        for _ in range(random.randint(1, 3)):
            start = fake.date_time_between(start_date="-365d", end_date="now")
            end = start + timedelta(hours=random.uniform(2, 48))
            units_produced = random.randint(50, 2000)
            defect_rate = random.uniform(0.0, 0.08)
            cursor.execute(
                """INSERT INTO production_runs
                   (work_order_id, machine_id, start_time, end_time,
                    units_produced, units_defective, downtime_minutes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (wo_id, random.choice(machine_ids), start.isoformat(), end.isoformat(),
                 units_produced, int(units_produced * defect_rate),
                 round(random.uniform(0, 180), 1)),
            )
    conn.commit()
    return [row[0] for row in cursor.execute("SELECT run_id FROM production_runs")]


def seed_quality_checks(conn: sqlite3.Connection, run_ids: list[int]) -> None:
    """Insert 1-2 quality inspection records per production run."""
    defect_types = ["surface scratch", "dimensional deviation", "material fracture",
                     "misalignment", "porosity", None]
    severities = ["minor", "major", "critical"]
    cursor = conn.cursor()
    for run_id in run_ids:
        for _ in range(random.randint(1, 2)):
            passed = random.random() > 0.12
            defect_type = None if passed else random.choice(defect_types[:-1])
            severity = None if passed else random.choice(severities)
            cursor.execute(
                """INSERT INTO quality_checks
                   (run_id, check_date, defect_type, severity, inspector, passed)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, fake.date_between(start_date="-365d", end_date="today").isoformat(),
                 defect_type, severity, fake.name(), int(passed)),
            )
    conn.commit()


def seed_maintenance_logs(conn: sqlite3.Connection, machine_ids: list[int]) -> None:
    """Insert 2-6 maintenance log entries per machine."""
    types = ["preventive", "preventive", "corrective", "emergency"]
    cursor = conn.cursor()
    for machine_id in machine_ids:
        for _ in range(random.randint(2, 6)):
            cursor.execute(
                """INSERT INTO maintenance_logs
                   (machine_id, maintenance_date, maintenance_type, cost, downtime_hours, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (machine_id, fake.date_between(start_date="-365d", end_date="today").isoformat(),
                 random.choice(types), round(random.uniform(100, 8000), 2),
                 round(random.uniform(0.5, 24), 1), fake.sentence(nb_words=8)),
            )
    conn.commit()


def seed_employees(conn: sqlite3.Connection, plant_ids: list[int], count: int = 60) -> None:
    """Insert employees distributed across plants and roles."""
    roles = ["Operator", "Operator", "Inspector", "Technician", "Supervisor"]
    cursor = conn.cursor()
    for _ in range(count):
        cursor.execute(
            "INSERT INTO employees (employee_name, role, plant_id, hire_date) VALUES (?, ?, ?, ?)",
            (fake.name(), random.choice(roles), random.choice(plant_ids),
             fake.date_between(start_date="-15y", end_date="-30d").isoformat()),
        )
    conn.commit()


def build_database() -> None:
    """Run all seed_* functions in dependency order to build manufacturing.db."""
    conn = sqlite3.connect(MANUFACTURING_DB_PATH)
    reset_database(conn)

    plant_ids = seed_plants(conn)
    line_ids = seed_production_lines(conn, plant_ids)
    machine_ids = seed_machines(conn, line_ids)
    product_ids = seed_products(conn)
    supplier_ids = seed_suppliers(conn)
    material_ids = seed_raw_materials(conn, supplier_ids)

    seed_inventory(conn, plant_ids, material_ids)
    seed_employees(conn, plant_ids)

    work_order_ids = seed_work_orders(conn, product_ids, line_ids)
    run_ids = seed_production_runs(conn, work_order_ids, machine_ids)
    seed_quality_checks(conn, run_ids)
    seed_maintenance_logs(conn, machine_ids)

    conn.close()
    print(f"Database built successfully at {MANUFACTURING_DB_PATH}")


if __name__ == "__main__":
    build_database()