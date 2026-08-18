from flask import Flask, render_template
from database import init_db, get_db

app = Flask(__name__)

# Initialize database
init_db()


# -------------------------
# DASHBOARD
# -------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# -------------------------
# INVENTORY
# -------------------------
@app.route("/inventory")
def inventory():
    conn = get_db()

    products = conn.execute("""
        SELECT *
        FROM inventory
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "inventory.html",
        products=products
    )


# -------------------------
# ORDERS
# -------------------------
@app.route("/orders")
def orders():
    conn = get_db()

    orders = conn.execute("""
        SELECT
            o.*,
            COALESCE(i.stock, 0) AS stock,
            COALESCE(i.reserved, 0) AS reserved,
            COALESCE(i.stock, 0) - COALESCE(i.reserved, 0)
                AS available_stock
        FROM orders o
        LEFT JOIN inventory i
            ON o.sku = i.sku
        ORDER BY o.priority_score DESC
    """).fetchall()

    conn.close()

    return render_template(
        "orders.html",
        orders=orders
    )


# -------------------------
# SMART DECISIONS
# -------------------------
@app.route("/decisions")
def decisions():
    conn = get_db()

    orders = conn.execute("""
        SELECT
            o.*,
            COALESCE(i.stock, 0) AS stock,
            COALESCE(i.reserved, 0) AS reserved,
            COALESCE(i.stock, 0) - COALESCE(i.reserved, 0)
                AS available_stock
        FROM orders o
        LEFT JOIN inventory i
            ON o.sku = i.sku
        ORDER BY o.priority_score DESC
    """).fetchall()

    conn.close()

    return render_template(
        "decisions.html",
        orders=orders
    )


# -------------------------
# ANALYZE ONE ORDER
# -------------------------
@app.route("/decision/<int:order_id>")
def decision(order_id):
    conn = get_db()

    order = conn.execute("""
        SELECT
            o.*,
            COALESCE(i.stock, 0) AS stock,
            COALESCE(i.reserved, 0) AS reserved,
            COALESCE(i.stock, 0) - COALESCE(i.reserved, 0)
                AS available_stock
        FROM orders o
        LEFT JOIN inventory i
            ON o.sku = i.sku
        WHERE o.id = ?
    """, (order_id,)).fetchone()

    conn.close()

    if order is None:
        return "Order not found", 404

    return render_template(
        "decision_result.html",
        order=order
    )


# -------------------------
# PICKING
# -------------------------
@app.route("/picking")
def picking():
    return render_template("picking.html")


# -------------------------
# EXCEPTIONS
# -------------------------
@app.route("/exceptions")
def exceptions():
    return render_template("exceptions.html")


# -------------------------
# DISPATCH
# -------------------------
@app.route("/dispatch")
def dispatch():
    return render_template("dispatch.html")


# -------------------------
# ANALYTICS
# -------------------------
@app.route("/analytics")
def analytics():
    return render_template("analytics.html")


# -------------------------
# START APPLICATION
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)