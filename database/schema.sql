-- ============================================================
-- schema.sql
--
-- Purpose
-- -------
-- Defines the SQLite schema for a fictional manufacturing
-- company, "Northbridge Precision Manufacturing". It covers
-- plants, production lines, machines, products, work orders,
-- production runs, quality/defect checks, suppliers, raw
-- materials, inventory, and maintenance logs.
--
-- This schema is the target that seed_data.py populates and
-- that the SQL deep agent queries at runtime. Loaded once by
-- database/seed_data.py via sqlite3.executescript().
-- ============================================================

PRAGMA foreign_keys = ON;

-- Physical manufacturing plants/sites
CREATE TABLE IF NOT EXISTS plants (
    plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_name TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    opened_year INTEGER
);

-- Production lines within a plant
CREATE TABLE IF NOT EXISTS production_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL REFERENCES plants(plant_id),
    line_name TEXT NOT NULL,
    line_type TEXT NOT NULL         -- e.g. 'Assembly', 'CNC Machining', 'Welding'
);

-- Machines/equipment installed on a production line
CREATE TABLE IF NOT EXISTS machines (
    machine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id INTEGER NOT NULL REFERENCES production_lines(line_id),
    machine_name TEXT NOT NULL,
    machine_type TEXT NOT NULL,     -- e.g. 'CNC Lathe', 'Robotic Arm', 'Press'
    manufacturer TEXT,
    install_date TEXT,              -- ISO date
    status TEXT NOT NULL DEFAULT 'operational'  -- operational, under_maintenance, decommissioned
);

-- Products manufactured by the company
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    product_category TEXT NOT NULL, -- e.g. 'Automotive Parts', 'Industrial Valves'
    unit_cost REAL NOT NULL,
    unit_price REAL NOT NULL
);

-- Suppliers of raw materials
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    country TEXT NOT NULL,
    reliability_score REAL          -- 0.0 - 1.0, historical on-time delivery rate
);

-- Raw materials, each sourced from one primary supplier
CREATE TABLE IF NOT EXISTS raw_materials (
    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_name TEXT NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    unit TEXT NOT NULL,             -- e.g. 'kg', 'liter', 'unit'
    unit_cost REAL NOT NULL
);

-- Current inventory levels of raw materials at each plant
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL REFERENCES plants(plant_id),
    material_id INTEGER NOT NULL REFERENCES raw_materials(material_id),
    quantity_on_hand REAL NOT NULL,
    reorder_level REAL NOT NULL,
    last_updated TEXT NOT NULL      -- ISO date
);

-- Work orders: a request to produce a quantity of a product on a line
CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    line_id INTEGER NOT NULL REFERENCES production_lines(line_id),
    quantity_ordered INTEGER NOT NULL,
    status TEXT NOT NULL,           -- 'planned', 'in_progress', 'completed', 'cancelled'
    created_date TEXT NOT NULL,
    due_date TEXT NOT NULL
);

-- Production runs: actual execution records tied to a work order
CREATE TABLE IF NOT EXISTS production_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id INTEGER NOT NULL REFERENCES work_orders(work_order_id),
    machine_id INTEGER NOT NULL REFERENCES machines(machine_id),
    start_time TEXT NOT NULL,       -- ISO datetime
    end_time TEXT,                  -- ISO datetime, NULL if still running
    units_produced INTEGER NOT NULL,
    units_defective INTEGER NOT NULL DEFAULT 0,
    downtime_minutes REAL NOT NULL DEFAULT 0
);

-- Quality checks / defect records tied to a production run
CREATE TABLE IF NOT EXISTS quality_checks (
    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES production_runs(run_id),
    check_date TEXT NOT NULL,
    defect_type TEXT,                -- NULL if passed
    severity TEXT,                   -- 'minor', 'major', 'critical', NULL if passed
    inspector TEXT NOT NULL,
    passed INTEGER NOT NULL          -- 1 = passed, 0 = failed
);

-- Maintenance logs for machines
CREATE TABLE IF NOT EXISTS maintenance_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES machines(machine_id),
    maintenance_date TEXT NOT NULL,
    maintenance_type TEXT NOT NULL,  -- 'preventive', 'corrective', 'emergency'
    cost REAL NOT NULL,
    downtime_hours REAL NOT NULL,
    notes TEXT
);

-- Employees (operators, inspectors, technicians)
CREATE TABLE IF NOT EXISTS employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_name TEXT NOT NULL,
    role TEXT NOT NULL,              -- 'Operator', 'Inspector', 'Technician', 'Supervisor'
    plant_id INTEGER NOT NULL REFERENCES plants(plant_id),
    hire_date TEXT NOT NULL
);

-- Helpful indexes for the kinds of aggregate queries the SQL deep agent
-- is expected to run (joins/filters by date range, machine, line, product).
CREATE INDEX IF NOT EXISTS idx_runs_work_order ON production_runs(work_order_id);
CREATE INDEX IF NOT EXISTS idx_runs_machine ON production_runs(machine_id);
CREATE INDEX IF NOT EXISTS idx_runs_start_time ON production_runs(start_time);
CREATE INDEX IF NOT EXISTS idx_quality_run ON quality_checks(run_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_machine ON maintenance_logs(machine_id);
CREATE INDEX IF NOT EXISTS idx_workorders_product ON work_orders(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_plant ON inventory(plant_id);