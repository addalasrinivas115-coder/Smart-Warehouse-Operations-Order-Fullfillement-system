import sqlite3

DATABASE = "warehouse.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # -------------------------
    # INVENTORY TABLE
    # -------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL,
            reserved INTEGER DEFAULT 0,
            reorder_level INTEGER NOT NULL,
            location TEXT NOT NULL
        )
    """)

    # -------------------------
    # ORDERS TABLE
    # -------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer TEXT NOT NULL,
            sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            priority TEXT NOT NULL,
            priority_score INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL,
            allocated_quantity INTEGER DEFAULT 0,
            shortage_quantity INTEGER DEFAULT 0
        )
    """)

    # -------------------------
    # SAMPLE INVENTORY
    # -------------------------
    products = [
        ("LAP-001", "Laptop", "Electronics", 25, 8, 10, "A-01"),
        ("MOU-001", "Wireless Mouse", "Accessories", 6, 2, 10, "A-02"),
        ("KEY-001", "Keyboard", "Accessories", 15, 4, 8, "A-03"),
        ("MON-001", "Monitor", "Electronics", 3, 1, 5, "B-01"),
        ("HDP-001", "Headphones", "Accessories", 0, 0, 5, "B-02"),
        ("PHN-001", "Smartphone", "Electronics", 30, 12, 10, "C-01")
    ]

    for product in products:
        try:
            conn.execute("""
                INSERT INTO inventory
                (sku, name, category, stock, reserved,
                 reorder_level, location)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, product)
        except sqlite3.IntegrityError:
            pass

    # -------------------------
    # SAMPLE ORDERS
    # -------------------------
    orders = [
        (
            "#1042",
            "Customer A",
            "LAP-001",
            "Laptop",
            10,
            "CRITICAL",
            100,
            "Today",
            "Pending",
            0,
            0
        ),

        (
            "#1043",
            "Customer B",
            "MOU-001",
            "Wireless Mouse",
            5,
            "HIGH",
            75,
            "Today",
            "Pending",
            0,
            0
        ),

        (
            "#1044",
            "Customer C",
            "KEY-001",
            "Keyboard",
            3,
            "NORMAL",
            50,
            "Tomorrow",
            "Pending",
            0,
            0
        ),

        (
            "#1045",
            "Customer D",
            "MON-001",
            "Monitor",
            2,
            "NORMAL",
            40,
            "Tomorrow",
            "Pending",
            0,
            0
        ),

        (
            "#1046",
            "Customer E",
            "HDP-001",
            "Headphones",
            4,
            "HIGH",
            80,
            "Today",
            "Pending",
            0,
            0
        )
    ]

    for order in orders:
        try:
            conn.execute("""
                INSERT INTO orders
                (
                    order_number,
                    customer,
                    sku,
                    product_name,
                    quantity,
                    priority,
                    priority_score,
                    due_date,
                    status,
                    allocated_quantity,
                    shortage_quantity
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, order)
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()