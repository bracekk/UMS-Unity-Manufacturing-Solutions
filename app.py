from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime, timedelta
import calendar
import math
import os
import json

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")


def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        company TEXT,
        email TEXT UNIQUE,
        password TEXT,
        company_id INTEGER,
        role TEXT NOT NULL DEFAULT 'admin',
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS production_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        order_id INTEGER,
        product_id INTEGER,
        workstation_id INTEGER,
        report_type TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        notes TEXT,
        reported_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (job_id) REFERENCES order_jobs(id),
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (workstation_id) REFERENCES workstations(id),
        FOREIGN KEY (reported_by) REFERENCES users(id)
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        customer TEXT,
        status TEXT,
        due_date TEXT,
        priority TEXT,
        product_id INTEGER,
        quantity REAL DEFAULT 1,
        materials_reserved INTEGER NOT NULL DEFAULT 0,
        company_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT NOT NULL,
        item_name TEXT NOT NULL,
        description TEXT,
        measurement_unit TEXT NOT NULL,
        unit_price REAL NOT NULL DEFAULT 0,
        stock_quantity REAL NOT NULL DEFAULT 0,
        min_stock REAL NOT NULL DEFAULT 0,
        supplier_id INTEGER,
        company_id INTEGER,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL,
        product_name TEXT NOT NULL,
        description TEXT,
        measurement_unit TEXT NOT NULL DEFAULT 'pcs',
        stock_quantity REAL NOT NULL DEFAULT 0,
        time_per_unit REAL NOT NULL DEFAULT 0,
        company_id INTEGER,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL DEFAULT 0,
        quantity REAL NOT NULL,
        component_type TEXT NOT NULL DEFAULT 'item',
        child_product_id INTEGER,
        company_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (child_product_id) REFERENCES products(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dashboard_layouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL,
        page_key TEXT NOT NULL DEFAULT 'dashboard',
        layout_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, company_id, page_key)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workstations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        hours_per_shift REAL NOT NULL DEFAULT 8,
        shifts_per_day INTEGER NOT NULL DEFAULT 1,
        working_days_per_month INTEGER NOT NULL DEFAULT 20,
        color TEXT NOT NULL DEFAULT '#3b82f6',
        company_id INTEGER,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_job_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        workstation_id INTEGER NOT NULL,
        job_name TEXT NOT NULL,
        sequence INTEGER NOT NULL DEFAULT 1,
        estimated_hours REAL NOT NULL DEFAULT 0,
        company_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (workstation_id) REFERENCES workstations(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_job_template_id INTEGER,
        job_product_id INTEGER,
        workstation_id INTEGER NOT NULL,
        job_name TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        planned_quantity REAL NOT NULL,
        completed_quantity REAL NOT NULL DEFAULT 0,
        estimated_hours REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Waiting',
        planned_start TEXT,
        planned_end TEXT,
        parent_job_id INTEGER,
        is_split_child INTEGER NOT NULL DEFAULT 0,
        company_id INTEGER,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (job_product_id) REFERENCES products(id),
        FOREIGN KEY (workstation_id) REFERENCES workstations(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)
        # ---------------------------
    # SUPPLIERS TABLE
    # ---------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        supplier_code TEXT,
        contact_person TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    # ---------------------------
    # PURCHASE REQUESTS TABLE
    # ---------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        request_number TEXT,
        item_id INTEGER,
        supplier_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        quantity REAL NOT NULL,
        unit TEXT,
        status TEXT DEFAULT 'draft',
        priority TEXT DEFAULT 'normal',
        needed_by DATE,
        requested_by INTEGER,
        approved_by INTEGER,
        ordered_by INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (requested_by) REFERENCES users(id)
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dashboard_layouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL,
        page_key TEXT NOT NULL DEFAULT 'dashboard',
        layout_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, company_id, page_key),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    """)

    # Backward-compatible ALTERs for existing DB
    alter_statements = [
        "ALTER TABLE users ADD COLUMN company_id INTEGER",
        "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'admin'",

        "ALTER TABLE orders ADD COLUMN product_id INTEGER",
        "ALTER TABLE orders ADD COLUMN quantity REAL DEFAULT 1",
        "ALTER TABLE orders ADD COLUMN materials_reserved INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN company_id INTEGER",

        "ALTER TABLE items ADD COLUMN stock_quantity REAL NOT NULL DEFAULT 0",
        "ALTER TABLE items ADD COLUMN min_stock REAL NOT NULL DEFAULT 0",
        "ALTER TABLE items ADD COLUMN company_id INTEGER",

        "ALTER TABLE products ADD COLUMN measurement_unit TEXT NOT NULL DEFAULT 'pcs'",
        "ALTER TABLE products ADD COLUMN stock_quantity REAL NOT NULL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN time_per_unit REAL NOT NULL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN company_id INTEGER",

        "ALTER TABLE bom ADD COLUMN component_type TEXT NOT NULL DEFAULT 'item'",
        "ALTER TABLE bom ADD COLUMN child_product_id INTEGER",
        "ALTER TABLE bom ADD COLUMN company_id INTEGER",

        "ALTER TABLE workstations ADD COLUMN color TEXT NOT NULL DEFAULT '#3b82f6'",
        "ALTER TABLE workstations ADD COLUMN company_id INTEGER",

        "ALTER TABLE product_job_templates ADD COLUMN company_id INTEGER",

        "ALTER TABLE order_jobs ADD COLUMN job_product_id INTEGER",
        "ALTER TABLE order_jobs ADD COLUMN planned_start TEXT",
        "ALTER TABLE order_jobs ADD COLUMN planned_end TEXT",
        "ALTER TABLE order_jobs ADD COLUMN parent_job_id INTEGER",
        "ALTER TABLE order_jobs ADD COLUMN is_split_child INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE order_jobs ADD COLUMN company_id INTEGER",
        "ALTER TABLE items ADD COLUMN supplier_id INTEGER",
        "ALTER TABLE production_reports ADD COLUMN unit TEXT DEFAULT 'pcs'",
    ]

    
    try:
        cursor.execute("ALTER TABLE production_reports ADD COLUMN unit TEXT DEFAULT 'pcs'")
    except sqlite3.OperationalError:
        pass

    for sql in alter_statements:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass

    # Backfill companies from old users.company text
    cursor.execute("""
        SELECT DISTINCT TRIM(company)
        FROM users
        WHERE company IS NOT NULL
          AND TRIM(company) != ''
    """)
    company_names = [row[0] for row in cursor.fetchall()]

    for company_name in company_names:
        cursor.execute("""
            INSERT OR IGNORE INTO companies (name)
            VALUES (?)
        """, (company_name,))

    cursor.execute("""
        UPDATE users
        SET company_id = (
            SELECT c.id
            FROM companies c
            WHERE c.name = users.company
        )
        WHERE company_id IS NULL
          AND company IS NOT NULL
          AND TRIM(company) != ''
    """)

    # Backfill core tables if there is exactly one company and old data exists
    cursor.execute("SELECT COUNT(*) FROM companies")
    company_count = cursor.fetchone()[0]

    if company_count == 1:
        cursor.execute("SELECT id FROM companies LIMIT 1")
        default_company_id = cursor.fetchone()[0]

        for table_name in [
            "orders",
            "items",
            "products",
            "bom",
            "workstations",
            "product_job_templates",
            "order_jobs",
        ]:
            cursor.execute(f"""
                UPDATE {table_name}
                SET company_id = ?
                WHERE company_id IS NULL
            """, (default_company_id,))

    conn.commit()
    conn.close()

def seed_data():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM orders")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("SELECT COUNT(*) FROM companies")
        company_count = cursor.fetchone()[0]

        if company_count == 1:
            cursor.execute("SELECT id FROM companies LIMIT 1")
            company_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO orders (order_number, customer, status, due_date, priority, company_id)
                VALUES
                ('ORD-1001', 'NordSteel', 'In Progress', '2026-03-25', 'High', ?),
                ('ORD-1002', 'Baltic Frame', 'Waiting', '2026-03-28', 'Medium', ?),
                ('ORD-1003', 'MetalWorks LT', 'Completed', '2026-03-20', 'Low', ?)
            """, (company_id, company_id, company_id))

    conn.commit()
    conn.close()


def is_logged_in():
    return "user_id" in session

def get_company_id():
    company_id = session.get("company_id")
    if not company_id:
        raise ValueError("Missing company_id in session.")
    return company_id

def get_user_role():
    return session.get("user_role", "user")


def ensure_logged_in():
    if not is_logged_in():
        return redirect(url_for("login"))
    return None


def fetch_one(cursor, query, params=()):
    cursor.execute(query, params)
    return cursor.fetchone()


def company_scope_condition(alias=None):
    column = "company_id" if not alias else f"{alias}.company_id"
    return f"{column} = ?"


def company_params():
    company_id = get_company_id()
    if not company_id:
        raise ValueError("Missing company_id in session.")
    return (company_id,)


def record_belongs_to_company(cursor, table_name, record_id, company_id):
    query = f"SELECT 1 FROM {table_name} WHERE id = ? AND company_id = ?"
    cursor.execute(query, (record_id, company_id))
    return cursor.fetchone() is not None


def require_company_record(cursor, table_name, record_id, company_id, not_found_message="Record not found."):
    if not record_belongs_to_company(cursor, table_name, record_id, company_id):
        raise ValueError(not_found_message)


def redirect_back(default_endpoint="jobs"):
    return redirect(request.referrer or url_for(default_endpoint))

def calculate_job_total_hours(estimated_hours, planned_quantity, completed_quantity=0):
    remaining_quantity = float(planned_quantity or 0) - float(completed_quantity or 0)
    if remaining_quantity < 0:
        remaining_quantity = 0
    return float(estimated_hours or 0) * remaining_quantity


def calculate_job_duration_days(total_job_hours, hours_per_shift, shifts_per_day):
    daily_capacity = float(hours_per_shift or 0) * float(shifts_per_day or 0)
    if daily_capacity <= 0:
        daily_capacity = 8
    if total_job_hours <= 0:
        return 1
    return max(1, math.ceil(total_job_hours / daily_capacity))








def recalculate_job_dates(cursor, job_id, planned_start=None):
    cursor.execute("""
        SELECT
            oj.id,
            oj.estimated_hours,
            oj.planned_quantity,
            oj.completed_quantity,
            oj.planned_start,
            w.hours_per_shift,
            w.shifts_per_day
        FROM order_jobs oj
        JOIN workstations w ON oj.workstation_id = w.id
        WHERE oj.id = ?
    """, (job_id,))
    row = cursor.fetchone()

    if row is None:
        return

    estimated_hours = float(row[1] or 0)
    planned_quantity = float(row[2] or 0)
    completed_quantity = float(row[3] or 0)
    current_planned_start = row[4]
    hours_per_shift = float(row[5] or 0)
    shifts_per_day = float(row[6] or 0)

    start_value = planned_start if planned_start is not None else current_planned_start

    if not start_value:
        cursor.execute("""
            UPDATE order_jobs
            SET planned_start = NULL, planned_end = NULL
            WHERE id = ?
        """, (job_id,))
        return

    total_job_hours = calculate_job_total_hours(
        estimated_hours,
        planned_quantity,
        completed_quantity
    )

    duration_days = calculate_job_duration_days(
        total_job_hours,
        hours_per_shift,
        shifts_per_day
    )

    start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
    end_date = start_date + timedelta(days=duration_days - 1)

    cursor.execute("""
        UPDATE order_jobs
        SET planned_start = ?, planned_end = ?
        WHERE id = ?
    """, (
        start_date.isoformat(),
        end_date.isoformat(),
        job_id
    ))


def build_month_days(year, month):
    days_in_month = calendar.monthrange(year, month)[1]
    month_days = []

    for day in range(1, days_in_month + 1):
        current_date = datetime(year, month, day).date()
        month_days.append({
            "day": day,
            "date": current_date.isoformat(),
            "weekday": current_date.strftime("%a")
        })

    return month_days







def generate_order_jobs_recursive(cursor, order_id, current_product_id, current_quantity, planned_date=None, path=None, company_id=None):
    if path is None:
        path = []

    if company_id is None:
        raise ValueError("company_id is required for job generation.")

    if current_product_id in path:
        raise ValueError("Circular BOM detected.")

    current_path = path + [current_product_id]

    cursor.execute("""
        SELECT child_product_id, quantity
        FROM bom
        WHERE product_id = ?
          AND company_id = ?
          AND component_type = 'product'
          AND child_product_id IS NOT NULL
        ORDER BY id ASC
    """, (current_product_id, company_id))
    child_rows = cursor.fetchall()

    for child_product_id, bom_quantity in child_rows:
        child_required_quantity = float(current_quantity) * float(bom_quantity)
        generate_order_jobs_recursive(
            cursor,
            order_id,
            child_product_id,
            child_required_quantity,
            planned_date,
            current_path,
            company_id
        )

    cursor.execute("""
        SELECT id, workstation_id, job_name, sequence, estimated_hours
        FROM product_job_templates
        WHERE product_id = ?
          AND company_id = ?
        ORDER BY sequence ASC, id ASC
    """, (current_product_id, company_id))
    templates = cursor.fetchall()

    for template_id, workstation_id, job_name, sequence, estimated_hours in templates:
        cursor.execute("""
            INSERT INTO order_jobs (
                order_id,
                product_job_template_id,
                job_product_id,
                workstation_id,
                job_name,
                sequence,
                planned_quantity,
                completed_quantity,
                estimated_hours,
                status,
                planned_start,
                planned_end,
                company_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            template_id,
            current_product_id,
            workstation_id,
            job_name,
            sequence,
            current_quantity,
            0,
            estimated_hours,
            "Waiting",
            planned_date,
            planned_date,
            company_id
        ))

        new_job_id = cursor.lastrowid
        recalculate_job_dates(cursor, new_job_id, planned_date)

def is_float_equal(a, b, tolerance=0.0001):
    return abs(float(a) - float(b)) <= tolerance


def job_has_split_children(cursor, job_id, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        SELECT 1
        FROM order_jobs
        WHERE parent_job_id = ?
          AND is_split_child = 1
          AND company_id = ?
        LIMIT 1
    """, (job_id, company_id))
    return cursor.fetchone() is not None



def sync_parent_job_status(cursor, parent_job_id, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        SELECT id, company_id
        FROM order_jobs
        WHERE id = ?
          AND company_id = ?
    """, (parent_job_id, company_id))
    parent = cursor.fetchone()

    if parent is None:
        return

    cursor.execute("""
        SELECT status, completed_quantity, planned_quantity
        FROM order_jobs
        WHERE parent_job_id = ?
          AND is_split_child = 1
          AND company_id = ?
    """, (parent_job_id, company_id))
    child_rows = cursor.fetchall()

    if not child_rows:
        return

    statuses = [row[0] for row in child_rows]
    all_done = all(status == "Done" for status in statuses)
    any_ongoing = any(status == "Ongoing" for status in statuses)
    any_paused = any(status == "Paused" for status in statuses)
    any_waiting = any(status == "Waiting" for status in statuses)

    total_completed = sum(float(row[1] or 0) for row in child_rows)
    total_planned = sum(float(row[2] or 0) for row in child_rows)

    if all_done:
        new_status = "Done"
    elif any_ongoing:
        new_status = "Ongoing"
    elif any_paused:
        new_status = "Paused"
    elif any_waiting:
        new_status = "Paused"
    else:
        new_status = "Paused"

    cursor.execute("""
        UPDATE order_jobs
        SET completed_quantity = ?, planned_quantity = ?, status = ?
        WHERE id = ?
          AND company_id = ?
    """, (total_completed, total_planned, new_status, parent_job_id, company_id))


def can_start_job(cursor, job_id, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        SELECT order_id, sequence, parent_job_id, is_split_child
        FROM order_jobs
        WHERE id = ?
          AND company_id = ?
    """, (job_id, company_id))
    row = cursor.fetchone()

    if row is None:
        return False

    order_id, sequence, parent_job_id, is_split_child = row

    if parent_job_id:
        cursor.execute("""
            SELECT status
            FROM order_jobs
            WHERE id = ?
              AND company_id = ?
        """, (parent_job_id, company_id))
        parent_row = cursor.fetchone()

        if parent_row and parent_row[0] not in ("Paused", "Ongoing", "Done"):
            return False

    cursor.execute("""
        SELECT COUNT(*)
        FROM order_jobs prev
        WHERE prev.order_id = ?
          AND prev.company_id = ?
          AND prev.sequence < ?
          AND prev.status != 'Done'
          AND (
                prev.is_split_child = 1
                OR NOT EXISTS (
                    SELECT 1
                    FROM order_jobs child
                    WHERE child.parent_job_id = prev.id
                      AND child.is_split_child = 1
                      AND child.company_id = prev.company_id
                )
          )
    """, (order_id, company_id, sequence))
    remaining = cursor.fetchone()[0]

    return remaining == 0


def sync_order_status(cursor, order_id, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        SELECT status
        FROM order_jobs
        WHERE order_id = ?
          AND company_id = ?
    """, (order_id, company_id))
    rows = cursor.fetchall()

    if not rows:
        cursor.execute("""
            UPDATE orders
            SET status = 'Waiting'
            WHERE id = ?
              AND company_id = ?
        """, (order_id, company_id))
        return

    statuses = [row[0] for row in rows]

    if all(status == "Done" for status in statuses):
        order_status = "Completed"
    elif any(status in ("Ongoing", "Paused") for status in statuses):
        order_status = "In Progress"
    else:
        order_status = "Waiting"

    cursor.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
          AND company_id = ?
    """, (order_status, order_id, company_id))


def create_split_children(cursor, parent_job_id, split_rows, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        SELECT
            id,
            order_id,
            product_job_template_id,
            job_product_id,
            workstation_id,
            job_name,
            sequence,
            planned_quantity,
            completed_quantity,
            estimated_hours,
            status,
            planned_start,
            planned_end,
            parent_job_id,
            is_split_child
        FROM order_jobs
        WHERE id = ?
          AND company_id = ?
    """, (parent_job_id, company_id))
    parent = cursor.fetchone()

    if parent is None:
        raise ValueError("Parent job not found.")

    if int(parent[14] or 0) == 1:
        raise ValueError("Split child job cannot be split again.")

    if float(parent[8] or 0) > 0:
        raise ValueError("Cannot split job that already has completed quantity.")

    if job_has_split_children(cursor, parent_job_id, company_id=company_id):
        raise ValueError("Job is already split.")

    parent_planned_quantity = float(parent[7] or 0)
    total_split_quantity = sum(float(row["quantity"]) for row in split_rows)

    if not is_float_equal(total_split_quantity, parent_planned_quantity):
        raise ValueError("Split quantities must match original planned quantity.")

    parent_planned_start = parent[11]

    for row in split_rows:
        workstation_id = int(row["workstation_id"])
        split_quantity = float(row["quantity"])

        require_company_record(cursor, "workstations", workstation_id, company_id, "Workstation not found.")

        cursor.execute("""
            INSERT INTO order_jobs (
                order_id,
                product_job_template_id,
                job_product_id,
                workstation_id,
                job_name,
                sequence,
                planned_quantity,
                completed_quantity,
                estimated_hours,
                status,
                planned_start,
                planned_end,
                parent_job_id,
                is_split_child,
                company_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            parent[1],          # order_id
            parent[2],          # product_job_template_id
            parent[3],          # job_product_id
            workstation_id,
            parent[5],          # job_name
            parent[6],          # sequence
            split_quantity,
            0,
            parent[9],          # estimated_hours
            "Waiting",
            parent_planned_start,
            parent_planned_start,
            parent_job_id,
            1,
            company_id
        ))

        new_child_id = cursor.lastrowid
        recalculate_job_dates(cursor, new_child_id, parent_planned_start)

    cursor.execute("""
        UPDATE order_jobs
        SET status = 'Paused',
            planned_start = NULL,
            planned_end = NULL
        WHERE id = ?
          AND company_id = ?
    """, (parent_job_id, company_id))

    sync_parent_job_status(cursor, parent_job_id, company_id=company_id)


def rebuild_order_jobs(cursor, order_id, root_product_id, root_quantity, planned_date=None, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        DELETE FROM order_jobs
        WHERE order_id = ?
          AND company_id = ?
    """, (order_id, company_id))

    generate_order_jobs_recursive(
        cursor,
        order_id,
        root_product_id,
        root_quantity,
        planned_date,
        company_id=company_id
    )

def get_active_jobs_for_reports(cursor, company_id):
    cursor.execute("""
        SELECT
            oj.id,
            o.order_number,
            COALESCE(p.product_name, '-') AS product_name,
            oj.job_name,
            COALESCE(w.name, '-') AS workstation_name,
            oj.status,
            oj.planned_quantity,
            oj.completed_quantity
        FROM order_jobs oj
        JOIN orders o
          ON oj.order_id = o.id
         AND o.company_id = oj.company_id
        LEFT JOIN products p
          ON oj.job_product_id = p.id
         AND p.company_id = oj.company_id
        LEFT JOIN workstations w
          ON oj.workstation_id = w.id
         AND w.company_id = oj.company_id
        WHERE oj.company_id = ?
          AND oj.status IN ('Waiting', 'Ongoing', 'Paused', 'Delayed')
          AND (
                oj.is_split_child = 1
                OR NOT EXISTS (
                    SELECT 1
                    FROM order_jobs child
                    WHERE child.parent_job_id = oj.id
                      AND child.is_split_child = 1
                      AND child.company_id = oj.company_id
                )
          )
        ORDER BY o.order_number ASC, oj.sequence ASC, oj.id ASC
    """, (company_id,))

    rows = cursor.fetchall()

    active_jobs = []
    for row in rows:
        active_jobs.append({
            "id": row[0],
            "order_number": row[1],
            "product_name": row[2],
            "job_name": row[3],
            "workstation_name": row[4],
            "status": row[5],
            "planned_quantity": float(row[6] or 0),
            "completed_quantity": float(row[7] or 0),
        })

    return active_jobs

def explode_bom_items_recursive(cursor, product_id, required_quantity, collected=None, path=None, company_id=None):
    if collected is None:
        collected = {}

    if path is None:
        path = []

    if company_id is None:
        raise ValueError("company_id is required.")

    if product_id in path:
        raise ValueError("Circular BOM detected.")

    current_path = path + [product_id]

    cursor.execute("""
        SELECT
            component_type,
            item_id,
            child_product_id,
            quantity
        FROM bom
        WHERE product_id = ?
          AND company_id = ?
        ORDER BY id ASC
    """, (product_id, company_id))
    rows = cursor.fetchall()

    for component_type, item_id, child_product_id, bom_quantity in rows:
        bom_quantity = float(bom_quantity or 0)
        total_required = float(required_quantity) * bom_quantity

        if component_type == "product" and child_product_id:
            explode_bom_items_recursive(
                cursor,
                child_product_id,
                total_required,
                collected,
                current_path,
                company_id
            )
        else:
            if item_id not in collected:
                collected[item_id] = 0
            collected[item_id] += total_required

    return collected




def split_parent_exclusion_sql(alias="oj"):
    return f"""
        NOT EXISTS (
            SELECT 1
            FROM order_jobs child
            WHERE child.parent_job_id = {alias}.id
              AND child.is_split_child = 1
              AND child.company_id = {alias}.company_id
        )
    """





def consume_job_materials(cursor, product_id, produced_quantity, company_id=None):
    produced_quantity = float(produced_quantity or 0)

    if company_id is None:
        raise ValueError("company_id is required.")

    if not product_id or produced_quantity <= 0:
        return

    exploded_items = explode_bom_items_recursive(
        cursor,
        product_id,
        produced_quantity,
        company_id=company_id
    )

    for item_id, required_quantity in exploded_items.items():
        cursor.execute("""
            UPDATE items
            SET stock_quantity = COALESCE(stock_quantity, 0) - ?
            WHERE id = ?
              AND company_id = ?
        """, (float(required_quantity or 0), item_id, company_id))

def add_finished_product_stock(cursor, product_id, produced_quantity, company_id=None):
    produced_quantity = float(produced_quantity or 0)

    if company_id is None:
        raise ValueError("company_id is required.")

    if not product_id or produced_quantity <= 0:
        return

    cursor.execute("""
        UPDATE products
        SET stock_quantity = COALESCE(stock_quantity, 0) + ?
        WHERE id = ?
          AND company_id = ?
    """, (produced_quantity, product_id, company_id))

def is_final_job(cursor, order_id, job_id, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        SELECT MAX(sequence)
        FROM order_jobs
        WHERE order_id = ?
          AND company_id = ?
    """, (order_id, company_id))
    max_sequence = cursor.fetchone()[0]

    cursor.execute("""
        SELECT sequence
        FROM order_jobs
        WHERE id = ?
          AND company_id = ?
    """, (job_id, company_id))
    row = cursor.fetchone()

    if row is None:
        return False

    job_sequence = row[0]
    return job_sequence == max_sequence


def reserve_order_materials(cursor, order_id, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    cursor.execute("""
        SELECT 1
        FROM orders
        WHERE id = ?
          AND company_id = ?
        LIMIT 1
    """, (order_id, company_id))
    exists = cursor.fetchone()

    if not exists:
        raise ValueError("Order not found.")

    # Orders currently do not reserve stock.
    # Kept for compatibility and future extension.
    return False






def calculate_product_material_cost(cursor, product_id, company_id=None):
    if company_id is None:
        raise ValueError("company_id is required.")

    try:
        exploded_items = explode_bom_items_recursive(
            cursor,
            product_id,
            1,
            company_id=company_id
        )
    except ValueError:
        return 0

    if not exploded_items:
        return 0

    item_ids = list(exploded_items.keys())
    placeholders = ",".join(["?"] * len(item_ids))

    cursor.execute(f"""
        SELECT id, unit_price
        FROM items
        WHERE id IN ({placeholders})
          AND company_id = ?
    """, item_ids + [company_id])
    rows = cursor.fetchall()

    total_material_cost = 0

    for item_id, unit_price in rows:
        quantity_per_unit = exploded_items.get(item_id, 0)
        total_material_cost += quantity_per_unit * (unit_price or 0)

    return total_material_cost


from functools import wraps

ROLE_DEFAULT_PERMISSIONS = {
    "admin": {
        "view_dashboard",
        "view_orders", "manage_orders",
        "view_jobs", "update_job_progress", "manage_jobs",
        "view_inventory", "manage_inventory",
        "view_products", "manage_products",
        "view_items", "manage_items",
        "view_workstations", "manage_workstations",
        "view_reports", "export_data",
        "manage_users",
        "manage_procurement",
        "view_suppliers",
        "manage_suppliers",
        "view_procurement",
        "manage_procurement",
    },
    "manager": {
        "view_dashboard",
        "view_orders", "manage_orders",
        "view_jobs", "update_job_progress", "manage_jobs",
        "view_inventory", "manage_inventory",
        "view_products", "manage_products",
        "view_items", "manage_items",
        "view_workstations", "manage_workstations",
        "view_reports", "export_data",
        "manage_procurement",
        "view_suppliers",
        "manage_suppliers",
        "view_procurement",
    },
    "worker": {
        "view_dashboard",
        "view_jobs",
        "update_job_progress",
        "view_procurement",
    },
}

ALL_PERMISSION_KEYS = [
    "view_dashboard",
    "view_orders",
    "manage_orders",
    "view_jobs",
    "update_job_progress",
    "manage_jobs",
    "view_inventory",
    "manage_inventory",
    "view_products",
    "manage_products",
    "view_items",
    "manage_items",
    "view_workstations",
    "manage_workstations",
    "view_reports",
    "export_data",
    "manage_users",
    "manage_procurement",
    "view_suppliers",
    "manage_suppliers",
    "view_procurement",
    "manage_procurement",
]


def get_current_user_role():
    return (session.get("user_role") or "worker").strip().lower()


def get_role_default_permissions(role):
    return set(ROLE_DEFAULT_PERMISSIONS.get((role or "worker").lower(), set()))


def get_user_permission_overrides(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT permission_key, allowed
        FROM user_permissions
        WHERE user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    overrides = {}
    for permission_key, allowed in rows:
        overrides[permission_key] = bool(allowed)

    return overrides


def get_effective_permissions(user_id=None, role=None):
    if user_id is None:
        user_id = session.get("user_id")
    if role is None:
        role = get_current_user_role()

    permissions = set(get_role_default_permissions(role))
    overrides = get_user_permission_overrides(user_id)

    for permission_key, allowed in overrides.items():
        if allowed:
            permissions.add(permission_key)
        else:
            permissions.discard(permission_key)

    return permissions


def has_permission(permission_key, user_id=None, role=None):
    return permission_key in get_effective_permissions(user_id=user_id, role=role)


def get_dashboard_layout(cursor, user_id, company_id, page_key="dashboard"):
    cursor.execute("""
        SELECT layout_json
        FROM dashboard_layouts
        WHERE user_id = ? AND company_id = ? AND page_key = ?
        LIMIT 1
    """, (user_id, company_id, page_key))

    row = cursor.fetchone()

    if not row:
        return []

    try:
        return json.loads(row[0])
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def save_dashboard_layout_record(cursor, user_id, company_id, layout_state, page_key="dashboard"):
    cursor.execute("""
        INSERT INTO dashboard_layouts (user_id, company_id, page_key, layout_json, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, company_id, page_key)
        DO UPDATE SET
            layout_json = excluded.layout_json,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, company_id, page_key, json.dumps(layout_state)))

def permission_required(permission_key):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not is_logged_in():
                return redirect(url_for("login"))

            if not has_permission(permission_key):
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for("dashboard"))

            return view_func(*args, **kwargs)
        return wrapped_view
    return decorator


@app.context_processor
def inject_permissions():
    if not session.get("user_id"):
        return {
            "current_user_role": None,
            "effective_permissions": set(),
            "has_permission_ui": lambda permission_key: False,
            "all_permission_keys": ALL_PERMISSION_KEYS,
        }

    effective_permissions = get_effective_permissions()

    return {
        "current_user_role": get_current_user_role(),
        "effective_permissions": effective_permissions,
        "has_permission_ui": lambda permission_key: permission_key in effective_permissions,
        "all_permission_keys": ALL_PERMISSION_KEYS,
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/landing")
def landing():
    return render_template("index.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, full_name, email, password, company_id, role
            FROM users
            WHERE email = ?
        """, (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            if not user[4]:
                flash("This account is not linked to a company.", "error")
                return render_template("login.html", error="This account is not linked to a company.")

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_email"] = user[2]
            session["company_id"] = user[4]
            session["user_role"] = user[5] or "user"

            return redirect(url_for("dashboard"))

        flash("Invalid email or password", "error")
        return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        company_name = request.form["company"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not full_name or not company_name or not email or not password:
            return render_template("register.html", error="All fields are required")

        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT id FROM users WHERE email = ?
            """, (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                conn.close()
                flash("Email already exists.", "error")
                return render_template("register.html", error="Email already exists")

            cursor.execute("""
                INSERT INTO companies (name)
                VALUES (?)
            """, (company_name,))
            company_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO users (full_name, company, email, password, company_id, role)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (full_name, company_name, email, hashed_password, company_id, "admin"))

            conn.commit()
            conn.close()

            flash("Account created successfully. You can now log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            flash("Company or email already exists.", "error")
            return render_template("register.html", error="Company or email already exists")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE company_id = ?
    """, (company_id,))
    total_orders = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'Waiting' AND company_id = ?
    """, (company_id,))
    waiting_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'Completed' AND company_id = ?
    """, (company_id,))
    completed_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'In Progress' AND company_id = ?
    """, (company_id,))
    in_progress_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM order_jobs
        WHERE status = 'Delayed' AND company_id = ?
    """, (company_id,))
    delayed_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            o.id,
            o.order_number,
            COALESCE(p.product_name, '-') AS product_name,
            o.quantity,
            o.status,
            o.due_date
        FROM orders o
        LEFT JOIN products p
          ON o.product_id = p.id
         AND p.company_id = o.company_id
        WHERE o.company_id = ?
        ORDER BY o.id DESC
        LIMIT 10
    """, (company_id,))
    order_rows = cursor.fetchall()

    recent_orders = []
    for row in order_rows:
        recent_orders.append({
            "id": row[0],
            "order_number": row[1],
            "product_name": row[2],
            "quantity": row[3],
            "status": row[4],
            "due_date": row[5]
        })

    cursor.execute("""
        SELECT
            w.id,
            w.name,
            (w.hours_per_shift * w.shifts_per_day * w.working_days_per_month) AS monthly_capacity,
            IFNULL((
                SELECT SUM(
                    oj.estimated_hours *
                    CASE
                        WHEN (oj.planned_quantity - oj.completed_quantity) < 0 THEN 0
                        ELSE (oj.planned_quantity - oj.completed_quantity)
                    END
                )
                FROM order_jobs oj
                WHERE oj.workstation_id = w.id
                AND oj.company_id = w.company_id
                AND oj.status != 'Done'
                AND (
                        oj.status = 'Waiting'
                        OR oj.status = 'Ongoing'
                        OR oj.status = 'Paused'
                        OR oj.status = 'Delayed'
                )
                AND (
                        oj.is_split_child = 1
                        OR NOT EXISTS (
                            SELECT 1
                            FROM order_jobs child
                            WHERE child.parent_job_id = oj.id
                            AND child.is_split_child = 1
                            AND child.company_id = oj.company_id
                        )
                )
            ), 0) AS used_load
        FROM workstations w
        WHERE w.company_id = ?
        ORDER BY w.name ASC
    """, (company_id,))
    workstation_rows = cursor.fetchall()

    workstation_load = []
    for row in workstation_rows:
        monthly_capacity = float(row[2] or 0)
        used_load = float(row[3] or 0)
        load_percent = round((used_load / monthly_capacity) * 100) if monthly_capacity > 0 else 0

        workstation_load.append({
            "id": row[0],
            "name": row[1],
            "monthly_capacity": round(monthly_capacity, 2),
            "used_load": round(used_load, 2),
            "load_percent": load_percent
        })

    saved_dashboard_layout = get_dashboard_layout(cursor, user_id, company_id, "dashboard")

    conn.close()

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        total_orders=total_orders,
        waiting_count=waiting_count,
        completed_count=completed_count,
        in_progress_count=in_progress_count,
        delayed_count=delayed_count,
        recent_orders=recent_orders,
        workstation_load=workstation_load,
        saved_dashboard_layout=saved_dashboard_layout
    )


@app.route("/orders")
@permission_required("view_orders")
def orders():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    order_number = request.args.get("order_number", "").strip()
    product_name = request.args.get("product_name", "").strip()
    statuses = request.args.getlist("status")
    priority = request.args.get("priority", "").strip()
    due_date_from = request.args.get("due_date_from", "").strip()
    due_date_to = request.args.get("due_date_to", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT
            o.id,
            o.order_number,
            p.product_name,
            o.quantity,
            o.status,
            o.due_date,
            o.priority
        FROM orders o
        LEFT JOIN products p
          ON o.product_id = p.id
         AND p.company_id = o.company_id
        WHERE o.company_id = ?
    """

    params = [company_id]

    if order_number:
        query += " AND o.order_number LIKE ?"
        params.append(f"%{order_number}%")

    if product_name:
        query += " AND p.product_name LIKE ?"
        params.append(f"%{product_name}%")

    if statuses and "All" not in statuses:
        placeholders = ",".join(["?"] * len(statuses))
        query += f" AND o.status IN ({placeholders})"
        params.extend(statuses)

    if priority:
        query += " AND o.priority = ?"
        params.append(priority)

    if due_date_from:
        query += " AND o.due_date >= ?"
        params.append(due_date_from)

    if due_date_to:
        query += " AND o.due_date <= ?"
        params.append(due_date_to)

    query += " ORDER BY o.id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    orders = []
    for row in rows:
        orders.append({
            "id": row[0],
            "order_number": row[1],
            "product_name": row[2] if row[2] else "-",
            "quantity": row[3],
            "status": row[4],
            "due_date": row[5],
            "priority": row[6]
        })

    return render_template(
        "orders.html",
        orders=orders,
        active_page="orders",
        filters={
            "order_number": order_number,
            "product_name": product_name,
            "status": statuses,
            "priority": priority,
            "due_date_from": due_date_from,
            "due_date_to": due_date_to
        }
    )


@app.route("/orders/new", methods=["GET", "POST"])
@permission_required("manage_orders")
def new_order():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        order_number = request.form["order_number"].strip()
        product_id_raw = request.form.get("product_id", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()
        status = request.form["status"].strip()
        due_date = request.form["due_date"].strip()
        priority = request.form["priority"].strip()

        if not product_id_raw:
            conn.close()
            flash("No product selected. Create a product first or choose an existing one.", "error")
            return redirect(url_for("new_order"))

        try:
            product_id = int(product_id_raw)
            quantity = float(quantity_raw)
        except ValueError:
            conn.close()
            flash("Invalid product or quantity.", "error")
            return redirect(url_for("new_order"))

        cursor.execute("""
            SELECT id
            FROM products
            WHERE id = ? AND company_id = ?
        """, (product_id, company_id))
        product_row = cursor.fetchone()

        if product_row is None:
            conn.close()
            flash("Selected product was not found in your current company.", "error")
            return redirect(url_for("new_order"))

        cursor.execute("""
            INSERT INTO orders (
                order_number,
                product_id,
                quantity,
                status,
                due_date,
                priority,
                company_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            order_number,
            product_id,
            quantity,
            status,
            due_date,
            priority,
            company_id
        ))

        order_id = cursor.lastrowid

        generate_order_jobs_recursive(
            cursor,
            order_id,
            product_id,
            quantity,
            planned_date=None,
            company_id=company_id
        )

        conn.commit()
        conn.close()

        flash("Order created successfully.", "success")
        return redirect(url_for("orders"))

    cursor.execute("""
        SELECT id, product_code, product_name
        FROM products
        WHERE company_id = ?
        ORDER BY product_name ASC, product_code ASC
    """, (company_id,))
    products = cursor.fetchall()

    conn.close()

    return render_template(
        "new_order.html",
        products=products,
        active_page="orders"
    )


@app.route("/orders/edit/<int:order_id>", methods=["GET", "POST"])
def edit_order(order_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, order_number, product_id, quantity, status, due_date, priority
        FROM orders
        WHERE id = ? AND company_id = ?
    """, (order_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return "Order not found", 404

    if request.method == "POST":
        order_number = request.form["order_number"].strip()
        product_id = int(request.form["product_id"])
        quantity = float(request.form["quantity"])
        status = request.form["status"].strip()
        due_date = request.form["due_date"].strip()
        priority = request.form["priority"].strip()

        try:
            require_company_record(cursor, "products", product_id, company_id, "Product not found.")

            cursor.execute("""
                UPDATE orders
                SET order_number = ?, product_id = ?, quantity = ?, status = ?, due_date = ?, priority = ?
                WHERE id = ? AND company_id = ?
            """, (order_number, product_id, quantity, status, due_date, priority, order_id, company_id))

            rebuild_order_jobs(
                cursor,
                order_id,
                int(product_id),
                quantity,
                due_date,
                company_id=company_id
            )

            conn.commit()
            conn.close()

            flash("Order updated successfully.", "success")
            return redirect(url_for("orders"))
        except ValueError as e:
            conn.rollback()
            conn.close()
            flash(str(e), "error")
            return redirect(url_for("edit_order", order_id=order_id))

    order = {
        "id": row[0],
        "order_number": row[1],
        "product_id": row[2],
        "quantity": row[3] if row[3] is not None else 1,
        "status": row[4],
        "due_date": row[5],
        "priority": row[6]
    }

    cursor.execute("""
        SELECT id, product_code, product_name
        FROM products
        WHERE company_id = ?
        ORDER BY product_name ASC
    """, (company_id,))
    products = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_order.html",
        order=order,
        products=products,
        active_page="orders"
    )


@app.route("/orders/<int:order_id>/materials")
def order_materials(order_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            o.id,
            o.order_number,
            o.quantity,
            p.id,
            p.product_name
        FROM orders o
        JOIN products p
          ON o.product_id = p.id
         AND p.company_id = o.company_id
        WHERE o.id = ? AND o.company_id = ?
    """, (order_id, company_id))

    order = cursor.fetchone()

    if not order:
        conn.close()
        return redirect(url_for("orders"))

    product_id = order[3]
    order_quantity = float(order[2] or 0)

    # BOM kiekis vienam produkto vienetui
    per_unit_exploded = explode_bom_items_recursive(
        cursor,
        product_id,
        1,
        company_id=company_id
    )

    # BOM kiekis visam užsakymui
    total_exploded = explode_bom_items_recursive(
        cursor,
        product_id,
        order_quantity,
        company_id=company_id
    )

    materials = []
    total_material_cost = 0

    item_ids = list(total_exploded.keys())

    if item_ids:
        placeholders = ",".join(["?"] * len(item_ids))
        cursor.execute(f"""
            SELECT id, item_name, item_code, measurement_unit, unit_price
            FROM items
            WHERE id IN ({placeholders}) AND company_id = ?
            ORDER BY item_name ASC
        """, item_ids + [company_id])

        for item_id, item_name, item_code, measurement_unit, unit_price in cursor.fetchall():
            bom_quantity = float(per_unit_exploded.get(item_id, 0) or 0)
            total_quantity = float(total_exploded.get(item_id, 0) or 0)
            unit_price = float(unit_price or 0)
            total_cost = total_quantity * unit_price
            total_material_cost += total_cost

            materials.append({
                "item_name": item_name,
                "item_code": item_code,
                "unit": measurement_unit,
                "bom_quantity": bom_quantity,
                "total_quantity": total_quantity,
                "unit_price": unit_price,
                "total_cost": total_cost
            })

    conn.close()

    return render_template(
        "order_materials.html",
        order={
            "order_number": order[1],
            "quantity": order_quantity,
            "product_name": order[4]
        },
        materials=materials,
        total_material_cost=total_material_cost,
        active_page="orders"
    )

@app.route("/orders/delete/<int:order_id>", methods=["POST"])
def delete_order(order_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # security check
    require_company_record(cursor, "orders", order_id, company_id)

    cursor.execute("""
        DELETE FROM order_jobs
        WHERE order_id = ? AND company_id = ?
    """, (order_id, company_id))

    cursor.execute("""
        DELETE FROM orders
        WHERE id = ? AND company_id = ?
    """, (order_id, company_id))

    conn.commit()
    conn.close()

    return redirect(url_for("orders"))


@app.route("/items")
def items():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    item_code = request.args.get("item_code", "").strip()
    item_name = request.args.get("item_name", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            item_code,
            item_name,
            description,
            measurement_unit,
            unit_price,
            stock_quantity,
            min_stock
        FROM items
        WHERE company_id = ?
    """
    params = [company_id]

    if item_code:
        query += " AND item_code LIKE ?"
        params.append(f"%{item_code}%")

    if item_name:
        query += " AND item_name LIKE ?"
        params.append(f"%{item_name}%")

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "item_code": row[1],
            "item_name": row[2],
            "description": row[3],
            "measurement_unit": row[4],
            "unit_price": row[5] if row[5] is not None else 0,
            "stock_quantity": row[6] if row[6] is not None else 0,
            "min_stock": row[7] if row[7] is not None else 0
        })

    filters = {
        "item_code": item_code,
        "item_name": item_name
    }

    return render_template(
        "items.html",
        items=items,
        filters=filters,
        active_page="items"
    )


@app.route("/items/new", methods=["GET", "POST"])
def new_item():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        item_code = request.form["item_code"].strip()
        item_name = request.form["item_name"].strip()
        description = request.form["description"].strip()
        measurement_unit = request.form["measurement_unit"].strip()
        unit_price = float(request.form["unit_price"] or 0)
        stock_quantity = float(request.form["stock_quantity"] or 0)
        min_stock = float(request.form["min_stock"] or 0)
        supplier_id_raw = request.form.get("supplier_id", "").strip()

        supplier_id = None
        if supplier_id_raw:
            try:
                supplier_id = int(supplier_id_raw)
            except ValueError:
                conn.close()
                flash("Invalid supplier selected.", "error")
                return redirect(url_for("new_item"))

            cursor.execute("""
                SELECT id
                FROM suppliers
                WHERE id = ? AND company_id = ?
            """, (supplier_id, company_id))
            supplier_row = cursor.fetchone()

            if supplier_row is None:
                conn.close()
                flash("Selected supplier not found.", "error")
                return redirect(url_for("new_item"))

        cursor.execute("""
            INSERT INTO items (
                item_code,
                item_name,
                description,
                measurement_unit,
                unit_price,
                stock_quantity,
                min_stock,
                supplier_id,
                company_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_code,
            item_name,
            description,
            measurement_unit,
            unit_price,
            stock_quantity,
            min_stock,
            supplier_id,
            company_id
        ))

        conn.commit()
        conn.close()

        flash("Item created successfully.", "success")
        return redirect(url_for("items"))

    cursor.execute("""
        SELECT id, name
        FROM suppliers
        WHERE company_id = ? AND is_active = 1
        ORDER BY name ASC
    """, (company_id,))
    suppliers = cursor.fetchall()

    conn.close()

    return render_template(
        "new_item.html",
        suppliers=suppliers,
        active_page="items"
    )


@app.route("/items/edit/<int:item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "items", item_id, company_id, "Item not found.")

        if request.method == "POST":
            item_code = request.form["item_code"].strip()
            item_name = request.form["item_name"].strip()
            description = request.form["description"].strip()
            measurement_unit = request.form["measurement_unit"].strip()
            unit_price = float(request.form["unit_price"] or 0)
            stock_quantity = float(request.form["stock_quantity"] or 0)
            min_stock = float(request.form["min_stock"] or 0)
            supplier_id_raw = request.form.get("supplier_id", "").strip()

            supplier_id = None
            if supplier_id_raw:
                try:
                    supplier_id = int(supplier_id_raw)
                except ValueError:
                    conn.close()
                    flash("Invalid supplier selected.", "error")
                    return redirect(url_for("edit_item", item_id=item_id))

                cursor.execute("""
                    SELECT id
                    FROM suppliers
                    WHERE id = ? AND company_id = ?
                """, (supplier_id, company_id))
                supplier_row = cursor.fetchone()

                if supplier_row is None:
                    conn.close()
                    flash("Selected supplier not found.", "error")
                    return redirect(url_for("edit_item", item_id=item_id))

            cursor.execute("""
                UPDATE items
                SET item_code = ?, item_name = ?, description = ?, measurement_unit = ?,
                    unit_price = ?, stock_quantity = ?, min_stock = ?, supplier_id = ?
                WHERE id = ? AND company_id = ?
            """, (
                item_code,
                item_name,
                description,
                measurement_unit,
                unit_price,
                stock_quantity,
                min_stock,
                supplier_id,
                item_id,
                company_id
            ))

            conn.commit()
            conn.close()

            flash("Item updated successfully.", "success")
            return redirect(url_for("items"))

        cursor.execute("""
            SELECT
                id,
                item_code,
                item_name,
                description,
                measurement_unit,
                unit_price,
                stock_quantity,
                min_stock,
                supplier_id
            FROM items
            WHERE id = ? AND company_id = ?
        """, (item_id, company_id))
        row = cursor.fetchone()

        cursor.execute("""
            SELECT id, name
            FROM suppliers
            WHERE company_id = ? AND is_active = 1
            ORDER BY name ASC
        """, (company_id,))
        supplier_rows = cursor.fetchall()

        conn.close()

        item = {
            "id": row[0],
            "item_code": row[1],
            "item_name": row[2],
            "description": row[3],
            "measurement_unit": row[4],
            "unit_price": row[5] if row[5] is not None else 0,
            "stock_quantity": row[6] if row[6] is not None else 0,
            "min_stock": row[7] if row[7] is not None else 0,
            "supplier_id": row[8]
        }

        return render_template(
            "edit_item.html",
            item=item,
            suppliers=supplier_rows,
            active_page="items"
        )
    except ValueError:
        conn.close()
        return "Item not found", 404


@app.route("/items/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "items", item_id, company_id, "Item not found.")

        cursor.execute("""
            DELETE FROM bom
            WHERE item_id = ? AND company_id = ?
        """, (item_id, company_id))

        cursor.execute("""
            DELETE FROM items
            WHERE id = ? AND company_id = ?
        """, (item_id, company_id))

        conn.commit()
        conn.close()

        flash("Item deleted successfully.", "info")
        return redirect(url_for("items"))
    except ValueError:
        conn.close()
        flash("Item not found.", "error")
        return redirect(url_for("items"))


@app.route("/products")
def products():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    product_code = request.args.get("product_code", "").strip()
    product_name = request.args.get("product_name", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            product_code,
            product_name,
            description,
            measurement_unit,
            time_per_unit,
            stock_quantity
        FROM products
        WHERE company_id = ?
    """
    params = [company_id]

    if product_code:
        query += " AND product_code LIKE ?"
        params.append(f"%{product_code}%")

    if product_name:
        query += " AND product_name LIKE ?"
        params.append(f"%{product_name}%")

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    products = []
    for row in rows:
        products.append({
            "id": row[0],
            "product_code": row[1],
            "product_name": row[2],
            "description": row[3],
            "measurement_unit": row[4],
            "time_per_unit": row[5] if row[5] is not None else 0,
            "stock_quantity": row[6] if row[6] is not None else 0
        })

    filters = {
        "product_code": product_code,
        "product_name": product_name
    }

    return render_template(
        "products.html",
        products=products,
        filters=filters,
        active_page="products"
    )


@app.route("/products/new", methods=["GET", "POST"])
def new_product():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    if request.method == "POST":
        product_code = request.form["product_code"].strip()
        product_name = request.form["product_name"].strip()
        description = request.form["description"].strip()
        measurement_unit = request.form["measurement_unit"].strip()
        time_per_unit = float(request.form["time_per_unit"] or 0)
        stock_quantity = float(request.form["stock_quantity"] or 0)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO products (
                product_code,
                product_name,
                description,
                measurement_unit,
                time_per_unit,
                stock_quantity,
                company_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            product_code,
            product_name,
            description,
            measurement_unit,
            time_per_unit,
            stock_quantity,
            company_id
        ))

        conn.commit()
        conn.close()

        flash("Product created successfully.", "success")
        return redirect(url_for("products"))

    return render_template(
        "new_product.html",
        active_page="products"
    )


@app.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "products", product_id, company_id, "Product not found.")

        if request.method == "POST":
            product_code = request.form["product_code"].strip()
            product_name = request.form["product_name"].strip()
            description = request.form["description"].strip()
            measurement_unit = request.form["measurement_unit"].strip()
            time_per_unit = float(request.form["time_per_unit"] or 0)
            stock_quantity = float(request.form["stock_quantity"] or 0)

            cursor.execute("""
                UPDATE products
                SET product_code = ?, product_name = ?, description = ?, measurement_unit = ?, time_per_unit = ?, stock_quantity = ?
                WHERE id = ? AND company_id = ?
            """, (
                product_code,
                product_name,
                description,
                measurement_unit,
                time_per_unit,
                stock_quantity,
                product_id,
                company_id
            ))

            conn.commit()
            conn.close()

            flash("Product updated successfully.", "success")
            return redirect(url_for("products"))

        cursor.execute("""
            SELECT
                id,
                product_code,
                product_name,
                description,
                measurement_unit,
                time_per_unit,
                stock_quantity
            FROM products
            WHERE id = ? AND company_id = ?
        """, (product_id, company_id))
        row = cursor.fetchone()
        conn.close()

        product = {
            "id": row[0],
            "product_code": row[1],
            "product_name": row[2],
            "description": row[3],
            "measurement_unit": row[4],
            "time_per_unit": row[5] if row[5] is not None else 0,
            "stock_quantity": row[6] if row[6] is not None else 0
        }

        return render_template(
            "edit_product.html",
            product=product,
            active_page="products"
        )
    except ValueError:
        conn.close()
        return "Product not found", 404


@app.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "products", product_id, company_id, "Product not found.")

        cursor.execute("""
            DELETE FROM bom
            WHERE product_id = ? AND company_id = ?
        """, (product_id, company_id))

        cursor.execute("""
            DELETE FROM bom
            WHERE child_product_id = ? AND company_id = ?
        """, (product_id, company_id))

        cursor.execute("""
            DELETE FROM product_job_templates
            WHERE product_id = ? AND company_id = ?
        """, (product_id, company_id))

        cursor.execute("""
            DELETE FROM products
            WHERE id = ? AND company_id = ?
        """, (product_id, company_id))

        conn.commit()
        conn.close()

        flash("Product deleted successfully.", "info")
        return redirect(url_for("products"))
    except ValueError:
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("products"))

@app.route("/products/<int:product_id>/jobs")
def product_jobs(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_code, product_name, description, measurement_unit, time_per_unit
        FROM products
        WHERE id = ? AND company_id = ?
    """, (product_id, company_id))
    product_row = cursor.fetchone()

    if product_row is None:
        conn.close()
        return "Product not found", 404

    product = {
        "id": product_row[0],
        "product_code": product_row[1],
        "product_name": product_row[2],
        "description": product_row[3],
        "measurement_unit": product_row[4],
        "time_per_unit": product_row[5]
    }

    cursor.execute("""
        SELECT
            pjt.id,
            pjt.job_name,
            pjt.sequence,
            pjt.estimated_hours,
            pjt.workstation_id,
            w.name
        FROM product_job_templates pjt
        JOIN workstations w
          ON pjt.workstation_id = w.id
         AND w.company_id = pjt.company_id
        WHERE pjt.product_id = ?
          AND pjt.company_id = ?
        ORDER BY pjt.sequence ASC, pjt.id ASC
    """, (product_id, company_id))
    rows = cursor.fetchall()

    job_templates = []
    for row in rows:
        job_templates.append({
            "id": row[0],
            "job_name": row[1],
            "sequence": row[2],
            "estimated_hours": row[3],
            "workstation_id": row[4],
            "workstation_name": row[5]
        })

    cursor.execute("""
        SELECT id, name
        FROM workstations
        WHERE company_id = ?
        ORDER BY name ASC
    """, (company_id,))
    workstation_rows = cursor.fetchall()

    workstations = [{"id": row[0], "name": row[1]} for row in workstation_rows]

    conn.close()

    return render_template(
        "product_jobs.html",
        product=product,
        job_templates=job_templates,
        workstations=workstations,
        active_page="products"
    )


@app.route("/products/<int:product_id>/jobs/add", methods=["POST"])
def add_product_job(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    job_name = request.form["job_name"].strip()
    workstation_id = int(request.form["workstation_id"])
    sequence = int(request.form["sequence"])
    estimated_hours = float(request.form["estimated_hours"] or 0)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "products", product_id, company_id, "Product not found.")
        require_company_record(cursor, "workstations", workstation_id, company_id, "Workstation not found.")

        cursor.execute("""
            INSERT INTO product_job_templates (
                product_id,
                workstation_id,
                job_name,
                sequence,
                estimated_hours,
                company_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, workstation_id, job_name, sequence, estimated_hours, company_id))

        conn.commit()
        conn.close()

        flash("Product job template added successfully.", "success")
        return redirect(url_for("product_jobs", product_id=product_id))
    except ValueError as e:
        conn.close()
        flash(str(e), "error")
        return redirect(url_for("product_jobs", product_id=product_id))


@app.route("/products/jobs/edit/<int:job_id>", methods=["GET", "POST"])
def edit_product_job(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_id, workstation_id, job_name, sequence, estimated_hours
        FROM product_job_templates
        WHERE id = ? AND company_id = ?
    """, (job_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return "Product job template not found", 404

    if request.method == "POST":
        job_name = request.form["job_name"].strip()
        workstation_id = int(request.form["workstation_id"])
        sequence = int(request.form["sequence"])
        estimated_hours = float(request.form["estimated_hours"] or 0)

        try:
            require_company_record(cursor, "workstations", workstation_id, company_id, "Workstation not found.")

            cursor.execute("""
                UPDATE product_job_templates
                SET job_name = ?, workstation_id = ?, sequence = ?, estimated_hours = ?
                WHERE id = ? AND company_id = ?
            """, (job_name, workstation_id, sequence, estimated_hours, job_id, company_id))

            conn.commit()
            product_id = row[1]
            conn.close()

            flash("Product job template updated successfully.", "success")
            return redirect(url_for("product_jobs", product_id=product_id))
        except ValueError as e:
            conn.close()
            flash(str(e), "error")
            return redirect(url_for("product_jobs", product_id=row[1]))

    job_template = {
        "id": row[0],
        "product_id": row[1],
        "workstation_id": row[2],
        "job_name": row[3],
        "sequence": row[4],
        "estimated_hours": row[5]
    }

    cursor.execute("""
        SELECT id, name
        FROM workstations
        WHERE company_id = ?
        ORDER BY name ASC
    """, (company_id,))
    workstation_rows = cursor.fetchall()
    workstations = [{"id": r[0], "name": r[1]} for r in workstation_rows]

    cursor.execute("""
        SELECT id, product_code, product_name
        FROM products
        WHERE id = ? AND company_id = ?
    """, (job_template["product_id"], company_id))
    product_row = cursor.fetchone()
    conn.close()

    product = {
        "id": product_row[0],
        "product_code": product_row[1],
        "product_name": product_row[2]
    }

    return render_template(
        "edit_product_job.html",
        job_template=job_template,
        workstations=workstations,
        product=product,
        active_page="products"
    )


@app.route("/products/jobs/delete/<int:job_id>", methods=["POST"])
def delete_product_job(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT product_id
        FROM product_job_templates
        WHERE id = ? AND company_id = ?
    """, (job_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Product job template not found.", "error")
        return redirect(url_for("products"))

    product_id = row[0]

    cursor.execute("""
        DELETE FROM product_job_templates
        WHERE id = ? AND company_id = ?
    """, (job_id, company_id))

    conn.commit()
    conn.close()

    flash("Product job template deleted successfully.", "info")
    return redirect(url_for("product_jobs", product_id=product_id))


@app.route("/bom/<int:product_id>")
def product_bom(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_code, product_name, description, measurement_unit, time_per_unit
        FROM products
        WHERE id = ? AND company_id = ?
    """, (product_id, company_id))
    product_row = cursor.fetchone()

    if product_row is None:
        conn.close()
        return "Product not found", 404

    product = {
        "id": product_row[0],
        "product_code": product_row[1],
        "product_name": product_row[2],
        "description": product_row[3],
        "measurement_unit": product_row[4],
        "time_per_unit": product_row[5]
    }

    cursor.execute("""
        SELECT
            bom.id,
            bom.component_type,
            bom.quantity,
            items.item_code,
            items.item_name,
            items.measurement_unit,
            products.product_code,
            products.product_name,
            products.measurement_unit
        FROM bom
        LEFT JOIN items
          ON bom.item_id = items.id
         AND bom.component_type = 'item'
         AND items.company_id = bom.company_id
        LEFT JOIN products
          ON bom.child_product_id = products.id
         AND bom.component_type = 'product'
         AND products.company_id = bom.company_id
        WHERE bom.product_id = ?
          AND bom.company_id = ?
        ORDER BY bom.id DESC
    """, (product_id, company_id))
    bom_rows = cursor.fetchall()

    bom_items = []
    for row in bom_rows:
        if row[1] == "product":
            bom_items.append({
                "id": row[0],
                "component_type": "product",
                "component_code": row[6],
                "component_name": row[7],
                "measurement_unit": row[8],
                "quantity": row[2]
            })
        else:
            bom_items.append({
                "id": row[0],
                "component_type": "item",
                "component_code": row[3],
                "component_name": row[4],
                "measurement_unit": row[5],
                "quantity": row[2]
            })

    cursor.execute("""
        SELECT id, item_code, item_name, measurement_unit
        FROM items
        WHERE company_id = ?
        ORDER BY item_name ASC
    """, (company_id,))
    item_rows = cursor.fetchall()
    items = [{"id": r[0], "item_code": r[1], "item_name": r[2], "measurement_unit": r[3]} for r in item_rows]

    cursor.execute("""
        SELECT id, product_code, product_name, measurement_unit
        FROM products
        WHERE id != ?
          AND company_id = ?
        ORDER BY product_name ASC
    """, (product_id, company_id))
    product_rows = cursor.fetchall()
    child_products = [{"id": r[0], "product_code": r[1], "product_name": r[2], "measurement_unit": r[3]} for r in product_rows]

    conn.close()

    return render_template(
        "bom.html",
        product=product,
        bom_items=bom_items,
        items=items,
        child_products=child_products,
        active_page="products"
    )


@app.route("/products/<int:product_id>/cost")
def product_cost(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_code, product_name, measurement_unit
        FROM products
        WHERE id = ? AND company_id = ?
    """, (product_id, company_id))
    product_row = cursor.fetchone()

    if product_row is None:
        conn.close()
        return "Product not found", 404

    product = {
        "id": product_row[0],
        "product_code": product_row[1],
        "product_name": product_row[2],
        "measurement_unit": product_row[3]
    }

    try:
        exploded_items = explode_bom_items_recursive(cursor, product_id, 1, company_id=company_id)
    except ValueError as e:
        conn.close()
        flash(str(e), "error")
        return redirect(url_for("products"))

    materials = []
    total_material_cost = 0

    if exploded_items:
        item_ids = list(exploded_items.keys())
        placeholders = ",".join(["?"] * len(item_ids))

        cursor.execute(f"""
            SELECT id, item_code, item_name, measurement_unit, unit_price
            FROM items
            WHERE id IN ({placeholders})
              AND company_id = ?
            ORDER BY item_name ASC
        """, item_ids + [company_id])
        item_rows = cursor.fetchall()

        for row in item_rows:
            item_id = row[0]
            quantity_per_unit = exploded_items.get(item_id, 0)
            unit_price = row[4] if row[4] is not None else 0
            total_cost = quantity_per_unit * unit_price
            total_material_cost += total_cost

            materials.append({
                "item_code": row[1],
                "item_name": row[2],
                "unit": row[3],
                "quantity_per_unit": quantity_per_unit,
                "unit_price": unit_price,
                "total_cost": total_cost
            })

    conn.close()

    return render_template(
        "product_cost.html",
        product=product,
        materials=materials,
        total_material_cost=total_material_cost,
        active_page="products"
    )


@app.route("/bom/<int:product_id>/add", methods=["POST"])
def add_bom_item(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    component_type = request.form.get("component_type", "item").strip()
    quantity = float(request.form.get("quantity", 0) or 0)

    item_id = request.form.get("item_id")
    child_product_id = request.form.get("child_product_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "products", product_id, company_id, "Product not found.")

        if component_type == "product":
            if not child_product_id:
                raise ValueError("Child product is required.")
            child_product_id = int(child_product_id)
            require_company_record(cursor, "products", child_product_id, company_id, "Child product not found.")

            cursor.execute("""
                INSERT INTO bom (
                    product_id,
                    item_id,
                    quantity,
                    component_type,
                    child_product_id,
                    company_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, 0, quantity, "product", child_product_id, company_id))
        else:
            if not item_id:
                raise ValueError("Item is required.")
            item_id = int(item_id)
            require_company_record(cursor, "items", item_id, company_id, "Item not found.")

            cursor.execute("""
                INSERT INTO bom (
                    product_id,
                    item_id,
                    quantity,
                    component_type,
                    child_product_id,
                    company_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, item_id, quantity, "item", None, company_id))

        conn.commit()
        conn.close()

        flash("BOM item added successfully.", "success")
        return redirect(url_for("product_bom", product_id=product_id))
    except ValueError as e:
        conn.close()
        flash(str(e), "error")
        return redirect(url_for("product_bom", product_id=product_id))


@app.route("/bom/delete/<int:bom_id>", methods=["POST"])
def delete_bom_item(bom_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT product_id
        FROM bom
        WHERE id = ? AND company_id = ?
    """, (bom_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("BOM row not found.", "error")
        return redirect(url_for("products"))

    product_id = row[0]

    cursor.execute("""
        DELETE FROM bom
        WHERE id = ? AND company_id = ?
    """, (bom_id, company_id))

    conn.commit()
    conn.close()

    flash("BOM item deleted successfully.", "info")
    return redirect(url_for("product_bom", product_id=product_id))


@app.route("/workstations/new", methods=["GET", "POST"])
def new_workstation():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    if request.method == "POST":
        name = request.form["name"].strip()
        description = request.form["description"].strip()
        hours_per_shift = float(request.form["hours_per_shift"] or 8)
        shifts_per_day = int(request.form["shifts_per_day"] or 1)
        working_days_per_month = int(request.form["working_days_per_month"] or 20)
        color = request.form.get("color", "#3b82f6").strip() or "#3b82f6"

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO workstations (
                name,
                description,
                hours_per_shift,
                shifts_per_day,
                working_days_per_month,
                color,
                company_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            description,
            hours_per_shift,
            shifts_per_day,
            working_days_per_month,
            color,
            company_id
        ))

        conn.commit()
        conn.close()

        flash("Workstation created successfully.", "success")
        return redirect(url_for("workstations"))

    return render_template(
        "new_workstation.html",
        active_page="workstations"
    )


@app.route("/workstations/edit/<int:workstation_id>", methods=["GET", "POST"])
def edit_workstation(workstation_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            description,
            hours_per_shift,
            shifts_per_day,
            working_days_per_month,
            color
        FROM workstations
        WHERE id = ? AND company_id = ?
    """, (workstation_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return "Workstation not found", 404

    if request.method == "POST":
        name = request.form["name"].strip()
        description = request.form["description"].strip()
        hours_per_shift = float(request.form["hours_per_shift"] or 8)
        shifts_per_day = int(request.form["shifts_per_day"] or 1)
        working_days_per_month = int(request.form["working_days_per_month"] or 20)
        color = request.form.get("color", "#3b82f6").strip() or "#3b82f6"

        cursor.execute("""
            UPDATE workstations
            SET name = ?, description = ?, hours_per_shift = ?, shifts_per_day = ?, working_days_per_month = ?, color = ?
            WHERE id = ? AND company_id = ?
        """, (
            name,
            description,
            hours_per_shift,
            shifts_per_day,
            working_days_per_month,
            color,
            workstation_id,
            company_id
        ))

        conn.commit()
        conn.close()

        flash("Workstation updated successfully.", "success")
        return redirect(url_for("workstations"))

    conn.close()

    workstation = {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "hours_per_shift": row[3],
        "shifts_per_day": row[4],
        "working_days_per_month": row[5],
        "color": row[6]
    }

    return render_template(
        "edit_workstation.html",
        workstation=workstation,
        active_page="workstations"
    )


@app.route("/workstations/delete/<int:workstation_id>", methods=["POST"])
def delete_workstation(workstation_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM product_job_templates
        WHERE workstation_id = ? AND company_id = ?
    """, (workstation_id, company_id))
    template_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM order_jobs
        WHERE workstation_id = ? AND company_id = ?
    """, (workstation_id, company_id))
    job_count = cursor.fetchone()[0]

    if template_count > 0 or job_count > 0:
        conn.close()
        flash("Cannot delete workstation that is used in jobs or templates.", "error")
        return redirect(url_for("workstations"))

    cursor.execute("""
        DELETE FROM workstations
        WHERE id = ? AND company_id = ?
    """, (workstation_id, company_id))

    conn.commit()
    conn.close()

    flash("Workstation deleted successfully.", "info")
    return redirect(url_for("workstations"))



@app.route("/jobs")
@permission_required("view_jobs")
def jobs():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    order_number = request.args.get("order_number", "").strip()
    product_name = request.args.get("product_name", "").strip()
    job_name = request.args.get("job_name", "").strip()
    workstation = request.args.get("workstation", "").strip()
    workstation_text = request.args.get("workstation_text", "").strip()
    due_date_from = request.args.get("due_date_from", "").strip()
    due_date_to = request.args.get("due_date_to", "").strip()

    selected_statuses = request.args.getlist("status")
    selected_statuses = [s.strip() for s in selected_statuses if s.strip()]

    statuses = selected_statuses[:]
    if "All" in statuses:
        statuses = []

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT
            oj.id,
            o.order_number,
            jp.product_name,
            oj.job_name,
            w.name,
            oj.workstation_id,
            oj.sequence,
            oj.planned_quantity,
            oj.completed_quantity,
            oj.estimated_hours,
            oj.status,
            o.due_date,
            oj.planned_start,
            oj.planned_end,
            oj.parent_job_id,
            oj.is_split_child,
            (
                SELECT COUNT(*)
                FROM order_jobs child
                WHERE child.parent_job_id = oj.id
                  AND child.is_split_child = 1
                  AND child.company_id = oj.company_id
            ) AS child_count
        FROM order_jobs oj
        JOIN orders o
          ON oj.order_id = o.id
         AND o.company_id = oj.company_id
        LEFT JOIN products jp
          ON oj.job_product_id = jp.id
         AND jp.company_id = oj.company_id
        JOIN workstations w
          ON oj.workstation_id = w.id
         AND w.company_id = oj.company_id
        WHERE oj.company_id = ?
    """
    params = [company_id]

    if order_number:
        query += " AND o.order_number LIKE ?"
        params.append(f"%{order_number}%")

    if product_name:
        query += " AND jp.product_name LIKE ?"
        params.append(f"%{product_name}%")

    if job_name:
        query += " AND oj.job_name LIKE ?"
        params.append(f"%{job_name}%")

    if workstation:
        query += " AND oj.workstation_id = ?"
        params.append(workstation)

    if workstation_text:
        query += " AND w.name LIKE ?"
        params.append(f"%{workstation_text}%")

    if statuses:
        placeholders = ",".join(["?"] * len(statuses))
        query += f" AND oj.status IN ({placeholders})"
        params.extend(statuses)

    if due_date_from:
        query += " AND o.due_date >= ?"
        params.append(due_date_from)

    if due_date_to:
        query += " AND o.due_date <= ?"
        params.append(due_date_to)

    query += " ORDER BY o.due_date ASC, o.order_number ASC, oj.sequence ASC, oj.id ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    jobs = []
    for row in rows:
        job_id = row[0]
        planned_quantity = float(row[7] or 0)
        completed_quantity = float(row[8] or 0)
        child_count = int(row[16] or 0)

        progress_percent = 0
        if planned_quantity > 0:
            progress_percent = min(100, max(0, (completed_quantity / planned_quantity) * 100))

        jobs.append({
            "id": row[0],
            "order_number": row[1],
            "product_name": row[2] if row[2] else "-",
            "job_name": row[3],
            "workstation_name": row[4],
            "workstation_id": row[5],
            "sequence": row[6],
            "planned_quantity": planned_quantity,
            "completed_quantity": completed_quantity,
            "estimated_hours": row[9],
            "status": row[10],
            "due_date": row[11],
            "planned_start": row[12],
            "planned_end": row[13],
            "progress_percent": progress_percent,
            "parent_job_id": row[14],
            "is_split_child": int(row[15] or 0),
            "child_count": child_count,
            "can_start": can_start_job(cursor, job_id, company_id=company_id) if child_count == 0 else False
        })

    cursor.execute("""
        SELECT id, name
        FROM workstations
        WHERE company_id = ?
        ORDER BY name ASC
    """, (company_id,))
    ws_rows = cursor.fetchall()
    conn.close()

    workstations = [{"id": w[0], "name": w[1]} for w in ws_rows]

    filters = {
        "order_number": order_number,
        "product_name": product_name,
        "job_name": job_name,
        "workstation": workstation,
        "workstation_text": workstation_text,
        "status": selected_statuses,
        "due_date_from": due_date_from,
        "due_date_to": due_date_to
    }

    return render_template(
        "jobs.html",
        jobs=jobs,
        workstations=workstations,
        filters=filters,
        active_page="jobs"
    )


@app.route("/jobs/update_workstation/<int:job_id>", methods=["POST"])
def update_job_workstation(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    new_workstation_id = int(request.form["workstation_id"])

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "order_jobs", job_id, company_id, "Job not found.")
        require_company_record(cursor, "workstations", new_workstation_id, company_id, "Workstation not found.")

        cursor.execute("""
            UPDATE order_jobs
            SET workstation_id = ?
            WHERE id = ? AND company_id = ?
        """, (new_workstation_id, job_id, company_id))

        recalculate_job_dates(cursor, job_id)

        conn.commit()
        conn.close()

        flash("Workstation updated.", "success")
        return redirect(request.referrer or url_for("jobs"))
    except ValueError as e:
        conn.close()
        flash(str(e), "error")
        return redirect(request.referrer or url_for("jobs"))



@app.route("/jobs/update_status/<int:job_id>/<new_status>", methods=["POST"])
def update_job_status(job_id, new_status):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    allowed_statuses = ["Waiting", "Ongoing", "Paused", "Done"]

    if new_status not in allowed_statuses:
        flash("Invalid status.", "error")
        return redirect_back("jobs")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            order_id,
            parent_job_id,
            job_product_id,
            planned_quantity,
            completed_quantity,
            status
        FROM order_jobs
        WHERE id = ? AND company_id = ?
    """, (job_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Job not found.", "error")
        return redirect_back("jobs")

    order_id = row[0]
    parent_job_id = row[1]
    job_product_id = row[2]
    planned_quantity = float(row[3] or 0)
    completed_quantity = float(row[4] or 0)

    if new_status == "Ongoing":
        if not can_start_job(cursor, job_id, company_id=company_id):
            conn.close()
            flash("Cannot start this job yet. Previous sequence jobs are not done.", "error")
            return redirect_back("jobs")

        reserve_order_materials(cursor, order_id, company_id=company_id)

        cursor.execute("""
            UPDATE order_jobs
            SET status = ?
            WHERE id = ? AND company_id = ?
        """, (new_status, job_id, company_id))

    elif new_status == "Done":
        if completed_quantity < planned_quantity:
            completed_quantity = planned_quantity
            cursor.execute("""
                UPDATE order_jobs
                SET completed_quantity = ?, status = ?
                WHERE id = ? AND company_id = ?
            """, (completed_quantity, "Done", job_id, company_id))
        else:
            cursor.execute("""
                UPDATE order_jobs
                SET status = ?
                WHERE id = ? AND company_id = ?
            """, ("Done", job_id, company_id))

        consume_job_materials(cursor, job_product_id, planned_quantity, company_id=company_id)

        if is_final_job(cursor, order_id, job_id, company_id=company_id):
            add_finished_product_stock(cursor, job_product_id, planned_quantity, company_id=company_id)

    else:
        cursor.execute("""
            UPDATE order_jobs
            SET status = ?
            WHERE id = ? AND company_id = ?
        """, (new_status, job_id, company_id))

    if parent_job_id:
        sync_parent_job_status(cursor, parent_job_id, company_id=company_id)

    sync_order_status(cursor, order_id, company_id=company_id)

    conn.commit()
    conn.close()

    flash("Job status updated.", "success")
    return redirect_back("jobs")


@app.route("/jobs/update_progress/<int:job_id>", methods=["POST"])
@permission_required("update_job_progress")
def update_job_progress(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    completed_quantity = float(request.form.get("completed_quantity", 0) or 0)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT planned_quantity, parent_job_id, order_id
        FROM order_jobs
        WHERE id = ?
          AND company_id = ?
    """, (job_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Job not found.", "error")
        return redirect_back("jobs")

    planned_quantity = float(row[0] or 0)
    parent_job_id = row[1]
    order_id = row[2]

    if completed_quantity < 0:
        completed_quantity = 0

    if completed_quantity > planned_quantity:
        completed_quantity = planned_quantity

    if completed_quantity >= planned_quantity and planned_quantity > 0:
        new_status = "Done"
    elif completed_quantity > 0:
        new_status = "Ongoing"
    else:
        new_status = "Waiting"

    cursor.execute("""
        UPDATE order_jobs
        SET completed_quantity = ?, status = ?
        WHERE id = ?
          AND company_id = ?
    """, (completed_quantity, new_status, job_id, company_id))

    recalculate_job_dates(cursor, job_id)

    if parent_job_id:
        sync_parent_job_status(cursor, parent_job_id, company_id=company_id)

    sync_order_status(cursor, order_id, company_id=company_id)

    conn.commit()
    conn.close()

    flash("Job progress updated.", "success")
    return redirect_back("jobs")


@app.route("/inventory")
@permission_required("view_inventory")
def inventory():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, item_code, item_name, measurement_unit, unit_price, stock_quantity, min_stock
        FROM items
        WHERE company_id = ?
        ORDER BY item_name ASC
    """, (company_id,))
    item_rows = cursor.fetchall()

    items_inventory = []
    total_items_value = 0

    for row in item_rows:
        stock_quantity = float(row[5] or 0)
        unit_price = float(row[4] or 0)
        min_stock = float(row[6] or 0)
        stock_value = stock_quantity * unit_price
        total_items_value += stock_value

        if stock_quantity <= 0:
            stock_status = "Out"
        elif stock_quantity < min_stock:
            stock_status = "Low"
        else:
            stock_status = "OK"

        items_inventory.append({
            "id": row[0],
            "item_code": row[1],
            "item_name": row[2],
            "measurement_unit": row[3],
            "unit_price": unit_price,
            "stock_quantity": stock_quantity,
            "min_stock": min_stock,
            "stock_value": stock_value,
            "stock_status": stock_status
        })

    cursor.execute("""
        SELECT id, product_code, product_name, measurement_unit, stock_quantity
        FROM products
        WHERE company_id = ?
        ORDER BY product_name ASC
    """, (company_id,))
    product_rows = cursor.fetchall()

    products_inventory = []
    total_products_value = 0

    for row in product_rows:
        product_id = row[0]
        stock_quantity = float(row[4] or 0)
        material_cost = calculate_product_material_cost(cursor, product_id, company_id=company_id)
        stock_value = stock_quantity * material_cost
        total_products_value += stock_value

        products_inventory.append({
            "id": product_id,
            "product_code": row[1],
            "product_name": row[2],
            "measurement_unit": row[3],
            "stock_quantity": stock_quantity,
            "material_cost_per_unit": material_cost,
            "stock_value": stock_value
        })

    conn.close()

    return render_template(
        "inventory.html",
        items_inventory=items_inventory,
        products_inventory=products_inventory,
        total_items_value=total_items_value,
        total_products_value=total_products_value,
        active_page="inventory"
    )


@app.route("/materials-shortage")
@permission_required("manage_procurement")
def materials_shortage():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            i.id,
            i.item_code,
            i.item_name,
            i.measurement_unit,
            COALESCE(i.stock_quantity, 0),
            COALESCE(i.min_stock, 0),
            i.supplier_id,
            s.name
        FROM items i
        LEFT JOIN suppliers s
          ON i.supplier_id = s.id
         AND s.company_id = i.company_id
        WHERE i.company_id = ?
          AND COALESCE(i.stock_quantity, 0) < COALESCE(i.min_stock, 0)
        ORDER BY i.item_name ASC
    """, (company_id,))
    rows = cursor.fetchall()

    conn.close()

    shortage_items = []
    for row in rows:
        stock_quantity = float(row[4] or 0)
        min_stock = float(row[5] or 0)

        shortage_items.append({
            "id": row[0],
            "item_code": row[1],
            "item_name": row[2],
            "unit": row[3],
            "stock_quantity": stock_quantity,
            "min_stock": min_stock,
            "supplier_id": row[6],
            "supplier_name": row[7],
            "required_to_order": max(0, min_stock - stock_quantity)
        })

    return render_template(
        "materials_shortage.html",
        shortage_items=shortage_items,
        active_page="shortage"
    )


@app.route("/inventory/items/<int:item_id>/add-stock", methods=["POST"])
@permission_required("manage_inventory")
def add_item_stock(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    add_quantity = float(request.form.get("add_quantity", 0) or 0)

    if add_quantity <= 0:
        flash("Add quantity must be greater than 0.", "error")
        return redirect(request.referrer or url_for("inventory"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM items
        WHERE id = ?
          AND company_id = ?
    """, (item_id, company_id))
    item = cursor.fetchone()

    if item is None:
        conn.close()
        flash("Item not found.", "error")
        return redirect(request.referrer or url_for("inventory"))

    cursor.execute("""
        UPDATE items
        SET stock_quantity = stock_quantity + ?
        WHERE id = ?
          AND company_id = ?
    """, (add_quantity, item_id, company_id))

    conn.commit()
    conn.close()

    flash("Item stock added.", "success")
    return redirect(request.referrer or url_for("inventory"))

@app.route("/inventory/products/<int:product_id>/add-stock", methods=["POST"])
def add_product_stock(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    add_quantity = float(request.form.get("add_quantity", 0) or 0)

    if add_quantity <= 0:
        flash("Add quantity must be greater than 0.", "error")
        return redirect(request.referrer or url_for("inventory"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM products
        WHERE id = ?
          AND company_id = ?
    """, (product_id, company_id))
    product = cursor.fetchone()

    if product is None:
        conn.close()
        flash("Product not found.", "error")
        return redirect(request.referrer or url_for("inventory"))

    cursor.execute("""
        UPDATE products
        SET stock_quantity = stock_quantity + ?
        WHERE id = ?
          AND company_id = ?
    """, (add_quantity, product_id, company_id))

    conn.commit()
    conn.close()

    flash("Product stock added.", "success")
    return redirect(request.referrer or url_for("inventory"))




@app.route("/planner")
def planner():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    today = datetime.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    month_start = f"{year:04d}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    month_end = f"{year:04d}-{month:02d}-{last_day:02d}"

    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year
    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year

    month_days = build_month_days(year, month)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            w.id,
            w.name,
            w.description,
            w.hours_per_shift,
            w.shifts_per_day,
            w.working_days_per_month,
            w.color
        FROM workstations w
        WHERE w.company_id = ?
        ORDER BY w.name ASC
    """, (company_id,))
    workstation_rows = cursor.fetchall()

    workstations = []
    workstation_map = {}
    jobs_by_workstation = {}

    for row in workstation_rows:
        workstation = {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "hours_per_shift": float(row[3] or 0),
            "shifts_per_day": int(row[4] or 0),
            "working_days_per_month": int(row[5] or 0),
            "color": row[6] or "#3b82f6"
        }
        workstations.append(workstation)
        workstation_map[workstation["id"]] = workstation
        jobs_by_workstation[workstation["id"]] = []

    cursor.execute("""
        SELECT
            oj.id,
            oj.workstation_id,
            oj.job_name,
            oj.status,
            oj.planned_start,
            oj.planned_end,
            oj.completed_quantity,
            oj.planned_quantity,
            oj.estimated_hours,
            o.order_number,
            p.product_name,
            oj.parent_job_id,
            oj.is_split_child
        FROM order_jobs oj
        JOIN orders o
          ON oj.order_id = o.id
         AND o.company_id = oj.company_id
        LEFT JOIN products p
          ON oj.job_product_id = p.id
         AND p.company_id = oj.company_id
        WHERE oj.company_id = ?
          AND (
                oj.is_split_child = 1
                OR NOT EXISTS (
                    SELECT 1
                    FROM order_jobs child
                    WHERE child.parent_job_id = oj.id
                      AND child.is_split_child = 1
                      AND child.company_id = oj.company_id
                )
          )
        ORDER BY o.order_number ASC, oj.sequence ASC, oj.id ASC
    """, (company_id,))
    rows = cursor.fetchall()

    conn.close()

    unscheduled_jobs = []

    for row in rows:
        workstation_id = row[1]
        planned_start = row[4]
        planned_end = row[5]
        planned_quantity = float(row[7] or 0)
        completed_quantity = float(row[6] or 0)

        progress_percent = 0
        if planned_quantity > 0:
            progress_percent = min(100, max(0, (completed_quantity / planned_quantity) * 100))

        job = {
            "id": row[0],
            "workstation_id": workstation_id,
            "job_name": row[2],
            "status": row[3],
            "planned_start": planned_start,
            "planned_end": planned_end,
            "estimated_hours": row[8],
            "planned_quantity": planned_quantity,
            "completed_quantity": completed_quantity,
            "progress_percent": progress_percent,
            "order_number": row[9],
            "product_name": row[10] if row[10] else "-",
            "parent_job_id": row[11],
            "is_split_child": int(row[12] or 0)
        }

        if not planned_start or not planned_end or workstation_id not in jobs_by_workstation:
            unscheduled_jobs.append(job)
            continue

        if planned_end < month_start or planned_start > month_end:
            continue

        start_date = max(planned_start, month_start)
        end_date = min(planned_end, month_end)

        start_day = int(start_date[-2:])
        end_day = int(end_date[-2:])
        span_days = max(1, (end_day - start_day) + 1)

        ws_color = workstation_map[workstation_id]["color"] if workstation_id in workstation_map else "#3b82f6"

        jobs_by_workstation[workstation_id].append({
            "id": job["id"],
            "order_number": job["order_number"],
            "product_name": job["product_name"],
            "job_name": job["job_name"],
            "status": job["status"],
            "planned_start": job["planned_start"],
            "planned_end": job["planned_end"],
            "start_day": start_day,
            "end_day": end_day,
            "span_days": span_days,
            "color": ws_color,
            "progress_percent": job["progress_percent"],
            "parent_job_id": job["parent_job_id"],
            "is_split_child": job["is_split_child"]
        })

    return render_template(
        "planner.html",
        workstations=workstations,
        month_days=month_days,
        jobs_by_workstation=jobs_by_workstation,
        unscheduled_jobs=unscheduled_jobs,
        planner_year=year,
        planner_month=month,
        planner_month_name=calendar.month_name[month],
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        active_page="planner"
    )



@app.route("/planner/update-job-date/<int:job_id>", methods=["POST"])
def update_planner_job_date(job_id):
    if not is_logged_in():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    company_id = get_company_id()
    planned_start = request.form.get("planned_start", "").strip()
    workstation_id_raw = request.form.get("workstation_id", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "order_jobs", job_id, company_id, "Job not found.")

        new_workstation_id = None
        if workstation_id_raw:
            try:
                new_workstation_id = int(workstation_id_raw)
            except ValueError:
                return jsonify({"ok": False, "error": "Invalid workstation id"}), 400

            require_company_record(
                cursor,
                "workstations",
                new_workstation_id,
                company_id,
                "Workstation not found."
            )

            cursor.execute("""
                UPDATE order_jobs
                SET workstation_id = ?
                WHERE id = ? AND company_id = ?
            """, (new_workstation_id, job_id, company_id))

        recalculate_job_dates(cursor, job_id, planned_start or None)

        cursor.execute("""
            SELECT planned_start, planned_end, workstation_id
            FROM order_jobs
            WHERE id = ? AND company_id = ?
        """, (job_id, company_id))
        updated = cursor.fetchone()

        conn.commit()
        conn.close()

        return jsonify({
            "ok": True,
            "job_id": job_id,
            "planned_start": updated[0],
            "planned_end": updated[1],
            "workstation_id": updated[2]
        }), 200

    except ValueError as e:
        conn.rollback()
        conn.close()
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"ok": False, "error": "Failed to update planner job."}), 500



@app.route("/jobs/split/<int:job_id>", methods=["POST"])
def split_job(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    workstation_ids = request.form.getlist("split_workstation_id")
    quantities = request.form.getlist("split_quantity")

    split_rows = []

    for workstation_id, quantity in zip(workstation_ids, quantities):
        workstation_id = workstation_id.strip()
        quantity = quantity.strip()

        if not workstation_id or not quantity:
            continue

        try:
            ws_id = int(workstation_id)
            qty_value = float(quantity)
        except ValueError:
            flash("Invalid split values.", "error")
            return redirect_back("jobs")

        if qty_value <= 0:
            continue

        split_rows.append({
            "workstation_id": ws_id,
            "quantity": qty_value
        })

    if len(split_rows) < 2:
        flash("Split requires at least 2 valid rows.", "error")
        return redirect_back("jobs")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        require_company_record(cursor, "order_jobs", job_id, company_id, "Job not found.")

        for row in split_rows:
            require_company_record(cursor, "workstations", row["workstation_id"], company_id, "Workstation not found.")

        create_split_children(
            cursor,
            job_id,
            split_rows,
            company_id=company_id
        )

        cursor.execute("""
            SELECT order_id
            FROM order_jobs
            WHERE id = ? AND company_id = ?
        """, (job_id, company_id))
        parent_row = cursor.fetchone()

        if parent_row:
            sync_order_status(cursor, parent_row[0], company_id=company_id)

        conn.commit()
        flash("Job split successfully.", "success")
    except ValueError as e:
        conn.rollback()
        flash(str(e), "error")
    except Exception:
        conn.rollback()
        flash("Failed to split job.", "error")
    finally:
        conn.close()

    return redirect_back("jobs")




@app.route("/workstations")
def workstations():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            w.id,
            w.name,
            w.description,
            w.hours_per_shift,
            w.shifts_per_day,
            w.working_days_per_month,
            w.color,
            (w.hours_per_shift * w.shifts_per_day * w.working_days_per_month) AS monthly_capacity,
            IFNULL((
                SELECT SUM(
                    oj.estimated_hours *
                    CASE
                        WHEN (oj.planned_quantity - oj.completed_quantity) < 0 THEN 0
                        ELSE (oj.planned_quantity - oj.completed_quantity)
                    END
                )
                FROM order_jobs oj
                WHERE oj.workstation_id = w.id
                  AND oj.company_id = w.company_id
                  AND oj.status != 'Done'
                  AND (
                        oj.status = 'Waiting'
                        OR oj.status = 'Ongoing'
                        OR oj.status = 'Paused'
                        OR oj.status = 'Delayed'
                  )
                  AND (
                        oj.is_split_child = 1
                        OR NOT EXISTS (
                            SELECT 1
                            FROM order_jobs child
                            WHERE child.parent_job_id = oj.id
                              AND child.is_split_child = 1
                              AND child.company_id = oj.company_id
                        )
                  )
            ), 0) AS used_load
        FROM workstations w
        WHERE w.company_id = ?
        ORDER BY w.name ASC
    """, (company_id,))
    rows = cursor.fetchall()
    conn.close()

    workstations = []
    for row in rows:
        monthly_capacity = float(row[7] or 0)
        used_load = float(row[8] or 0)
        free_load = monthly_capacity - used_load

        workstations.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "hours_per_shift": row[3],
            "shifts_per_day": row[4],
            "working_days_per_month": row[5],
            "color": row[6],
            "monthly_capacity": monthly_capacity,
            "used_load": used_load,
            "free_load": free_load
        })

    return render_template(
        "workstations.html",
        workstations=workstations,
        active_page="workstations"
    )



@app.route("/users")
@permission_required("manage_users")
def users():
    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, full_name, email, role, COALESCE(is_active, 1)
        FROM users
        WHERE company_id = ?
        ORDER BY id ASC
    """, (company_id,))
    rows = cursor.fetchall()
    conn.close()

    users = []
    for row in rows:
        user_id = row[0]
        role = row[3] or "worker"
        effective_permissions = get_effective_permissions(user_id=user_id, role=role)

        users.append({
            "id": user_id,
            "full_name": row[1],
            "email": row[2],
            "role": role,
            "is_active": int(row[4] or 0),
            "permissions": sorted(effective_permissions),
        })

    return render_template(
        "users.html",
        users=users,
        permission_keys=ALL_PERMISSION_KEYS,
        active_page="users"
    )

@app.route("/users/new", methods=["GET", "POST"])
@permission_required("manage_users")
def new_user():
    company_id = get_company_id()

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        role = request.form.get("role", "worker").strip().lower()

        if not full_name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("new_user"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("new_user"))

        if role not in ROLE_DEFAULT_PERMISSIONS:
            flash("Invalid role.", "error")
            return redirect(url_for("new_user"))

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        existing = cursor.fetchone()

        if existing:
            conn.close()
            flash("Email already exists.", "error")
            return redirect(url_for("new_user"))

        hashed_password = generate_password_hash(password)

        cursor.execute("""
            INSERT INTO users (full_name, company, email, password, company_id, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            full_name,
            session.get("company_name", ""),
            email,
            hashed_password,
            company_id,
            role
        ))

        user_id = cursor.lastrowid

        for permission_key in ALL_PERMISSION_KEYS:
            form_value = request.form.get(f"perm_{permission_key}")
            default_has = permission_key in get_role_default_permissions(role)
            selected_has = bool(form_value)

            if selected_has != default_has:
                cursor.execute("""
                    INSERT INTO user_permissions (user_id, permission_key, allowed)
                    VALUES (?, ?, ?)
                """, (user_id, permission_key, 1 if selected_has else 0))

        conn.commit()
        conn.close()

        flash("User created successfully.", "success")
        return redirect(url_for("users"))

    return render_template(
        "new_user.html",
        permission_keys=ALL_PERMISSION_KEYS,
        role_defaults=ROLE_DEFAULT_PERMISSIONS,
        active_page="users"
    )


@app.route("/users/<int:user_id>/role", methods=["POST"])
@permission_required("manage_users")
def update_user_role(user_id):
    company_id = get_company_id()
    current_user_id = session.get("user_id")
    new_role = request.form.get("role", "worker").strip().lower()

    if new_role not in ROLE_DEFAULT_PERMISSIONS:
        flash("Invalid role.", "error")
        return redirect(url_for("users"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM users
        WHERE id = ? AND company_id = ?
    """, (user_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("users"))

    if user_id == current_user_id and new_role != "admin":
        conn.close()
        flash("You cannot remove admin role from your own account.", "error")
        return redirect(url_for("users"))

    cursor.execute("""
        UPDATE users
        SET role = ?
        WHERE id = ? AND company_id = ?
    """, (new_role, user_id, company_id))

    conn.commit()
    conn.close()

    flash("Role updated.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/permissions", methods=["POST"])
@permission_required("manage_users")
def update_user_permissions(user_id):
    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role
        FROM users
        WHERE id = ? AND company_id = ?
    """, (user_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("users"))

    role = (row[0] or "worker").lower()
    defaults = get_role_default_permissions(role)

    cursor.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))

    for permission_key in ALL_PERMISSION_KEYS:
        selected_has = request.form.get(f"perm_{permission_key}") == "1"
        default_has = permission_key in defaults

        if selected_has != default_has:
            cursor.execute("""
                INSERT INTO user_permissions (user_id, permission_key, allowed)
                VALUES (?, ?, ?)
            """, (user_id, permission_key, 1 if selected_has else 0))

    conn.commit()
    conn.close()

    flash("Permissions updated.", "success")
    return redirect(url_for("users"))
    

@app.route("/account")
@permission_required("view_dashboard")
def account():
    user_id = session.get("user_id")
    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, full_name, email, role, COALESCE(is_active, 1)
        FROM users
        WHERE id = ? AND company_id = ?
    """, (user_id, company_id))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        flash("Account not found.", "error")
        return redirect(url_for("dashboard"))

    account_user = {
        "id": row[0],
        "full_name": row[1],
        "email": row[2],
        "role": row[3],
        "is_active": int(row[4] or 0),
        "permissions": sorted(get_effective_permissions(user_id=row[0], role=row[3])),
    }

    permission_groups = {
        "Orders": ["view_orders", "manage_orders"],
        "Jobs": ["view_jobs", "update_job_progress", "manage_jobs"],
        "Inventory": ["view_inventory", "manage_inventory"],
        "Products & Items": ["view_products", "manage_products", "view_items", "manage_items"],
        "Workstations": ["view_workstations", "manage_workstations"],
        "Reports & Export": ["view_reports", "export_data"],
        "Administration": ["manage_users"],
        "Procurement": ["manage_procurement"],
    }

    return render_template(
        "account.html",
        account_user=account_user,
        permission_groups=permission_groups,
        active_page="account"
    )   


@app.route("/account/change-password", methods=["POST"])
@permission_required("view_dashboard")
def change_password():
    user_id = session.get("user_id")
    company_id = get_company_id()

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not current_password or not new_password or not confirm_password:
        flash("All password fields are required.", "error")
        return redirect(url_for("account"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("account"))

    if len(new_password) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("account"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT password
        FROM users
        WHERE id = ? AND company_id = ?
    """, (user_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Account not found.", "error")
        return redirect(url_for("dashboard"))

    current_password_hash = row[0]

    if not check_password_hash(current_password_hash, current_password):
        conn.close()
        flash("Current password is incorrect.", "error")
        return redirect(url_for("account"))

    new_password_hash = generate_password_hash(new_password)

    cursor.execute("""
        UPDATE users
        SET password = ?
        WHERE id = ? AND company_id = ?
    """, (new_password_hash, user_id, company_id))

    conn.commit()
    conn.close()

    flash("Password updated successfully.", "success")
    return redirect(url_for("account"))
# ---------------------------
# SUPPLIERS LIST
# ---------------------------
@app.route("/suppliers")
@permission_required("manage_procurement")
def suppliers():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().lower()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    sql = """
        SELECT
            id,
            company_id,
            name,
            supplier_code,
            contact_person,
            email,
            phone,
            address,
            notes,
            is_active,
            created_at
        FROM suppliers
        WHERE company_id = ?
    """
    params = [company_id]

    if search:
        sql += """
          AND (
                LOWER(COALESCE(name, '')) LIKE ?
             OR LOWER(COALESCE(supplier_code, '')) LIKE ?
             OR LOWER(COALESCE(contact_person, '')) LIKE ?
             OR LOWER(COALESCE(email, '')) LIKE ?
             OR LOWER(COALESCE(phone, '')) LIKE ?
          )
        """
        like_value = f"%{search.lower()}%"
        params.extend([like_value, like_value, like_value, like_value, like_value])

    if status_filter == "active":
        sql += " AND COALESCE(is_active, 0) = 1"
    elif status_filter == "inactive":
        sql += " AND COALESCE(is_active, 0) = 0"

    sql += " ORDER BY created_at DESC, id DESC"

    cursor.execute(sql, tuple(params))
    suppliers = cursor.fetchall()
    conn.close()

    return render_template(
        "suppliers.html",
        suppliers=suppliers,
        active_page="suppliers",
        search=search,
        status_filter=status_filter
    )


@app.route("/suppliers/new", methods=["GET", "POST"])
@permission_required("manage_suppliers")
def new_supplier():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        supplier_code = request.form.get("supplier_code", "").strip()
        contact_person = request.form.get("contact_person", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            conn.close()
            flash("Supplier name is required.", "error")
            return redirect(url_for("new_supplier"))

        cursor.execute("""
            INSERT INTO suppliers (
                company_id,
                name,
                supplier_code,
                contact_person,
                email,
                phone,
                address,
                notes,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            company_id,
            name,
            supplier_code or None,
            contact_person or None,
            email or None,
            phone or None,
            address or None,
            notes or None
        ))

        conn.commit()
        conn.close()

        flash("Supplier created successfully.", "success")
        return redirect(url_for("suppliers"))

    conn.close()
    return render_template(
        "new_supplier.html",
        active_page="suppliers"
    )

@app.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@permission_required("manage_suppliers")
def edit_supplier(supplier_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            company_id,
            name,
            supplier_code,
            contact_person,
            email,
            phone,
            address,
            notes,
            is_active,
            created_at
        FROM suppliers
        WHERE id = ? AND company_id = ?
    """, (supplier_id, company_id))

    supplier = cursor.fetchone()

    if supplier is None:
        conn.close()
        flash("Supplier not found.", "error")
        return redirect(url_for("suppliers"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        supplier_code = request.form.get("supplier_code", "").strip()
        contact_person = request.form.get("contact_person", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()
        is_active = 1 if request.form.get("is_active") == "on" else 0

        if not name:
            conn.close()
            flash("Supplier name is required.", "error")
            return redirect(url_for("edit_supplier", supplier_id=supplier_id))

        cursor.execute("""
            UPDATE suppliers
            SET
                name = ?,
                supplier_code = ?,
                contact_person = ?,
                email = ?,
                phone = ?,
                address = ?,
                notes = ?,
                is_active = ?
            WHERE id = ? AND company_id = ?
        """, (
            name,
            supplier_code or None,
            contact_person or None,
            email or None,
            phone or None,
            address or None,
            notes or None,
            is_active,
            supplier_id,
            company_id
        ))

        conn.commit()
        conn.close()

        flash("Supplier updated successfully.", "success")
        return redirect(url_for("suppliers"))

    conn.close()
    return render_template(
        "edit_supplier.html",
        supplier=supplier,
        active_page="suppliers"
    )


@app.route("/procurement/requests")
@permission_required("manage_procurement")
def purchase_requests():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().lower()
    priority_filter = request.args.get("priority", "").strip().lower()
    supplier_filter = request.args.get("supplier_id", "").strip()
    history_search = request.args.get("history_search", "").strip()
    history_status_filter = request.args.get("history_status", "").strip().lower()
    history_priority_filter = request.args.get("history_priority", "").strip().lower()
    history_supplier_filter = request.args.get("history_supplier_id", "").strip()
    show_history = request.args.get("show_history", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    active_sql = """
        SELECT
            pr.id,
            pr.company_id,
            pr.request_number,
            pr.item_id,
            pr.supplier_id,
            pr.title,
            pr.description,
            pr.quantity,
            pr.unit,
            pr.status,
            pr.priority,
            pr.needed_by,
            pr.requested_by,
            pr.approved_by,
            pr.ordered_by,
            pr.notes,
            pr.created_at,
            pr.updated_at,
            s.name AS supplier_name,
            u.full_name AS requester_name,
            i.item_name AS item_name
        FROM purchase_requests pr
        LEFT JOIN suppliers s
          ON pr.supplier_id = s.id
         AND s.company_id = pr.company_id
        LEFT JOIN users u
          ON pr.requested_by = u.id
         AND u.company_id = pr.company_id
        LEFT JOIN items i
          ON pr.item_id = i.id
         AND i.company_id = pr.company_id
        WHERE pr.company_id = ?
          AND COALESCE(pr.status, 'draft') NOT IN ('received', 'cancelled', 'rejected')
    """
    active_params = [company_id]

    if search:
        active_sql += """
          AND (
                LOWER(COALESCE(pr.request_number, '')) LIKE ?
             OR LOWER(COALESCE(pr.title, '')) LIKE ?
             OR LOWER(COALESCE(pr.description, '')) LIKE ?
             OR LOWER(COALESCE(s.name, '')) LIKE ?
             OR LOWER(COALESCE(i.item_name, '')) LIKE ?
          )
        """
        like_value = f"%{search.lower()}%"
        active_params.extend([like_value, like_value, like_value, like_value, like_value])

    if status_filter in ("draft", "submitted", "approved", "ordered"):
        active_sql += " AND LOWER(COALESCE(pr.status, 'draft')) = ?"
        active_params.append(status_filter)

    if priority_filter in ("low", "normal", "high"):
        active_sql += " AND LOWER(COALESCE(pr.priority, 'normal')) = ?"
        active_params.append(priority_filter)

    if supplier_filter:
        try:
            active_sql += " AND pr.supplier_id = ?"
            active_params.append(int(supplier_filter))
        except ValueError:
            pass

    active_sql += " ORDER BY pr.created_at DESC, pr.id DESC"

    cursor.execute(active_sql, tuple(active_params))
    requests = cursor.fetchall()

    archive_sql = """
        SELECT
            pr.id,
            pr.company_id,
            pr.request_number,
            pr.item_id,
            pr.supplier_id,
            pr.title,
            pr.description,
            pr.quantity,
            pr.unit,
            pr.status,
            pr.priority,
            pr.needed_by,
            pr.requested_by,
            pr.approved_by,
            pr.ordered_by,
            pr.notes,
            pr.created_at,
            pr.updated_at,
            s.name AS supplier_name,
            u.full_name AS requester_name,
            i.item_name AS item_name
        FROM purchase_requests pr
        LEFT JOIN suppliers s
          ON pr.supplier_id = s.id
         AND s.company_id = pr.company_id
        LEFT JOIN users u
          ON pr.requested_by = u.id
         AND u.company_id = pr.company_id
        LEFT JOIN items i
          ON pr.item_id = i.id
         AND i.company_id = pr.company_id
        WHERE pr.company_id = ?
          AND COALESCE(pr.status, 'draft') IN ('received', 'cancelled', 'rejected')
    """
    archive_params = [company_id]

    if history_search:
        archive_sql += """
          AND (
                LOWER(COALESCE(pr.request_number, '')) LIKE ?
             OR LOWER(COALESCE(pr.title, '')) LIKE ?
             OR LOWER(COALESCE(pr.description, '')) LIKE ?
             OR LOWER(COALESCE(s.name, '')) LIKE ?
             OR LOWER(COALESCE(i.item_name, '')) LIKE ?
          )
        """
        history_like_value = f"%{history_search.lower()}%"
        archive_params.extend([
            history_like_value,
            history_like_value,
            history_like_value,
            history_like_value,
            history_like_value
        ])

    if history_status_filter in ("received", "cancelled", "rejected"):
        archive_sql += " AND LOWER(COALESCE(pr.status, 'draft')) = ?"
        archive_params.append(history_status_filter)

    if history_priority_filter in ("low", "normal", "high"):
        archive_sql += " AND LOWER(COALESCE(pr.priority, 'normal')) = ?"
        archive_params.append(history_priority_filter)

    if history_supplier_filter:
        try:
            archive_sql += " AND pr.supplier_id = ?"
            archive_params.append(int(history_supplier_filter))
        except ValueError:
            pass

    archive_sql += " ORDER BY COALESCE(pr.updated_at, pr.created_at) DESC, pr.id DESC"

    cursor.execute(archive_sql, tuple(archive_params))
    archived_requests = cursor.fetchall()

    cursor.execute("""
        SELECT id, name
        FROM suppliers
        WHERE company_id = ?
        ORDER BY name ASC
    """, (company_id,))
    supplier_options = cursor.fetchall()

    conn.close()

    return render_template(
        "purchase_requests.html",
        requests=requests,
        archived_requests=archived_requests,
        supplier_options=supplier_options,
        active_page="purchase_requests",
        search=search,
        status_filter=status_filter,
        priority_filter=priority_filter,
        supplier_filter=supplier_filter,
        history_search=history_search,
        history_status_filter=history_status_filter,
        history_priority_filter=history_priority_filter,
        history_supplier_filter=history_supplier_filter,
        show_history=(show_history == "1")
    )


@app.route("/procurement/requests/new", methods=["GET", "POST"])
@permission_required("manage_procurement")
def new_purchase_request():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()
        unit = request.form.get("unit", "").strip()
        supplier_id_raw = request.form.get("supplier_id", "").strip()
        priority = request.form.get("priority", "normal").strip().lower()
        needed_by = request.form.get("needed_by", "").strip()
        notes = request.form.get("notes", "").strip()

        item_id = None
        selected_item_name = None
        selected_item_unit = None
        selected_item_supplier_id = None

        if item_id_raw:
            try:
                item_id = int(item_id_raw)
            except ValueError:
                conn.close()
                flash("Invalid item selected.", "error")
                return redirect(url_for("new_purchase_request"))

            cursor.execute("""
                SELECT id, item_name, measurement_unit, supplier_id
                FROM items
                WHERE id = ? AND company_id = ?
            """, (item_id, company_id))
            item_row = cursor.fetchone()

            if item_row is None:
                conn.close()
                flash("Selected item was not found.", "error")
                return redirect(url_for("new_purchase_request"))

            selected_item_name = item_row[1]
            selected_item_unit = item_row[2]
            selected_item_supplier_id = item_row[3]

        if not title:
            title = selected_item_name or ""

        if not title:
            conn.close()
            flash("Request title is required.", "error")
            return redirect(url_for("new_purchase_request"))

        if not quantity_raw:
            conn.close()
            flash("Quantity is required.", "error")
            return redirect(url_for("new_purchase_request"))

        try:
            quantity = float(quantity_raw)
        except ValueError:
            conn.close()
            flash("Quantity must be a valid number.", "error")
            return redirect(url_for("new_purchase_request"))

        if quantity <= 0:
            conn.close()
            flash("Quantity must be greater than zero.", "error")
            return redirect(url_for("new_purchase_request"))

        if not unit and selected_item_unit:
            unit = selected_item_unit

        if not unit:
            conn.close()
            flash("Unit is required.", "error")
            return redirect(url_for("new_purchase_request"))

        if priority not in ("low", "normal", "high"):
            priority = "normal"

        if not supplier_id_raw and selected_item_supplier_id:
            supplier_id_raw = str(selected_item_supplier_id)

        supplier_id = None
        if supplier_id_raw:
            try:
                supplier_id = int(supplier_id_raw)
            except ValueError:
                conn.close()
                flash("Invalid supplier selected.", "error")
                return redirect(url_for("new_purchase_request"))

            cursor.execute("""
                SELECT id
                FROM suppliers
                WHERE id = ? AND company_id = ?
            """, (supplier_id, company_id))
            supplier_row = cursor.fetchone()

            if supplier_row is None:
                conn.close()
                flash("Selected supplier was not found.", "error")
                return redirect(url_for("new_purchase_request"))

        cursor.execute("""
            INSERT INTO purchase_requests (
                company_id,
                request_number,
                item_id,
                supplier_id,
                title,
                description,
                quantity,
                unit,
                status,
                priority,
                needed_by,
                requested_by,
                approved_by,
                ordered_by,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            company_id,
            None,
            item_id,
            supplier_id,
            title,
            description or None,
            quantity,
            unit,
            "draft",
            priority,
            needed_by or None,
            user_id,
            None,
            None,
            notes or None
        ))

        new_request_id = cursor.lastrowid
        request_number = f"PR-{new_request_id:05d}"

        cursor.execute("""
            UPDATE purchase_requests
            SET request_number = ?
            WHERE id = ? AND company_id = ?
        """, (request_number, new_request_id, company_id))

        conn.commit()
        conn.close()

        flash("Purchase request created successfully.", "success")
        return redirect(url_for("purchase_requests"))

    cursor.execute("""
        SELECT id, name
        FROM suppliers
        WHERE company_id = ? AND is_active = 1
        ORDER BY name ASC
    """, (company_id,))
    suppliers = cursor.fetchall()

    cursor.execute("""
        SELECT
            i.id,
            i.item_name,
            i.measurement_unit,
            i.supplier_id,
            s.name
        FROM items i
        LEFT JOIN suppliers s
          ON i.supplier_id = s.id
         AND s.company_id = i.company_id
        WHERE i.company_id = ?
        ORDER BY i.item_name ASC
    """, (company_id,))
    items = cursor.fetchall()

    conn.close()

    return render_template(
        "new_purchase_request.html",
        suppliers=suppliers,
        items=items,
        active_page="purchase_requests"
    )


@app.route("/procurement/requests/<int:request_id>/status/<status>")
@permission_required("manage_procurement")
def update_request_status(request_id, status):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    user_id = session.get("user_id")
    status = (status or "").strip().lower()

    allowed_statuses = {"submitted", "approved", "rejected", "ordered", "cancelled"}

    if status not in allowed_statuses:
        flash("Invalid status.", "error")
        return redirect(url_for("purchase_requests"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, status
        FROM purchase_requests
        WHERE id = ? AND company_id = ?
    """, (request_id, company_id))

    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Purchase request not found.", "error")
        return redirect(url_for("purchase_requests"))

    current_status = (row[1] or "").lower()

    allowed_transitions = {
        "draft": {"submitted", "cancelled"},
        "submitted": {"approved", "rejected", "cancelled"},
        "approved": {"ordered", "cancelled"},
        "ordered": set(),
        "rejected": set(),
        "cancelled": set()
    }

    if status not in allowed_transitions.get(current_status, set()):
        conn.close()
        flash(f"Cannot change status from {current_status} to {status}.", "error")
        return redirect(url_for("purchase_requests"))

    approved_by = None
    ordered_by = None

    if status == "approved":
        approved_by = user_id

    if status == "ordered":
        ordered_by = user_id

    cursor.execute("""
        UPDATE purchase_requests
        SET
            status = ?,
            approved_by = COALESCE(?, approved_by),
            ordered_by = COALESCE(?, ordered_by),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND company_id = ?
    """, (
        status,
        approved_by,
        ordered_by,
        request_id,
        company_id
    ))

    conn.commit()
    conn.close()

    flash(f"Request marked as {status}.", "success")
    return redirect(url_for("purchase_requests"))


@app.route("/procurement/requests/<int:request_id>/edit", methods=["GET", "POST"])
@permission_required("manage_procurement")
def edit_purchase_request(request_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            company_id,
            request_number,
            item_id,
            supplier_id,
            title,
            description,
            quantity,
            unit,
            status,
            priority,
            needed_by,
            requested_by,
            approved_by,
            ordered_by,
            notes,
            created_at,
            updated_at
        FROM purchase_requests
        WHERE id = ? AND company_id = ?
    """, (request_id, company_id))

    purchase_request = cursor.fetchone()

    if purchase_request is None:
        conn.close()
        flash("Purchase request not found.", "error")
        return redirect(url_for("purchase_requests"))

    current_status = (purchase_request[9] or "").lower()

    if current_status not in ("draft", "submitted"):
        conn.close()
        flash("Only draft or submitted requests can be edited.", "error")
        return redirect(url_for("purchase_requests"))

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()
        unit = request.form.get("unit", "").strip()
        supplier_id_raw = request.form.get("supplier_id", "").strip()
        priority = request.form.get("priority", "normal").strip().lower()
        needed_by = request.form.get("needed_by", "").strip()
        notes = request.form.get("notes", "").strip()

        item_id = None
        selected_item_name = None
        selected_item_unit = None
        selected_item_supplier_id = None

        if item_id_raw:
            try:
                item_id = int(item_id_raw)
            except ValueError:
                conn.close()
                flash("Invalid item selected.", "error")
                return redirect(url_for("edit_purchase_request", request_id=request_id))

            cursor.execute("""
                SELECT id, item_name, measurement_unit, supplier_id
                FROM items
                WHERE id = ? AND company_id = ?
            """, (item_id, company_id))
            item_row = cursor.fetchone()

            if item_row is None:
                conn.close()
                flash("Selected item was not found.", "error")
                return redirect(url_for("edit_purchase_request", request_id=request_id))

            selected_item_name = item_row[1]
            selected_item_unit = item_row[2]
            selected_item_supplier_id = item_row[3]

        if not title:
            title = selected_item_name or ""

        if not title:
            conn.close()
            flash("Request title is required.", "error")
            return redirect(url_for("edit_purchase_request", request_id=request_id))

        if not quantity_raw:
            conn.close()
            flash("Quantity is required.", "error")
            return redirect(url_for("edit_purchase_request", request_id=request_id))

        try:
            quantity = float(quantity_raw)
        except ValueError:
            conn.close()
            flash("Quantity must be a valid number.", "error")
            return redirect(url_for("edit_purchase_request", request_id=request_id))

        if quantity <= 0:
            conn.close()
            flash("Quantity must be greater than zero.", "error")
            return redirect(url_for("edit_purchase_request", request_id=request_id))

        if not unit and selected_item_unit:
            unit = selected_item_unit

        if not unit:
            conn.close()
            flash("Unit is required.", "error")
            return redirect(url_for("edit_purchase_request", request_id=request_id))

        if priority not in ("low", "normal", "high"):
            priority = "normal"

        if not supplier_id_raw and selected_item_supplier_id:
            supplier_id_raw = str(selected_item_supplier_id)

        supplier_id = None
        if supplier_id_raw:
            try:
                supplier_id = int(supplier_id_raw)
            except ValueError:
                conn.close()
                flash("Invalid supplier selected.", "error")
                return redirect(url_for("edit_purchase_request", request_id=request_id))

            cursor.execute("""
                SELECT id
                FROM suppliers
                WHERE id = ? AND company_id = ?
            """, (supplier_id, company_id))

            supplier_row = cursor.fetchone()

            if supplier_row is None:
                conn.close()
                flash("Selected supplier was not found.", "error")
                return redirect(url_for("edit_purchase_request", request_id=request_id))

        cursor.execute("""
            UPDATE purchase_requests
            SET
                item_id = ?,
                supplier_id = ?,
                title = ?,
                description = ?,
                quantity = ?,
                unit = ?,
                priority = ?,
                needed_by = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND company_id = ?
        """, (
            item_id,
            supplier_id,
            title,
            description or None,
            quantity,
            unit,
            priority,
            needed_by or None,
            notes or None,
            request_id,
            company_id
        ))

        conn.commit()
        conn.close()

        flash("Purchase request updated successfully.", "success")
        return redirect(url_for("purchase_requests"))

    cursor.execute("""
        SELECT id, name
        FROM suppliers
        WHERE company_id = ? AND is_active = 1
        ORDER BY name ASC
    """, (company_id,))
    suppliers = cursor.fetchall()

    cursor.execute("""
        SELECT
            i.id,
            i.item_name,
            i.measurement_unit,
            i.supplier_id,
            s.name
        FROM items i
        LEFT JOIN suppliers s
          ON i.supplier_id = s.id
         AND s.company_id = i.company_id
        WHERE i.company_id = ?
        ORDER BY i.item_name ASC
    """, (company_id,))
    items = cursor.fetchall()

    conn.close()

    return render_template(
        "edit_purchase_request.html",
        purchase_request=purchase_request,
        suppliers=suppliers,
        items=items,
        active_page="purchase_requests"
    )


@app.route("/procurement/requests/<int:request_id>/receive", methods=["POST"])
@permission_required("manage_procurement")
def receive_purchase_request(request_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            item_id,
            quantity,
            status,
            title,
            unit
        FROM purchase_requests
        WHERE id = ?
          AND company_id = ?
    """, (request_id, company_id))

    request_row = cursor.fetchone()

    if request_row is None:
        conn.close()
        flash("Purchase request not found.", "error")
        return redirect(url_for("purchase_requests"))

    item_id = request_row[1]
    quantity = float(request_row[2] or 0)
    current_status = (request_row[3] or "").lower()
    request_title = request_row[4] or "Request"

    if current_status != "ordered":
        conn.close()
        flash("Only ordered requests can be received.", "error")
        return redirect(url_for("purchase_requests"))

    if not item_id:
        conn.close()
        flash("This request is not linked to an inventory item, so stock cannot be received.", "error")
        return redirect(url_for("purchase_requests"))

    if quantity <= 0:
        conn.close()
        flash("Received quantity must be greater than zero.", "error")
        return redirect(url_for("purchase_requests"))

    cursor.execute("""
        SELECT id
        FROM items
        WHERE id = ?
          AND company_id = ?
    """, (item_id, company_id))
    item_row = cursor.fetchone()

    if item_row is None:
        conn.close()
        flash("Linked inventory item was not found.", "error")
        return redirect(url_for("purchase_requests"))

    cursor.execute("""
        UPDATE items
        SET stock_quantity = COALESCE(stock_quantity, 0) + ?
        WHERE id = ?
          AND company_id = ?
    """, (quantity, item_id, company_id))

    cursor.execute("""
        UPDATE purchase_requests
        SET
            status = 'received',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
          AND company_id = ?
    """, (request_id, company_id))

    conn.commit()
    conn.close()

    flash(f"{request_title} received and inventory updated.", "success")
    return redirect(url_for("purchase_requests"))



@app.route("/materials-shortage/<int:item_id>/create-request", methods=["POST"])
@permission_required("manage_procurement")
def create_request_from_shortage(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            item_name,
            measurement_unit,
            supplier_id,
            COALESCE(stock_quantity, 0),
            COALESCE(min_stock, 0)
        FROM items
        WHERE id = ?
          AND company_id = ?
    """, (item_id, company_id))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Item not found.", "error")
        return redirect(url_for("materials_shortage"))

    stock_quantity = float(row[4] or 0)
    min_stock = float(row[5] or 0)
    required_to_order = max(0, min_stock - stock_quantity)

    if required_to_order <= 0:
        conn.close()
        flash("This item is no longer below minimum stock.", "info")
        return redirect(url_for("materials_shortage"))

    cursor.execute("""
        INSERT INTO purchase_requests (
            company_id,
            request_number,
            item_id,
            supplier_id,
            title,
            description,
            quantity,
            unit,
            status,
            priority,
            needed_by,
            requested_by,
            approved_by,
            ordered_by,
            notes,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        company_id,
        None,
        row[0],
        row[3],
        row[1],
        f"Auto-created from shortage. Current stock: {stock_quantity:g}, minimum stock: {min_stock:g}.",
        required_to_order,
        row[2] or "",
        "draft",
        "high",
        None,
        user_id,
        None,
        None,
        "Created from shortage screen."
    ))

    new_request_id = cursor.lastrowid
    request_number = f"PR-{new_request_id:05d}"

    cursor.execute("""
        UPDATE purchase_requests
        SET request_number = ?
        WHERE id = ?
          AND company_id = ?
    """, (request_number, new_request_id, company_id))

    conn.commit()
    conn.close()

    flash("Purchase request created from shortage.", "success")
    return redirect(url_for("purchase_requests"))





@app.route("/dashboard/save-layout", methods=["POST"])
def save_dashboard_layout():
    if not is_logged_in():
        return {"ok": False, "error": "Unauthorized"}, 401

    company_id = get_company_id()
    user_id = session.get("user_id")

    data = request.get_json(silent=True) or {}
    layout = data.get("layout", [])

    if not isinstance(layout, list):
        return {"ok": False, "error": "Invalid payload"}, 400

    clean_layout = []

    for item in layout:
        if not isinstance(item, dict):
            continue

        widget_id = str(item.get("id", "")).strip()
        if not widget_id:
            continue

        try:
            x = float(item.get("x", 0))
            y = float(item.get("y", 0))
            w = float(item.get("w", 320))
            h = float(item.get("h", 180))
        except (TypeError, ValueError):
            continue

        clean_layout.append({
            "id": widget_id,
            "x": max(0, x),
            "y": max(0, y),
            "w": max(240, w),
            "h": max(100, h)
        })

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    save_dashboard_layout_record(cursor, user_id, company_id, clean_layout, "dashboard")

    conn.commit()
    conn.close()

    return {"ok": True}




@app.route("/reports")
@permission_required("view_reports")
def reports():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()

    report_type = request.args.get("report_type", "").strip()
    job_search = request.args.get("job_search", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT
            pr.id,
            pr.report_type,
            pr.quantity,
            COALESCE(pr.unit, 'pcs') AS unit,
            pr.notes,
            pr.created_at,
            oj.id,
            oj.job_name,
            oj.status,
            o.order_number,
            COALESCE(p.product_name, '-') AS product_name,
            COALESCE(w.name, '-') AS workstation_name,
            COALESCE(u.full_name, 'System') AS reported_by_name
        FROM production_reports pr
        JOIN order_jobs oj
          ON pr.job_id = oj.id
         AND oj.company_id = pr.company_id
        LEFT JOIN orders o
          ON pr.order_id = o.id
         AND o.company_id = pr.company_id
        LEFT JOIN products p
          ON pr.product_id = p.id
         AND p.company_id = pr.company_id
        LEFT JOIN workstations w
          ON pr.workstation_id = w.id
         AND w.company_id = pr.company_id
        LEFT JOIN users u
          ON pr.reported_by = u.id
        WHERE pr.company_id = ?
    """
    params = [company_id]

    if report_type:
        query += " AND pr.report_type = ?"
        params.append(report_type)

    if job_search:
        query += """
          AND (
                o.order_number LIKE ?
                OR oj.job_name LIKE ?
                OR p.product_name LIKE ?
                OR w.name LIKE ?
          )
        """
        like_value = f"%{job_search}%"
        params.extend([like_value, like_value, like_value, like_value])

    query += " ORDER BY pr.created_at DESC, pr.id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    reports = []
    total_scrap = 0
    total_waste = 0
    total_defect = 0

    for row in rows:
        report = {
            "id": row[0],
            "report_type": row[1],
            "quantity": float(row[2] or 0),
            "unit": row[3] or "pcs",
            "notes": row[4],
            "created_at": row[5],
            "job_id": row[6],
            "job_name": row[7],
            "job_status": row[8],
            "order_number": row[9],
            "product_name": row[10],
            "workstation_name": row[11],
            "reported_by_name": row[12]
        }
        reports.append(report)

        if report["report_type"] == "scrap":
            total_scrap += report["quantity"]
        elif report["report_type"] == "waste":
            total_waste += report["quantity"]
        elif report["report_type"] == "defect":
            total_defect += report["quantity"]

    conn.close()

    return render_template(
        "reports.html",
        reports=reports,
        total_scrap=total_scrap,
        total_waste=total_waste,
        total_defect=total_defect,
        filters={
            "report_type": report_type,
            "job_search": job_search
        },
        active_page="reports"
    )


@app.route("/reports/new", methods=["GET", "POST"])
@permission_required("view_reports")
def new_report():
    if not is_logged_in():
        return redirect(url_for("login"))

    company_id = get_company_id()
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        job_id_raw = request.form.get("job_id", "").strip()
        report_type = request.form.get("report_type", "").strip().lower()
        quantity_raw = request.form.get("quantity", "").strip()
        unit_raw = request.form.get("unit", "").strip()
        custom_unit_raw = request.form.get("custom_unit", "").strip()
        notes = request.form.get("notes", "").strip()

        if not job_id_raw or not report_type or not quantity_raw:
            conn.close()
            flash("Job, report type and quantity are required.", "error")
            return redirect(url_for("new_report"))

        if report_type not in {"scrap", "waste", "defect", "note"}:
            conn.close()
            flash("Invalid report type.", "error")
            return redirect(url_for("new_report"))

        try:
            job_id = int(job_id_raw)
            quantity = float(quantity_raw)
        except ValueError:
            conn.close()
            flash("Invalid job or quantity.", "error")
            return redirect(url_for("new_report"))

        if quantity < 0:
            conn.close()
            flash("Quantity cannot be negative.", "error")
            return redirect(url_for("new_report"))

        unit = unit_raw or "pcs"
        if unit == "custom":
            unit = custom_unit_raw.strip()

        if not unit:
            unit = "pcs"

        cursor.execute("""
            SELECT
                oj.id,
                oj.order_id,
                oj.job_product_id,
                oj.workstation_id,
                oj.status
            FROM order_jobs oj
            WHERE oj.id = ?
              AND oj.company_id = ?
        """, (job_id, company_id))
        job_row = cursor.fetchone()

        if job_row is None:
            conn.close()
            flash("Selected job not found.", "error")
            return redirect(url_for("new_report"))

        if job_row[4] not in ("Waiting", "Ongoing", "Paused", "Delayed"):
            conn.close()
            flash("Reports can only be created for active jobs.", "error")
            return redirect(url_for("new_report"))

        cursor.execute("""
            INSERT INTO production_reports (
                company_id,
                job_id,
                order_id,
                product_id,
                workstation_id,
                report_type,
                quantity,
                unit,
                notes,
                reported_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            job_row[0],
            job_row[1],
            job_row[2],
            job_row[3],
            report_type,
            quantity,
            unit,
            notes,
            user_id
        ))

        conn.commit()
        conn.close()

        flash("Production report created successfully.", "success")
        return redirect(url_for("reports"))

    active_jobs = get_active_jobs_for_reports(cursor, company_id)
    conn.close()

    return render_template(
        "new_report.html",
        active_jobs=active_jobs,
        active_page="reports"
    )


@app.route("/reports/new/<int:job_id>")
@permission_required("view_reports")
def new_report_for_job(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    return redirect(url_for("new_report", job_id=job_id))


if __name__ == "__main__":
    init_db()
    seed_data()
    app.run(debug=True)