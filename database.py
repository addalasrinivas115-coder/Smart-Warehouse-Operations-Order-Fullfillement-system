import sqlite3
from datetime import datetime, timedelta

DATABASE = "warehouse.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table_name, column_name, column_def):
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row[1] for row in columns}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            reserved INTEGER NOT NULL DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 0,
            location TEXT NOT NULL DEFAULT 'A-01',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer TEXT NOT NULL,
            sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'NORMAL',
            priority_score INTEGER NOT NULL DEFAULT 0,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            allocated_quantity INTEGER NOT NULL DEFAULT 0,
            shortage_quantity INTEGER NOT NULL DEFAULT 0,
            picking_status TEXT NOT NULL DEFAULT 'PENDING',
            packing_status TEXT NOT NULL DEFAULT 'PENDING',
            dispatch_status TEXT NOT NULL DEFAULT 'PENDING',
            dispatch_time TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_name TEXT,
            exception_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'MEDIUM',
            status TEXT NOT NULL DEFAULT 'OPEN',
            recommended_resolution TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type TEXT NOT NULL,
            title TEXT NOT NULL,
            order_id INTEGER,
            product_name TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'GENERAL',
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    ensure_column(conn, 'inventory', 'reserved', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'inventory', 'reorder_level', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'inventory', 'location', 'TEXT NOT NULL DEFAULT "A-01"')
    ensure_column(conn, 'orders', 'picking_status', 'TEXT NOT NULL DEFAULT "PENDING"')
    ensure_column(conn, 'orders', 'packing_status', 'TEXT NOT NULL DEFAULT "PENDING"')
    ensure_column(conn, 'orders', 'dispatch_status', 'TEXT NOT NULL DEFAULT "PENDING"')
    ensure_column(conn, 'orders', 'dispatch_time', 'TEXT')
    ensure_column(conn, 'orders', 'allocated_quantity', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'orders', 'shortage_quantity', 'INTEGER NOT NULL DEFAULT 0')

    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    inventory_count = conn.execute('SELECT COUNT(*) FROM inventory').fetchone()[0]
    if inventory_count == 0:
        products = [
            ("LAP-001", "Laptop", "Electronics", 25, 8, 10, "A-01"),
            ("MOU-001", "Wireless Mouse", "Accessories", 6, 2, 10, "A-02"),
            ("KEY-001", "Keyboard", "Accessories", 15, 4, 8, "A-03"),
            ("MON-001", "Monitor", "Electronics", 3, 1, 5, "B-01"),
            ("HDP-001", "Headphones", "Accessories", 0, 0, 5, "B-02"),
            ("PHN-001", "Smartphone", "Electronics", 30, 12, 10, "C-01")
        ]
        conn.executemany(
            """
            INSERT INTO inventory (sku, name, category, stock, reserved, reorder_level, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            products,
        )

    order_count = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    if order_count == 0:
        orders = [
            ("#1042", "Customer A", "LAP-001", "Laptop", 10, "CRITICAL", 100, today, "PENDING", 0, 0, "PENDING", "PENDING", "PENDING", None),
            ("#1043", "Customer B", "MOU-001", "Wireless Mouse", 5, "HIGH", 75, today, "PENDING", 0, 0, "PENDING", "PENDING", "PENDING", None),
            ("#1044", "Customer C", "KEY-001", "Keyboard", 3, "NORMAL", 50, tomorrow, "PENDING", 0, 0, "PENDING", "PENDING", "PENDING", None),
            ("#1045", "Customer D", "MON-001", "Monitor", 2, "NORMAL", 40, tomorrow, "PENDING", 0, 0, "PENDING", "PENDING", "PENDING", None),
            ("#1046", "Customer E", "HDP-001", "Headphones", 4, "HIGH", 80, today, "PENDING", 0, 0, "PENDING", "PENDING", "PENDING", None),
        ]
        conn.executemany(
            """
            INSERT INTO orders (
                order_number, customer, sku, product_name, quantity, priority, priority_score,
                due_date, status, allocated_quantity, shortage_quantity,
                picking_status, packing_status, dispatch_status, dispatch_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            orders,
        )

    exception_count = conn.execute('SELECT COUNT(*) FROM exceptions').fetchone()[0]
    if exception_count == 0:
        conn.executemany(
            """
            INSERT INTO exceptions (order_id, product_name, exception_type, severity, status, recommended_resolution)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 'Laptop', 'Stock mismatch', 'CRITICAL', 'OPEN', 'Replenish stock for laptop order before dispatch.'),
                (2, 'Wireless Mouse', 'Damaged item', 'MEDIUM', 'OPEN', 'Replace damaged item and re-check packing.'),
                (3, 'Keyboard', 'Picking issue', 'HIGH', 'OPEN', 'Recount keyboard units at picking station.'),
            ],
        )

    message_count = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
    if message_count == 0:
        conn.executemany(
            """
            INSERT INTO messages (sender, category, message)
            VALUES (?, ?, ?)
            """,
            [
                ('Warehouse Lead', 'URGENT', 'Critical laptop shortage requires replenishment before dispatch.'),
                ('Inventory Team', 'INVENTORY', 'Laptop inventory is below reorder level. Check the replenishment queue.'),
                ('Picking Team', 'PICKING', 'Two orders are ready for picking this afternoon.'),
            ],
        )

    activity_count = conn.execute('SELECT COUNT(*) FROM activities').fetchone()[0]
    if activity_count == 0:
        conn.executemany(
            """
            INSERT INTO activities (activity_type, title, order_id, product_name, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ('Picking', 'Picking started for order #1042', 1, 'Laptop', 'ACTIVE'),
                ('Packing', 'Packing scheduled for keyboard replenishment', 3, 'Keyboard', 'SCHEDULED'),
                ('Dispatch', 'Dispatch window is open for ready shipments', 1, 'Laptop', 'ACTIVE'),
            ],
        )

    conn.commit()
    conn.close()


def get_order_decision(order):
    required_quantity = int(order['quantity']) if order['quantity'] is not None else 0
    stock = int(order['stock']) if order['stock'] is not None else 0
    reserved = int(order['reserved']) if order['reserved'] is not None else 0
    available_stock = max(stock - reserved, 0)
    allocated_quantity = min(required_quantity, available_stock)
    shortage = max(required_quantity - available_stock, 0)

    if shortage == 0:
        action = "Full allocation"
        recommendation = f"Allocate {required_quantity} units immediately."
    else:
        action = "Replenishment required"
        recommendation = f"Allocate {allocated_quantity} units immediately and replenish {shortage} units."

    priority = str(order['priority']).upper()
    reason = "Sufficient stock available for this order."
    if shortage > 0:
        reason = f"Stock shortage: {shortage} units below the required quantity."
    if priority in {'HIGH', 'CRITICAL'}:
        reason += f" Prioritize this order because it is {priority}."

    return {
        'required_quantity': required_quantity,
        'available_stock': available_stock,
        'allocated_quantity': allocated_quantity,
        'shortage': shortage,
        'priority': priority,
        'action': action,
        'recommendation': recommendation,
        'reason': reason,
    }


def get_inventory_status(product):
    available = max(int(product['stock']) - int(product['reserved']), 0)
    if int(product['stock']) == 0:
        return {'label': 'OUT OF STOCK', 'class_name': 'status out'}
    if available <= int(product['reorder_level']):
        return {'label': 'LOW STOCK', 'class_name': 'status low'}
    return {'label': 'IN STOCK', 'class_name': 'status good'}


def sync_order_allocations():
    conn = get_db()
    rows = conn.execute(
        '''
        SELECT o.id, o.quantity, o.priority,
               COALESCE(i.stock, 0) AS stock,
               COALESCE(i.reserved, 0) AS reserved
        FROM orders o
        LEFT JOIN inventory i ON o.sku = i.sku
        '''
    ).fetchall()
    for row in rows:
        available = max(int(row['stock']) - int(row['reserved']), 0)
        required = int(row['quantity'])
        allocated = min(required, available)
        shortage = max(required - available, 0)
        conn.execute(
            'UPDATE orders SET allocated_quantity = ?, shortage_quantity = ? WHERE id = ?',
            (allocated, shortage, row['id']),
        )
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    sync_order_allocations()
    print('Database initialized successfully.')