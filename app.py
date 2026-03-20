from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
import calendar
import math

app = Flask(__name__)
app.secret_key = "ums-secret-key-change-this-later"


def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        customer TEXT,
        status TEXT,
        due_date TEXT,
        priority TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        company TEXT,
        email TEXT UNIQUE,
        password TEXT
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
        min_stock REAL NOT NULL DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL,
        product_name TEXT NOT NULL,
        description TEXT,
        measurement_unit TEXT NOT NULL,
        stock_quantity REAL NOT NULL DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (item_id) REFERENCES items(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workstations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        hours_per_shift REAL NOT NULL DEFAULT 8,
        shifts_per_day INTEGER NOT NULL DEFAULT 1,
        working_days_per_month INTEGER NOT NULL DEFAULT 20
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
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (workstation_id) REFERENCES workstations(id)
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
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (job_product_id) REFERENCES products(id),
        FOREIGN KEY (workstation_id) REFERENCES workstations(id)
    )
    """)

    try:
        cursor.execute("ALTER TABLE products ADD COLUMN measurement_unit TEXT NOT NULL DEFAULT 'pcs'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE products ADD COLUMN stock_quantity REAL NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN product_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN quantity REAL DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE bom ADD COLUMN component_type TEXT NOT NULL DEFAULT 'item'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE bom ADD COLUMN child_product_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE order_jobs ADD COLUMN job_product_id INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN stock_quantity REAL NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE items ADD COLUMN min_stock REAL NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN materials_reserved INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE order_jobs ADD COLUMN planned_start TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE order_jobs ADD COLUMN planned_end TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE workstations ADD COLUMN color TEXT NOT NULL DEFAULT '#3b82f6'")
    except sqlite3.OperationalError:
        pass
    


    try:
        cursor.execute("ALTER TABLE order_jobs ADD COLUMN parent_job_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE order_jobs ADD COLUMN is_split_child INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def seed_data():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM orders")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
        INSERT INTO orders (order_number, customer, status, due_date, priority)
        VALUES
        ('ORD-1001', 'NordSteel', 'In Progress', '2026-03-25', 'High'),
        ('ORD-1002', 'Baltic Frame', 'Waiting', '2026-03-28', 'Medium'),
        ('ORD-1003', 'MetalWorks LT', 'Completed', '2026-03-20', 'Low')
        """)

    conn.commit()
    conn.close()


def is_logged_in():
    return "user_id" in session

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

def generate_order_jobs_recursive(cursor, order_id, current_product_id, current_quantity, planned_date=None, path=None):
    if path is None:
        path = []

    if current_product_id in path:
        raise ValueError("Circular BOM detected.")

    current_path = path + [current_product_id]

    cursor.execute("""
        SELECT child_product_id, quantity
        FROM bom
        WHERE product_id = ?
          AND component_type = 'product'
          AND child_product_id IS NOT NULL
        ORDER BY id ASC
    """, (current_product_id,))
    child_rows = cursor.fetchall()

    for child_product_id, bom_quantity in child_rows:
        child_required_quantity = float(current_quantity) * float(bom_quantity)
        generate_order_jobs_recursive(
            cursor,
            order_id,
            child_product_id,
            child_required_quantity,
            planned_date,
            current_path
        )

    cursor.execute("""
        SELECT id, workstation_id, job_name, sequence, estimated_hours
        FROM product_job_templates
        WHERE product_id = ?
        ORDER BY sequence ASC, id ASC
    """, (current_product_id,))
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
                planned_end
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            planned_date
        ))

        new_job_id = cursor.lastrowid
        recalculate_job_dates(cursor, new_job_id, planned_date)

def is_float_equal(a, b, tolerance=0.0001):
    return abs(float(a) - float(b)) <= tolerance


def job_has_split_children(cursor, job_id):
    cursor.execute("""
        SELECT COUNT(*)
        FROM order_jobs
        WHERE parent_job_id = ?
          AND is_split_child = 1
    """, (job_id,))
    return cursor.fetchone()[0] > 0

def can_start_job(cursor, job_id):
    cursor.execute("""
        SELECT
            id,
            order_id,
            sequence,
            parent_job_id,
            is_split_child
        FROM order_jobs
        WHERE id = ?
    """, (job_id,))
    job = cursor.fetchone()

    if job is None:
        return False

    order_id = job[1]
    sequence = int(job[2] or 0)
    parent_job_id = job[3]
    is_split_child = int(job[4] or 0)

    if sequence <= 1:
        return True

    # Jei tai split child job, tikrinam tik ankstesnius executable job'us:
    # - single job'us
    # - split child job'us
    # ir ignoruojam split parent'us
    if is_split_child == 1:
        cursor.execute("""
            SELECT COUNT(*)
            FROM order_jobs prev
            WHERE prev.order_id = ?
              AND prev.sequence < ?
              AND prev.status != 'Done'
              AND (
                    prev.is_split_child = 1
                    OR NOT EXISTS (
                        SELECT 1
                        FROM order_jobs child
                        WHERE child.parent_job_id = prev.id
                          AND child.is_split_child = 1
                    )
                  )
        """, (order_id, sequence))
        remaining = cursor.fetchone()[0]
        return remaining == 0

    # Jei tai paprastas single job arba split parent
    # tikrinam tik ankstesnius single job'us ir split child job'us,
    # bet ignoruojam split parent'us
    cursor.execute("""
        SELECT COUNT(*)
        FROM order_jobs prev
        WHERE prev.order_id = ?
          AND prev.sequence < ?
          AND prev.status != 'Done'
          AND (
                prev.is_split_child = 1
                OR NOT EXISTS (
                    SELECT 1
                    FROM order_jobs child
                    WHERE child.parent_job_id = prev.id
                      AND child.is_split_child = 1
                )
              )
    """, (order_id, sequence))
    remaining = cursor.fetchone()[0]

    return remaining == 0

def sync_parent_job_status(cursor, parent_job_id):
    cursor.execute("""
        SELECT id, planned_quantity, completed_quantity, status
        FROM order_jobs
        WHERE parent_job_id = ?
          AND is_split_child = 1
        ORDER BY id ASC
    """, (parent_job_id,))
    children = cursor.fetchall()

    if not children:
        return

    total_planned = sum(float(row[1] or 0) for row in children)
    total_completed = sum(float(row[2] or 0) for row in children)
    child_statuses = [row[3] for row in children]

    if all(status == "Done" for status in child_statuses):
        parent_status = "Done"
    elif any(status == "Ongoing" for status in child_statuses):
        parent_status = "Ongoing"
    elif any(status == "Paused" for status in child_statuses):
        parent_status = "Paused"
    else:
        parent_status = "Waiting"

    cursor.execute("""
        UPDATE order_jobs
        SET completed_quantity = ?, status = ?
        WHERE id = ?
    """, (total_completed, parent_status, parent_job_id))


def can_start_job(cursor, job_id):
    cursor.execute("""
        SELECT
            id,
            order_id,
            sequence,
            parent_job_id,
            is_split_child
        FROM order_jobs
        WHERE id = ?
    """, (job_id,))
    job = cursor.fetchone()

    if job is None:
        return False

    order_id = job[1]
    sequence = int(job[2] or 0)
    is_split_child = int(job[4] or 0)

    if sequence <= 1:
        return True

    # Split child atveju tikrinam tik realiai vykdomus ankstesnius job'us
    if is_split_child == 1:
        cursor.execute("""
            SELECT COUNT(*)
            FROM order_jobs prev
            WHERE prev.order_id = ?
              AND prev.sequence < ?
              AND prev.status != 'Done'
              AND (
                    prev.is_split_child = 1
                    OR NOT EXISTS (
                        SELECT 1
                        FROM order_jobs child
                        WHERE child.parent_job_id = prev.id
                          AND child.is_split_child = 1
                    )
                  )
        """, (order_id, sequence))
        remaining = cursor.fetchone()[0]
        return remaining == 0

    # Single job arba split parent tikrina ankstesnius vykdomus job'us,
    # bet ignoruoja split parent'us, kurie turi child'us
    cursor.execute("""
        SELECT COUNT(*)
        FROM order_jobs prev
        WHERE prev.order_id = ?
          AND prev.sequence < ?
          AND prev.status != 'Done'
          AND (
                prev.is_split_child = 1
                OR NOT EXISTS (
                    SELECT 1
                    FROM order_jobs child
                    WHERE child.parent_job_id = prev.id
                      AND child.is_split_child = 1
                )
              )
    """, (order_id, sequence))
    remaining = cursor.fetchone()[0]

    return remaining == 0


def sync_order_status(cursor, order_id):
    cursor.execute("""
        SELECT
            oj.id,
            oj.status,
            oj.is_split_child,
            (
                SELECT COUNT(*)
                FROM order_jobs child
                WHERE child.parent_job_id = oj.id
                  AND child.is_split_child = 1
            ) AS child_count
        FROM order_jobs oj
        WHERE oj.order_id = ?
    """, (order_id,))
    jobs = cursor.fetchall()

    if not jobs:
        cursor.execute("""
            UPDATE orders
            SET status = 'Waiting'
            WHERE id = ?
        """, (order_id,))
        return

    executable_statuses = []

    for job in jobs:
        job_status = job[1]
        is_split_child = int(job[2] or 0)
        child_count = int(job[3] or 0)

        # Split parent ignoruojam, nes jis tik reference
        if is_split_child == 0 and child_count > 0:
            continue

        executable_statuses.append(job_status)

    if not executable_statuses:
        new_order_status = "Waiting"
    elif all(status == "Done" for status in executable_statuses):
        new_order_status = "Completed"
    elif any(status == "Ongoing" for status in executable_statuses):
        new_order_status = "In Progress"
    elif any(status == "Paused" for status in executable_statuses):
        new_order_status = "Delayed"
    else:
        new_order_status = "Waiting"

    cursor.execute("""
        UPDATE orders
        SET status = ?
        WHERE id = ?
    """, (new_order_status, order_id))


def create_split_children(cursor, parent_job_id, split_rows):
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
            planned_start
        FROM order_jobs
        WHERE id = ?
    """, (parent_job_id,))
    parent = cursor.fetchone()

    if parent is None:
        raise ValueError("Parent job not found.")

    if float(parent[8] or 0) > 0:
        raise ValueError("Cannot split job that already has completed quantity.")

    if job_has_split_children(cursor, parent_job_id):
        raise ValueError("Job is already split.")

    parent_planned_quantity = float(parent[7] or 0)

    total_split_quantity = sum(float(row["quantity"]) for row in split_rows)

    if not is_float_equal(total_split_quantity, parent_planned_quantity):
        raise ValueError("Split quantities must match original planned quantity.")

    for row in split_rows:
        workstation_id = int(row["workstation_id"])
        split_quantity = float(row["quantity"])

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
                is_split_child
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            parent[1],                  # order_id
            parent[2],                  # product_job_template_id
            parent[3],                  # job_product_id
            workstation_id,             # workstation_id
            parent[5],                  # job_name
            parent[6],                  # sequence
            split_quantity,             # planned_quantity
            0,                          # completed_quantity
            parent[9],                  # estimated_hours
            "Waiting",                  # status
            parent[11],                 # planned_start
            parent[11],                 # planned_end
            parent_job_id,              # parent_job_id
            1                           # is_split_child
        ))

        new_child_id = cursor.lastrowid
        recalculate_job_dates(cursor, new_child_id, parent[11])

    cursor.execute("""
        UPDATE order_jobs
        SET status = 'Paused'
        WHERE id = ?
    """, (parent_job_id,))

    sync_parent_job_status(cursor, parent_job_id)


def rebuild_order_jobs(cursor, order_id, root_product_id, root_quantity, planned_date=None):
    cursor.execute("DELETE FROM order_jobs WHERE order_id = ?", (order_id,))
    generate_order_jobs_recursive(cursor, order_id, root_product_id, root_quantity, planned_date)

def explode_bom_items_recursive(cursor, product_id, required_quantity, collected=None, path=None):
    if collected is None:
        collected = {}

    if path is None:
        path = []

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
        ORDER BY id ASC
    """, (product_id,))
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
                current_path
            )
        else:
            if item_id not in collected:
                collected[item_id] = 0
            collected[item_id] += total_required

    return collected

def consume_job_materials(cursor, product_id, produced_quantity):
    produced_quantity = float(produced_quantity or 0)

    if not product_id or produced_quantity <= 0:
        return

    exploded_items = explode_bom_items_recursive(cursor, product_id, produced_quantity)

    for item_id, required_quantity in exploded_items.items():
        cursor.execute("""
            UPDATE items
            SET stock_quantity = COALESCE(stock_quantity, 0) - ?
            WHERE id = ?
        """, (float(required_quantity or 0), item_id))

def add_finished_product_stock(cursor, product_id, produced_quantity):
    produced_quantity = float(produced_quantity or 0)

    if not product_id or produced_quantity <= 0:
        return

    cursor.execute("""
        UPDATE products
        SET stock_quantity = COALESCE(stock_quantity, 0) + ?
        WHERE id = ?
    """, (produced_quantity, product_id))

def is_final_job(cursor, order_id, job_id):
    cursor.execute("""
        SELECT MAX(sequence)
        FROM order_jobs
        WHERE order_id = ?
    """, (order_id,))
    max_sequence = cursor.fetchone()[0]

    cursor.execute("""
        SELECT sequence
        FROM order_jobs
        WHERE id = ?
    """, (job_id,))
    job_sequence = cursor.fetchone()[0]

    return job_sequence == max_sequence


def reserve_order_materials(cursor, order_id):
    """
    Orders no longer affect inventory.
    This function is kept only for compatibility.
    """
    return False


def calculate_product_material_cost(cursor, product_id):
    try:
        exploded_items = explode_bom_items_recursive(cursor, product_id, 1)
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
    """, item_ids)
    rows = cursor.fetchall()

    total_material_cost = 0

    for item_id, unit_price in rows:
        quantity_per_unit = exploded_items.get(item_id, 0)
        total_material_cost += quantity_per_unit * (unit_price or 0)

    return total_material_cost

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/landing")
def landing():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, full_name, email
            FROM users
            WHERE email = ? AND password = ?
        """, (email, password))

        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_email"] = user[2]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "error")
            return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        company = request.form["company"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (full_name, company, email, password)
                VALUES (?, ?, ?, ?)
            """, (full_name, company, email, password))

            conn.commit()
            conn.close()

            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Email already exists.", "error")
            return render_template("register.html", error="Email already exists")

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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'In Progress'")
    in_progress_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Waiting'")
    waiting_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Completed'")
    completed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Delayed'")
    delayed_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT orders.id, orders.order_number, products.product_name, orders.quantity, orders.status, orders.due_date, orders.priority
        FROM orders
        LEFT JOIN products ON orders.product_id = products.id
        ORDER BY orders.id DESC
        LIMIT 5
    """)
    recent_rows = cursor.fetchall()

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
                  AND oj.status != 'Done'
                  AND (
                        oj.is_split_child = 1
                        OR NOT EXISTS (
                            SELECT 1
                            FROM order_jobs child
                            WHERE child.parent_job_id = oj.id
                              AND child.is_split_child = 1
                        )
                      )
            ), 0) AS used_load
        FROM workstations w
        GROUP BY w.id, w.name, w.hours_per_shift, w.shifts_per_day, w.working_days_per_month
        HAVING used_load > 0
        ORDER BY used_load DESC, w.name ASC
    """)
    workstation_rows = cursor.fetchall()

    conn.close()

    recent_orders = []
    for row in recent_rows:
        recent_orders.append({
            "id": row[0],
            "order_number": row[1],
            "product_name": row[2] if row[2] else "-",
            "quantity": row[3] if row[3] is not None else 1,
            "status": row[4],
            "due_date": row[5],
            "priority": row[6]
        })

    workstation_load = []
    workstation_count = len(workstation_rows)

    if workstation_count <= 2:
        ring_size_class = "load-size-large"
    elif workstation_count <= 4:
        ring_size_class = "load-size-medium"
    elif workstation_count <= 8:
        ring_size_class = "load-size-small"
    else:
        ring_size_class = "load-size-xsmall"

    for row in workstation_rows:
        monthly_capacity = float(row[2] or 0)
        used_load = float(row[3] or 0)
        load_percent = (used_load / monthly_capacity * 100) if monthly_capacity > 0 else 0

        workstation_load.append({
            "id": row[0],
            "name": row[1],
            "monthly_capacity": round(monthly_capacity, 2),
            "used_load": round(used_load, 2),
            "load_percent": round(load_percent, 1),
            "size_class": ring_size_class
        })

    return render_template(
        "dashboard.html",
        total_orders=total_orders,
        in_progress_count=in_progress_count,
        waiting_count=waiting_count,
        completed_count=completed_count,
        delayed_count=delayed_count,
        recent_orders=recent_orders,
        workstation_load=workstation_load,
        active_page="dashboard"
    )


@app.route("/orders")
def orders():
    if not is_logged_in():
        return redirect(url_for("login"))

    order_number = request.args.get("order_number", "").strip()
    product_name = request.args.get("product_name", "").strip()
    priority = request.args.get("priority", "").strip()
    due_date_from = request.args.get("due_date_from", "").strip()
    due_date_to = request.args.get("due_date_to", "").strip()

    statuses = request.args.getlist("status")
    statuses = [s.strip() for s in statuses if s.strip()]

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            o.id,
            o.order_number,
            o.customer,
            o.status,
            o.due_date,
            o.priority,
            o.product_id,
            o.quantity,
            p.product_name
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.id
    """

    conditions = []
    params = []

    if order_number:
        conditions.append("o.order_number LIKE ?")
        params.append(f"%{order_number}%")

    if product_name:
        conditions.append("p.product_name LIKE ?")
        params.append(f"%{product_name}%")

    if priority:
        conditions.append("o.priority = ?")
        params.append(priority)

    if "All" in statuses:
        statuses = []

    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        conditions.append(f"o.status IN ({placeholders})")
        params.extend(statuses)

    if due_date_from:
        conditions.append("o.due_date >= ?")
        params.append(due_date_from)

    if due_date_to:
        conditions.append("o.due_date <= ?")
        params.append(due_date_to)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY o.id DESC"

    cursor.execute(query, params)
    orders = cursor.fetchall()

    conn.close()

    filters = {
        "order_number": order_number,
        "product_name": product_name,
        "priority": priority,
        "status": statuses,
        "due_date_from": due_date_from,
        "due_date_to": due_date_to
    }

    return render_template(
        "orders.html",
        orders=orders,
        filters=filters,
        active_page="orders"
    )


@app.route("/orders/new", methods=["GET", "POST"])
def new_order():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        order_number = request.form.get("order_number", "").strip()
        product_id = request.form.get("product_id", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()
        status = request.form.get("status", "").strip()
        due_date = request.form.get("due_date", "").strip()
        priority = request.form.get("priority", "").strip()

        if not order_number:
            conn.close()
            flash("Order number is required.", "error")
            return redirect(url_for("new_order"))

        if not product_id:
            conn.close()
            flash("Product is required.", "error")
            return redirect(url_for("new_order"))

        if not quantity_raw:
            conn.close()
            flash("Quantity is required.", "error")
            return redirect(url_for("new_order"))

        try:
            quantity = float(quantity_raw)
        except ValueError:
            conn.close()
            flash("Quantity must be a valid number.", "error")
            return redirect(url_for("new_order"))

        if quantity <= 0:
            conn.close()
            flash("Quantity must be greater than 0.", "error")
            return redirect(url_for("new_order"))

        if not status:
            conn.close()
            flash("Status is required.", "error")
            return redirect(url_for("new_order"))

        if not due_date:
            conn.close()
            flash("Due date is required.", "error")
            return redirect(url_for("new_order"))

        if not priority:
            conn.close()
            flash("Priority is required.", "error")
            return redirect(url_for("new_order"))

        cursor.execute("""
            INSERT INTO orders (order_number, customer, product_id, quantity, status, due_date, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (order_number, "", product_id, quantity, status, due_date, priority))

        order_id = cursor.lastrowid

        try:
            generate_order_jobs_recursive(cursor, order_id, int(product_id), quantity, due_date)
        except ValueError as e:
            conn.rollback()
            conn.close()
            flash(str(e), "error")
            return redirect(url_for("new_order"))

        conn.commit()
        conn.close()

        flash("Order created successfully.", "success")
        return redirect(url_for("orders"))

    cursor.execute("""
        SELECT id, product_code, product_name
        FROM products
        ORDER BY product_name ASC
    """)
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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        order_number = request.form["order_number"]
        product_id = request.form["product_id"]
        quantity = float(request.form["quantity"])
        status = request.form["status"]
        due_date = request.form["due_date"]
        priority = request.form["priority"]

        cursor.execute("""
            UPDATE orders
            SET order_number = ?, product_id = ?, quantity = ?, status = ?, due_date = ?, priority = ?
            WHERE id = ?
        """, (order_number, product_id, quantity, status, due_date, priority, order_id))

        try:
            rebuild_order_jobs(cursor, order_id, int(product_id), quantity, due_date)
        except ValueError as e:
            conn.rollback()
            conn.close()
            flash(str(e), "error")
            return redirect(url_for("edit_order", order_id=order_id))

        conn.commit()
        conn.close()

        flash("Order updated successfully.", "success")
        return redirect(url_for("orders"))

    cursor.execute("""
        SELECT id, order_number, product_id, quantity, status, due_date, priority
        FROM orders
        WHERE id = ?
    """, (order_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return "Order not found", 404

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
        ORDER BY product_name ASC
    """)
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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            orders.id,
            orders.order_number,
            orders.product_id,
            orders.quantity,
            products.product_name
        FROM orders
        LEFT JOIN products ON orders.product_id = products.id
        WHERE orders.id = ?
    """, (order_id,))
    order_row = cursor.fetchone()

    if order_row is None:
        conn.close()
        return "Order not found", 404

    order = {
        "id": order_row[0],
        "order_number": order_row[1],
        "product_id": order_row[2],
        "quantity": order_row[3] if order_row[3] is not None else 1,
        "product_name": order_row[4] if order_row[4] else "-"
    }

    if order["product_id"] is None:
        conn.close()
        flash("Order has no product assigned.", "error")
        return redirect(url_for("orders"))

    try:
        exploded_items = explode_bom_items_recursive(
            cursor,
            order["product_id"],
            float(order["quantity"])
        )
    except ValueError as e:
        conn.close()
        flash(str(e), "error")
        return redirect(url_for("orders"))

    materials = []
    total_material_cost = 0

    if exploded_items:
        item_ids = list(exploded_items.keys())
        placeholders = ",".join(["?"] * len(item_ids))

        cursor.execute(f"""
            SELECT
                id,
                item_code,
                item_name,
                measurement_unit,
                unit_price
            FROM items
            WHERE id IN ({placeholders})
            ORDER BY item_name ASC
        """, item_ids)
        item_rows = cursor.fetchall()

        for row in item_rows:
            item_id = row[0]
            total_quantity = exploded_items.get(item_id, 0)
            unit_price = row[4] if row[4] is not None else 0
            total_cost = total_quantity * unit_price
            total_material_cost += total_cost

            materials.append({
                "item_code": row[1],
                "item_name": row[2],
                "unit": row[3],
                "bom_quantity": total_quantity / float(order["quantity"]) if float(order["quantity"]) > 0 else 0,
                "total_quantity": total_quantity,
                "unit_price": unit_price,
                "total_cost": total_cost
            })

    conn.close()

    return render_template(
        "order_materials.html",
        order=order,
        materials=materials,
        total_material_cost=total_material_cost,
        active_page="orders"
    )

@app.route("/orders/delete/<int:order_id>", methods=["POST"])
def delete_order(order_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM order_jobs
        WHERE order_id = ?
    """, (order_id,))

    cursor.execute("""
        DELETE FROM orders
        WHERE id = ?
    """, (order_id,))

    conn.commit()
    conn.close()

    flash("Order deleted successfully.", "success")
    return redirect(url_for("orders"))


@app.route("/items")
def items():
    if not is_logged_in():
        return redirect(url_for("login"))

    item_code = request.args.get("item_code", "").strip()
    item_name = request.args.get("item_name", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT id, item_code, item_name, description, measurement_unit, unit_price, stock_quantity, min_stock
        FROM items
    """

    conditions = []
    params = []

    if item_code:
        conditions.append("item_code LIKE ?")
        params.append(f"%{item_code}%")

    if item_name:
        conditions.append("item_name LIKE ?")
        params.append(f"%{item_name}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

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

    if request.method == "POST":
        item_code = request.form["item_code"]
        item_name = request.form["item_name"]
        description = request.form["description"]
        measurement_unit = request.form["measurement_unit"]
        unit_price = float(request.form["unit_price"] or 0)
        stock_quantity = float(request.form["stock_quantity"] or 0)
        min_stock = float(request.form["min_stock"] or 0)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO items (
                item_code, item_name, description, measurement_unit, unit_price, stock_quantity, min_stock
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_code, item_name, description, measurement_unit, unit_price, stock_quantity, min_stock))

        conn.commit()
        conn.close()

        flash("Item created successfully.", "success")
        return redirect(url_for("items"))

    return render_template(
        "new_item.html",
        active_page="items"
    )


@app.route("/items/edit/<int:item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        item_code = request.form["item_code"]
        item_name = request.form["item_name"]
        description = request.form["description"]
        measurement_unit = request.form["measurement_unit"]
        unit_price = float(request.form["unit_price"] or 0)
        stock_quantity = float(request.form["stock_quantity"] or 0)
        min_stock = float(request.form["min_stock"] or 0)

        cursor.execute("""
            UPDATE items
            SET item_code = ?, item_name = ?, description = ?, measurement_unit = ?, unit_price = ?, stock_quantity = ?, min_stock = ?
            WHERE id = ?
        """, (item_code, item_name, description, measurement_unit, unit_price, stock_quantity, min_stock, item_id))

        conn.commit()
        conn.close()

        flash("Item updated successfully.", "success")
        return redirect(url_for("items"))

    cursor.execute("""
        SELECT id, item_code, item_name, description, measurement_unit, unit_price, stock_quantity, min_stock
        FROM items
        WHERE id = ?
    """, (item_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return "Item not found", 404

    item = {
        "id": row[0],
        "item_code": row[1],
        "item_name": row[2],
        "description": row[3],
        "measurement_unit": row[4],
        "unit_price": row[5] if row[5] is not None else 0,
        "stock_quantity": row[6] if row[6] is not None else 0,
        "min_stock": row[7] if row[7] is not None else 0
    }

    return render_template(
        "edit_item.html",
        item=item,
        active_page="items"
    )


@app.route("/items/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))

    conn.commit()
    conn.close()

    flash("Item deleted successfully.", "info")
    return redirect(url_for("items"))


@app.route("/products")
def products():
    if not is_logged_in():
        return redirect(url_for("login"))

    product_code = request.args.get("product_code", "").strip()
    product_name = request.args.get("product_name", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    query = """
        SELECT id, product_code, product_name, description, measurement_unit, time_per_unit, stock_quantity
        FROM products
    """

    conditions = []
    params = []

    if product_code:
        conditions.append("product_code LIKE ?")
        params.append(f"%{product_code}%")

    if product_name:
        conditions.append("product_name LIKE ?")
        params.append(f"%{product_name}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

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
            "time_per_unit": row[5],
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

    if request.method == "POST":
        product_code = request.form["product_code"]
        product_name = request.form["product_name"]
        description = request.form["description"]
        measurement_unit = request.form["measurement_unit"]
        time_per_unit = request.form["time_per_unit"]
        stock_quantity = float(request.form["stock_quantity"] or 0)

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO products (
                product_code, product_name, description, measurement_unit, time_per_unit, stock_quantity
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product_code, product_name, description, measurement_unit, time_per_unit, stock_quantity))

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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        product_code = request.form["product_code"]
        product_name = request.form["product_name"]
        description = request.form["description"]
        measurement_unit = request.form["measurement_unit"]
        time_per_unit = request.form["time_per_unit"]
        stock_quantity = float(request.form["stock_quantity"] or 0)

        cursor.execute("""
            UPDATE products
            SET product_code = ?, product_name = ?, description = ?, measurement_unit = ?, time_per_unit = ?, stock_quantity = ?
            WHERE id = ?
        """, (product_code, product_name, description, measurement_unit, time_per_unit, stock_quantity, product_id))

        conn.commit()
        conn.close()

        flash("Product updated successfully.", "success")
        return redirect(url_for("products"))

    cursor.execute("""
        SELECT id, product_code, product_name, description, measurement_unit, time_per_unit, stock_quantity
        FROM products
        WHERE id = ?
    """, (product_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return "Product not found", 404

    product = {
        "id": row[0],
        "product_code": row[1],
        "product_name": row[2],
        "description": row[3],
        "measurement_unit": row[4],
        "time_per_unit": row[5],
        "stock_quantity": row[6] if row[6] is not None else 0
    }

    return render_template(
        "edit_product.html",
        product=product,
        active_page="products"
    )


@app.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))

    conn.commit()
    conn.close()

    flash("Product deleted successfully.", "info")
    return redirect(url_for("products"))

@app.route("/products/<int:product_id>/jobs")
def product_jobs(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_code, product_name, description, measurement_unit, time_per_unit
        FROM products
        WHERE id = ?
    """, (product_id,))
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
        JOIN workstations w ON pjt.workstation_id = w.id
        WHERE pjt.product_id = ?
        ORDER BY pjt.sequence ASC, pjt.id ASC
    """, (product_id,))
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
        ORDER BY name ASC
    """)
    workstation_rows = cursor.fetchall()

    workstations = []
    for row in workstation_rows:
        workstations.append({
            "id": row[0],
            "name": row[1]
        })

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

    job_name = request.form["job_name"]
    workstation_id = request.form["workstation_id"]
    sequence = request.form["sequence"]
    estimated_hours = request.form["estimated_hours"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO product_job_templates (
            product_id, workstation_id, job_name, sequence, estimated_hours
        )
        VALUES (?, ?, ?, ?, ?)
    """, (product_id, workstation_id, job_name, sequence, estimated_hours))

    conn.commit()
    conn.close()

    flash("Product job template added successfully.", "success")
    return redirect(url_for("product_jobs", product_id=product_id))


@app.route("/products/jobs/edit/<int:job_id>", methods=["GET", "POST"])
def edit_product_job(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        job_name = request.form["job_name"]
        workstation_id = request.form["workstation_id"]
        sequence = request.form["sequence"]
        estimated_hours = request.form["estimated_hours"]

        cursor.execute("""
            UPDATE product_job_templates
            SET job_name = ?, workstation_id = ?, sequence = ?, estimated_hours = ?
            WHERE id = ?
        """, (job_name, workstation_id, sequence, estimated_hours, job_id))

        cursor.execute("""
            SELECT product_id
            FROM product_job_templates
            WHERE id = ?
        """, (job_id,))
        row = cursor.fetchone()

        conn.commit()
        conn.close()

        flash("Product job template updated successfully.", "success")
        return redirect(url_for("product_jobs", product_id=row[0]))

    cursor.execute("""
        SELECT id, product_id, workstation_id, job_name, sequence, estimated_hours
        FROM product_job_templates
        WHERE id = ?
    """, (job_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return "Product job template not found", 404

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
        ORDER BY name ASC
    """)
    workstation_rows = cursor.fetchall()

    workstations = []
    for workstation_row in workstation_rows:
        workstations.append({
            "id": workstation_row[0],
            "name": workstation_row[1]
        })

    cursor.execute("""
        SELECT id, product_code, product_name
        FROM products
        WHERE id = ?
    """, (job_template["product_id"],))
    product_row = cursor.fetchone()

    product = {
        "id": product_row[0],
        "product_code": product_row[1],
        "product_name": product_row[2]
    }

    conn.close()

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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT product_id
        FROM product_job_templates
        WHERE id = ?
    """, (job_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("Product job template not found.", "error")
        return redirect(url_for("products"))

    product_id = row[0]

    cursor.execute("DELETE FROM product_job_templates WHERE id = ?", (job_id,))

    conn.commit()
    conn.close()

    flash("Product job template deleted successfully.", "info")
    return redirect(url_for("product_jobs", product_id=product_id))


@app.route("/bom/<int:product_id>")
def product_bom(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_code, product_name, description, measurement_unit, time_per_unit
        FROM products
        WHERE id = ?
    """, (product_id,))
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
        LEFT JOIN items ON bom.item_id = items.id AND bom.component_type = 'item'
        LEFT JOIN products ON bom.child_product_id = products.id AND bom.component_type = 'product'
        WHERE bom.product_id = ?
        ORDER BY bom.id DESC
    """, (product_id,))
    bom_rows = cursor.fetchall()

    bom_items = []
    for row in bom_rows:
        component_type = row[1]

        if component_type == "product":
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
        ORDER BY item_name ASC
    """)
    item_rows = cursor.fetchall()

    items = []
    for row in item_rows:
        items.append({
            "id": row[0],
            "item_code": row[1],
            "item_name": row[2],
            "measurement_unit": row[3]
        })

    cursor.execute("""
        SELECT id, product_code, product_name, measurement_unit
        FROM products
        WHERE id != ?
        ORDER BY product_name ASC
    """, (product_id,))
    product_rows = cursor.fetchall()

    child_products = []
    for row in product_rows:
        child_products.append({
            "id": row[0],
            "product_code": row[1],
            "product_name": row[2],
            "measurement_unit": row[3]
        })

    conn.close()

    return render_template(
        "bom.html",
        product=product,
        bom_items=bom_items,
        items=items,
        child_products=child_products,
        active_page="bom"
    )


@app.route("/products/<int:product_id>/cost")
def product_cost(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_code, product_name, measurement_unit
        FROM products
        WHERE id = ?
    """, (product_id,))
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
        exploded_items = explode_bom_items_recursive(cursor, product_id, 1)
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
            SELECT
                id,
                item_code,
                item_name,
                measurement_unit,
                unit_price
            FROM items
            WHERE id IN ({placeholders})
            ORDER BY item_name ASC
        """, item_ids)
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

    component_type = request.form["component_type"]
    quantity = request.form["quantity"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if component_type == "product":
        child_product_id = request.form["child_product_id"]

        if str(child_product_id) == str(product_id):
            conn.close()
            flash("Product cannot contain itself in BOM.", "error")
            return redirect(url_for("product_bom", product_id=product_id))

        cursor.execute("""
            INSERT INTO bom (product_id, item_id, child_product_id, component_type, quantity)
            VALUES (?, ?, ?, ?, ?)
        """, (product_id, 0, child_product_id, "product", quantity))

    else:
        item_id = request.form["item_id"]

        cursor.execute("""
            INSERT INTO bom (product_id, item_id, child_product_id, component_type, quantity)
            VALUES (?, ?, ?, ?, ?)
        """, (product_id, item_id, None, "item", quantity))

    conn.commit()
    conn.close()

    flash("BOM component added successfully.", "success")
    return redirect(url_for("product_bom", product_id=product_id))
@app.route("/bom/delete/<int:bom_id>", methods=["POST"])
def delete_bom_item(bom_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT product_id FROM bom WHERE id = ?", (bom_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        flash("BOM item not found.", "error")
        return redirect(url_for("products"))

    product_id = row[0]

    cursor.execute("DELETE FROM bom WHERE id = ?", (bom_id,))

    conn.commit()
    conn.close()

    flash("BOM item deleted successfully.", "info")
    return redirect(url_for("product_bom", product_id=product_id))


@app.route("/workstations/new", methods=["GET", "POST"])



@app.route("/workstations/new", methods=["GET", "POST"])


@app.route("/workstations/new", methods=["GET", "POST"])
def new_workstation():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        hours_per_shift = request.form["hours_per_shift"]
        shifts_per_day = request.form["shifts_per_day"]
        working_days_per_month = request.form["working_days_per_month"]
        color = request.form["color"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO workstations (name, description, hours_per_shift, shifts_per_day, working_days_per_month, color)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            description,
            hours_per_shift,
            shifts_per_day,
            working_days_per_month,
            color
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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        hours_per_shift = request.form["hours_per_shift"]
        shifts_per_day = request.form["shifts_per_day"]
        working_days_per_month = request.form["working_days_per_month"]
        color = request.form["color"]

        cursor.execute("""
            UPDATE workstations
            SET name = ?, description = ?, hours_per_shift = ?, shifts_per_day = ?, working_days_per_month = ?, color = ?
            WHERE id = ?
        """, (name, description, hours_per_shift, shifts_per_day, working_days_per_month, color, workstation_id))

        conn.commit()
        conn.close()

        flash("Workstation updated successfully.", "success")
        return redirect(url_for("workstations"))

    cursor.execute("""
        SELECT id, name, description, hours_per_shift, shifts_per_day, working_days_per_month, color
        FROM workstations
        WHERE id = ?
    """, (workstation_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return "Workstation not found", 404

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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM workstations WHERE id = ?", (workstation_id,))

    conn.commit()
    conn.close()

    flash("Workstation deleted successfully.", "info")
    return redirect(url_for("workstations"))



@app.route("/jobs")
def jobs():
    if not is_logged_in():
        return redirect(url_for("login"))

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
            ) AS child_count
        FROM order_jobs oj
        JOIN orders o ON oj.order_id = o.id
        LEFT JOIN products jp ON oj.job_product_id = jp.id
        JOIN workstations w ON oj.workstation_id = w.id
    """

    conditions = []
    params = []

    if order_number:
        conditions.append("o.order_number LIKE ?")
        params.append(f"%{order_number}%")

    if product_name:
        conditions.append("jp.product_name LIKE ?")
        params.append(f"%{product_name}%")

    if job_name:
        conditions.append("oj.job_name LIKE ?")
        params.append(f"%{job_name}%")

    if workstation:
        conditions.append("CAST(oj.workstation_id AS TEXT) = ?")
        params.append(workstation)

    if workstation_text:
        conditions.append("w.name LIKE ?")
        params.append(f"%{workstation_text}%")

    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        conditions.append(f"oj.status IN ({placeholders})")
        params.extend(statuses)

    if due_date_from:
        conditions.append("o.due_date >= ?")
        params.append(due_date_from)

    if due_date_to:
        conditions.append("o.due_date <= ?")
        params.append(due_date_to)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        ORDER BY
            o.id DESC,
            CASE WHEN oj.parent_job_id IS NULL THEN oj.id ELSE oj.parent_job_id END ASC,
            oj.is_split_child ASC,
            oj.id ASC
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()

    jobs = []
    for row in rows:
        job_id = row[0]
        child_count = int(row[16] or 0)

        jobs.append({
            "id": job_id,
            "order_number": row[1],
            "product_name": row[2] if row[2] else "-",
            "job_name": row[3],
            "workstation": row[4],
            "workstation_id": row[5],
            "sequence": row[6],
            "planned_quantity": row[7],
            "completed_quantity": row[8],
            "estimated_hours": row[9],
            "status": row[10],
            "due_date": row[11],
            "planned_start": row[12],
            "planned_end": row[13],
            "parent_job_id": row[14],
            "is_split_child": int(row[15] or 0),
            "child_count": child_count,
            "can_start": can_start_job(cursor, job_id) if child_count == 0 else False
        })

    cursor.execute("""
        SELECT id, name
        FROM workstations
        ORDER BY name ASC
    """)
    ws_rows = cursor.fetchall()

    workstations = []
    for w in ws_rows:
        workstations.append({
            "id": w[0],
            "name": w[1]
        })

    conn.close()

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

    new_workstation_id = request.form["workstation_id"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE order_jobs
        SET workstation_id = ?
        WHERE id = ?
    """, (new_workstation_id, job_id))

    recalculate_job_dates(cursor, job_id)

    conn.commit()
    conn.close()

    flash("Workstation updated.", "success")
    return redirect(request.referrer or url_for("jobs"))

@app.route("/jobs/update_status/<int:job_id>/<string:new_status>", methods=["POST"])
@app.route("/jobs/update_status/<int:job_id>/<new_status>", methods=["POST"])
def update_job_status(job_id, new_status):
    if not is_logged_in():
        return redirect(url_for("login"))

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
        WHERE id = ?
    """, (job_id,))
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
    current_status = row[5]

    if new_status == "Ongoing":
        if not can_start_job(cursor, job_id):
            conn.close()
            flash("Cannot start this job yet. Previous sequence jobs are not done.", "error")
            return redirect_back("jobs")

        reserve_order_materials(cursor, order_id)

        cursor.execute("""
            UPDATE order_jobs
            SET status = ?
            WHERE id = ?
        """, (new_status, job_id))

    elif new_status == "Done":
        quantity_to_finish = planned_quantity - completed_quantity
        if quantity_to_finish < 0:
            quantity_to_finish = 0

        if current_status != "Done" and quantity_to_finish > 0:
            try:
                # 1. nurašom medžiagas
                consume_job_materials(cursor, job_product_id, quantity_to_finish)

                # 2. tik jei tai FINAL job → pridedam produktą
                if is_final_job(cursor, order_id, job_id):
                    add_finished_product_stock(cursor, job_product_id, quantity_to_finish)

            except ValueError as e:
                conn.rollback()
                conn.close()
                flash(str(e), "error")
                return redirect_back("jobs")

        cursor.execute("""
            UPDATE order_jobs
            SET status = ?, completed_quantity = ?
            WHERE id = ?
        """, ("Done", planned_quantity, job_id))

    else:
        cursor.execute("""
            UPDATE order_jobs
            SET status = ?
            WHERE id = ?
        """, (new_status, job_id))

    if parent_job_id:
        sync_parent_job_status(cursor, parent_job_id)

    sync_order_status(cursor, order_id)

    conn.commit()
    conn.close()

    flash("Job status updated.", "success")
    return redirect(request.referrer or url_for("jobs"))


@app.route("/jobs/update_progress/<int:job_id>", methods=["POST"])
def update_job_progress(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    completed_quantity = float(request.form.get("completed_quantity", 0) or 0)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT planned_quantity, parent_job_id, order_id
        FROM order_jobs
        WHERE id = ?
    """, (job_id,))
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
    """, (completed_quantity, new_status, job_id))

    recalculate_job_dates(cursor, job_id)

    if parent_job_id:
        sync_parent_job_status(cursor, parent_job_id)

    sync_order_status(cursor, order_id)

    conn.commit()
    conn.close()

    flash("Job progress updated.", "success")
    return redirect_back("jobs")


@app.route("/inventory")
def inventory():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            item_code,
            item_name,
            measurement_unit,
            unit_price,
            stock_quantity,
            min_stock
        FROM items
        ORDER BY item_name ASC
    """)
    item_rows = cursor.fetchall()

    items_inventory = []
    total_items_value = 0

    for row in item_rows:
        real_stock_quantity = float(row[5] or 0)
        display_stock_quantity = max(0, real_stock_quantity)
        unit_price = float(row[4] or 0)
        min_stock = float(row[6] or 0)

        stock_value = display_stock_quantity * unit_price
        total_items_value += stock_value

        if real_stock_quantity <= 0:
            stock_status = "Out"
        elif real_stock_quantity <= min_stock:
            stock_status = "Low"
        else:
            stock_status = "OK"

        items_inventory.append({
            "id": row[0],
            "item_code": row[1],
            "item_name": row[2],
            "measurement_unit": row[3],
            "unit_price": unit_price,
            "stock_quantity": display_stock_quantity,
            "real_stock_quantity": real_stock_quantity,
            "min_stock": min_stock,
            "stock_value": stock_value,
            "stock_status": stock_status
        })

    cursor.execute("""
        SELECT
            id,
            product_code,
            product_name,
            measurement_unit,
            stock_quantity
        FROM products
        ORDER BY product_name ASC
    """)
    product_rows = cursor.fetchall()

    products_inventory = []
    total_products_value = 0

    for row in product_rows:
        product_id = row[0]
        stock_quantity = float(row[4] or 0)
        material_cost_per_unit = float(calculate_product_material_cost(cursor, product_id) or 0)
        stock_value = max(0, stock_quantity) * material_cost_per_unit
        total_products_value += stock_value

        products_inventory.append({
            "id": product_id,
            "product_code": row[1],
            "product_name": row[2],
            "measurement_unit": row[3],
            "stock_quantity": max(0, stock_quantity),
            "real_stock_quantity": stock_quantity,
            "material_cost_per_unit": material_cost_per_unit,
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


@app.route("/inventory/items/<int:item_id>/add-stock", methods=["POST"])
def add_item_stock(item_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    add_quantity = float(request.form.get("add_quantity", 0) or 0)
    

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE items
        SET stock_quantity = stock_quantity + ?
        WHERE id = ?
    """, (add_quantity, item_id))

    conn.commit()
    conn.close()

    flash("Item stock added.", "success")
    return redirect(request.referrer or url_for("inventory"))

@app.route("/inventory/products/<int:product_id>/add-stock", methods=["POST"])
def add_product_stock(product_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    add_quantity = float(request.form.get("add_quantity", 0) or 0)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products
        SET stock_quantity = stock_quantity + ?
        WHERE id = ?
    """, (add_quantity, product_id))

    conn.commit()
    conn.close()

    flash("Product stock added.", "success")
    return redirect(request.referrer or url_for("inventory"))

@app.route("/materials-shortage")
def materials_shortage():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            product_id,
            quantity,
            order_number,
            status
        FROM orders
        WHERE product_id IS NOT NULL
          AND status IN ('Waiting', 'In Progress', 'Delayed')
        ORDER BY id DESC
    """)
    order_rows = cursor.fetchall()

    required_by_item = {}

    for order_id, product_id, order_quantity, order_number, status in order_rows:
        if not product_id:
            continue

        try:
            exploded_items = explode_bom_items_recursive(
                cursor,
                product_id,
                float(order_quantity or 0)
            )
        except ValueError:
            continue

        for item_id, required_qty in exploded_items.items():
            if item_id not in required_by_item:
                required_by_item[item_id] = 0
            required_by_item[item_id] += float(required_qty or 0)

    shortage_items = []

    if required_by_item:
        item_ids = list(required_by_item.keys())
        placeholders = ",".join(["?"] * len(item_ids))

        cursor.execute(f"""
            SELECT
                id,
                item_code,
                item_name,
                measurement_unit,
                unit_price,
                stock_quantity,
                min_stock
            FROM items
            WHERE id IN ({placeholders})
            ORDER BY item_name ASC
        """, item_ids)
        rows = cursor.fetchall()

        for row in rows:
            item_id = row[0]
            item_code = row[1]
            item_name = row[2]
            measurement_unit = row[3]
            unit_price = float(row[4] or 0)
            stock_quantity = float(row[5] or 0)
            min_stock = float(row[6] or 0)

            required_quantity = float(required_by_item.get(item_id, 0))
            available_stock = max(0, stock_quantity)

            required_to_order = max(0, required_quantity - available_stock)

            if required_to_order > 0:
                shortage_items.append({
                    "id": item_id,
                    "item_code": item_code,
                    "item_name": item_name,
                    "unit": measurement_unit,
                    "stock_quantity": available_stock,
                    "real_stock_quantity": stock_quantity,
                    "min_stock": min_stock,
                    "required_quantity": required_quantity,
                    "required_to_order": required_to_order,
                    "shortage_value": required_to_order * unit_price,
                    "status": "Out of stock" if available_stock <= 0 else "Below required"
                })

    conn.close()

    return render_template(
        "materials_shortage.html",
        shortage_items=shortage_items,
        active_page="shortage"
    )


@app.route("/planner")
def planner():
    if not is_logged_in():
        return redirect(url_for("login"))

    today = datetime.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    month_days = build_month_days(year, month)
    month_start = month_days[0]["date"]
    month_end = month_days[-1]["date"]

    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

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
        ORDER BY w.name ASC
    """)
    workstation_rows = cursor.fetchall()

    workstations = []
    for row in workstation_rows:
        workstations.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "hours_per_shift": row[3],
            "shifts_per_day": row[4],
            "working_days_per_month": row[5],
            "color": row[6]
        })

    cursor.execute("""
        SELECT
            oj.id,
            oj.workstation_id,
            o.order_number,
            COALESCE(jp.product_name, '-') AS product_name,
            oj.job_name,
            oj.status,
            oj.planned_start,
            oj.planned_end,
            oj.estimated_hours,
            oj.planned_quantity,
            oj.completed_quantity,
            oj.parent_job_id,
            oj.is_split_child,
            (
                SELECT COUNT(*)
                FROM order_jobs child
                WHERE child.parent_job_id = oj.id
                  AND child.is_split_child = 1
            ) AS child_count
        FROM order_jobs oj
        JOIN orders o ON oj.order_id = o.id
        LEFT JOIN products jp ON oj.job_product_id = jp.id
        ORDER BY oj.workstation_id ASC, oj.planned_start ASC, oj.id ASC
    """)
    job_rows = cursor.fetchall()
    conn.close()

    workstation_map = {ws["id"]: ws for ws in workstations}

    jobs_by_workstation = {}
    for ws in workstations:
        jobs_by_workstation[ws["id"]] = []

    unscheduled_jobs = []

    for row in job_rows:
        child_count = int(row[13] or 0)

        if child_count > 0:
            continue

        job_id = row[0]
        workstation_id = row[1]
        planned_start = row[6]
        planned_end = row[7]

        planned_quantity = float(row[9] or 0)
        completed_quantity = float(row[10] or 0)

        if planned_quantity > 0:
            progress_percent = round((completed_quantity / planned_quantity) * 100, 1)
        else:
            progress_percent = 0

        job = {
            "id": job_id,
            "workstation_id": workstation_id,
            "order_number": row[2],
            "product_name": row[3],
            "job_name": row[4],
            "status": row[5],
            "planned_start": planned_start,
            "planned_end": planned_end,
            "estimated_hours": row[8],
            "planned_quantity": planned_quantity,
            "completed_quantity": completed_quantity,
            "progress_percent": progress_percent,
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
        return redirect(url_for("login"))

    planned_start = request.form.get("planned_start", "").strip()

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    recalculate_job_dates(cursor, job_id, planned_start or None)
    conn.commit()
    conn.close()

    return ("", 204)

@app.route("/jobs/split/<int:job_id>", methods=["POST"])
def split_job(job_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    workstation_ids = request.form.getlist("split_workstation_id")
    quantities = request.form.getlist("split_quantity")

    split_rows = []

    for workstation_id, quantity in zip(workstation_ids, quantities):
        workstation_id = workstation_id.strip()
        quantity = quantity.strip()

        if not workstation_id or not quantity:
            continue

        try:
            qty_value = float(quantity)
        except ValueError:
            return redirect_back("jobs")

        if qty_value <= 0:
            continue

        split_rows.append({
            "workstation_id": workstation_id,
            "quantity": qty_value
        })

    if len(split_rows) < 2:
        flash("Split requires at least 2 valid rows.", "error")
        return redirect_back("jobs")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        create_split_children(cursor, job_id, split_rows)
        conn.commit()
        flash("Job split successfully.", "success")
    except ValueError as e:
        conn.rollback()
        flash(str(e), "error")
    finally:
        conn.close()

    return redirect_back("jobs")


@app.route("/workstations")
def workstations():
    if not is_logged_in():
        return redirect(url_for("login"))

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
                  AND oj.status != 'Done'
                  AND (
                        oj.is_split_child = 1
                        OR NOT EXISTS (
                            SELECT 1
                            FROM order_jobs child
                            WHERE child.parent_job_id = oj.id
                              AND child.is_split_child = 1
                        )
                      )
            ), 0) AS used_load
        FROM workstations w
        ORDER BY w.name ASC
    """)

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


if __name__ == "__main__":
    init_db()
    seed_data()
    app.run(debug=True)