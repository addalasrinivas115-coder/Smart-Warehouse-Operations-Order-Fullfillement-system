from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for

from database import get_db, get_inventory_status, get_order_decision, init_db, sync_order_allocations

app = Flask(__name__)
app.config['SECRET_KEY'] = 'warehouse-hackathon-secret'

init_db()
sync_order_allocations()


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_metric_summary():
    conn = get_db()
    total_products = conn.execute('SELECT COUNT(*) FROM inventory').fetchone()[0]
    total_orders = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    pending_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status IN ('PENDING', 'PICKING', 'PACKING', 'READY FOR DISPATCH')").fetchone()[0]
    critical_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE priority = 'CRITICAL'").fetchone()[0]
    low_stock_products = conn.execute("SELECT COUNT(*) FROM inventory WHERE stock > 0 AND (stock - reserved) <= reorder_level").fetchone()[0]
    out_of_stock_products = conn.execute('SELECT COUNT(*) FROM inventory WHERE stock = 0').fetchone()[0]
    ready_dispatch = conn.execute("SELECT COUNT(*) FROM orders WHERE dispatch_status = 'READY FOR DISPATCH'").fetchone()[0]

    completed_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'COMPLETED' OR dispatch_status = 'DISPATCHED'").fetchone()[0]
    fulfillment_rate = 0
    if total_orders:
        fulfillment_rate = round((completed_orders / total_orders) * 100, 1)

    conn.close()
    return {
        'total_products': total_products,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'critical_orders': critical_orders,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'ready_dispatch': ready_dispatch,
        'fulfillment_rate': fulfillment_rate,
    }


def build_order_rows(conn, query=''):
    sql = """
        SELECT o.*, i.stock, i.reserved,
               COALESCE(i.stock, 0) - COALESCE(i.reserved, 0) AS available_stock
        FROM orders o
        LEFT JOIN inventory i ON o.sku = i.sku
    """
    params = []
    if query:
        sql += " WHERE o.order_number LIKE ? OR o.customer LIKE ? OR o.product_name LIKE ? OR o.sku LIKE ?"
        q = f'%{query}%'
        params.extend([q, q, q, q])
    sql += " ORDER BY o.priority_score DESC, o.id DESC"
    return conn.execute(sql, params).fetchall()


@app.route('/')
@app.route('/dashboard')
def dashboard():
    metrics = get_metric_summary()
    conn = get_db()
    recent_orders = conn.execute("""
        SELECT o.*, i.stock, i.reserved,
               COALESCE(i.stock, 0) - COALESCE(i.reserved, 0) AS available_stock
        FROM orders o
        LEFT JOIN inventory i ON o.sku = i.sku
        ORDER BY o.id DESC
        LIMIT 5
    """).fetchall()
    low_stock_products = conn.execute("""
        SELECT *, stock - reserved AS available
        FROM inventory
        WHERE stock > 0 AND (stock - reserved) <= reorder_level
        ORDER BY name
    """).fetchall()
    open_exceptions = conn.execute("""
        SELECT *
        FROM exceptions
        WHERE status != 'RESOLVED'
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()
    recent_activities = conn.execute("""
        SELECT *
        FROM activities
        ORDER BY id DESC
        LIMIT 6
    """).fetchall()
    conn.close()
    return render_template(
        'dashboard.html',
        metrics=metrics,
        recent_orders=recent_orders,
        low_stock_products=low_stock_products,
        open_exceptions=open_exceptions,
        recent_activities=recent_activities,
    )


@app.route('/inventory', methods=['GET'])
def inventory():
    query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ALL').upper()
    conn = get_db()
    sql = '''
        SELECT *
        FROM inventory
        WHERE 1 = 1
    '''
    params = []
    if query:
        sql += ' AND (name LIKE ? OR sku LIKE ? OR category LIKE ? OR location LIKE ?)'
        like = f'%{query}%'
        params.extend([like, like, like, like])
    if status_filter != 'ALL':
        if status_filter == 'OUT OF STOCK':
            sql += ' AND stock = 0'
        elif status_filter == 'LOW STOCK':
            sql += ' AND stock > 0 AND (stock - reserved) <= reorder_level'
        elif status_filter == 'IN STOCK':
            sql += ' AND stock > 0 AND (stock - reserved) > reorder_level'
    sql += ' ORDER BY name'
    products = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template('inventory.html', products=products, query=query, status_filter=status_filter)


@app.route('/inventory/add', methods=['POST'])
def add_product():
    name = request.form.get('name', '').strip()
    sku = request.form.get('sku', '').strip().upper()
    category = request.form.get('category', '').strip()
    stock = parse_int(request.form.get('stock'), 0)
    reserved = parse_int(request.form.get('reserved'), 0)
    reorder_level = parse_int(request.form.get('reorder_level'), 0)
    location = request.form.get('location', '').strip().upper()

    if not name or not sku or not category or not location:
        return redirect(url_for('inventory', error='Product name, SKU, category, and location are required.'))
    if stock < 0 or reserved < 0 or reorder_level < 0 or reserved > stock:
        return redirect(url_for('inventory', error='Invalid inventory values. Stock and reserved must be non-negative and reserved cannot exceed stock.'))

    conn = get_db()
    conn.execute(
        '''
        INSERT INTO inventory (sku, name, category, stock, reserved, reorder_level, location)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (sku, name, category, stock, reserved, reorder_level, location),
    )
    conn.commit()
    conn.close()
    sync_order_allocations()
    return redirect(url_for('inventory'))


@app.route('/inventory/update/<int:product_id>', methods=['POST'])
def update_product(product_id):
    stock = parse_int(request.form.get('stock'), 0)
    reserved = parse_int(request.form.get('reserved'), 0)
    reorder_level = parse_int(request.form.get('reorder_level'), 0)

    if stock < 0 or reserved < 0 or reorder_level < 0 or reserved > stock:
        return redirect(url_for('inventory', error='Invalid value: stock and reserved must be non-negative, and reserved cannot exceed stock.'))

    conn = get_db()
    conn.execute(
        '''
        UPDATE inventory
        SET stock = ?, reserved = ?, reorder_level = ?
        WHERE id = ?
        ''',
        (stock, reserved, reorder_level, product_id),
    )
    conn.commit()
    conn.close()
    sync_order_allocations()
    return redirect(url_for('inventory'))


@app.route('/inventory/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    conn = get_db()
    conn.execute('DELETE FROM inventory WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    sync_order_allocations()
    return redirect(url_for('inventory'))


@app.route('/orders', methods=['GET'])
def orders():
    query = request.args.get('q', '').strip()
    status = request.args.get('status', 'ALL').upper()
    conn = get_db()
    sql = '''
        SELECT o.*, i.stock, i.reserved,
               COALESCE(i.stock, 0) - COALESCE(i.reserved, 0) AS available_stock
        FROM orders o
        LEFT JOIN inventory i ON o.sku = i.sku
        WHERE 1 = 1
    '''
    params = []
    if query:
        sql += ' AND (o.order_number LIKE ? OR o.customer LIKE ? OR o.product_name LIKE ? OR o.sku LIKE ?)' 
        like = f'%{query}%'
        params.extend([like, like, like, like])
    if status != 'ALL':
        sql += ' AND o.status = ?'
        params.append(status)
    sql += ' ORDER BY o.priority_score DESC, o.id DESC'
    order_rows = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template('orders.html', orders=order_rows, query=query, status_filter=status)


@app.route('/decisions')
def decisions():
    conn = get_db()
    order_rows = build_order_rows(conn)
    conn.close()
    decisions_data = []
    for order in order_rows:
        order_decision = get_order_decision(order)
        decision_row = dict(order)
        decision_row.update(order_decision)
        decisions_data.append(decision_row)
    return render_template('decisions.html', orders=decisions_data)


@app.route('/decision/<int:order_id>')
def decision(order_id):
    conn = get_db()
    order = conn.execute(
        '''
        SELECT o.*, i.stock, i.reserved,
               COALESCE(i.stock, 0) - COALESCE(i.reserved, 0) AS available_stock
        FROM orders o
        LEFT JOIN inventory i ON o.sku = i.sku
        WHERE o.id = ?
        ''',
        (order_id,),
    ).fetchone()
    conn.close()
    if order is None:
        return 'Order not found', 404
    order_data = dict(order)
    order_data.update(get_order_decision(order))
    return render_template('decision_result.html', order=order_data)


@app.route('/picking', methods=['GET'])
def picking():
    conn = get_db()
    order_rows = conn.execute(
        '''
        SELECT o.*, i.location,
               COALESCE(i.stock, 0) - COALESCE(i.reserved, 0) AS available_stock
        FROM orders o
        LEFT JOIN inventory i ON o.sku = i.sku
        ORDER BY o.priority_score DESC, o.id DESC
        '''
    ).fetchall()
    conn.close()
    return render_template('picking.html', orders=order_rows)


@app.route('/picking/update/<int:order_id>', methods=['POST'])
def update_picking(order_id):
    status = request.form.get('status', 'PENDING').upper()
    valid_statuses = {'PENDING', 'PICKING', 'PICKED'}
    if status not in valid_statuses:
        return redirect(url_for('picking'))
    conn = get_db()
    conn.execute('UPDATE orders SET picking_status = ?, status = ? WHERE id = ?', (status, status, order_id))
    conn.commit()
    conn.close()
    sync_order_allocations()
    return redirect(url_for('picking'))


@app.route('/packing', methods=['GET'])
def packing():
    conn = get_db()
    rows = conn.execute(
        '''
        SELECT o.id, o.order_number, o.product_name, o.quantity, o.packing_status, i.location
        FROM orders o
        LEFT JOIN inventory i ON o.sku = i.sku
        ORDER BY o.id DESC
        '''
    ).fetchall()
    conn.close()
    return render_template('packing.html', orders=rows)


@app.route('/packing/update/<int:order_id>', methods=['POST'])
def update_packing(order_id):
    status = request.form.get('status', 'PENDING').upper()
    valid_statuses = {'PENDING', 'PACKING', 'PACKED'}
    if status not in valid_statuses:
        return redirect(url_for('packing'))
    conn = get_db()
    conn.execute('UPDATE orders SET packing_status = ?, status = ? WHERE id = ?', (status, status, order_id))
    conn.commit()
    conn.close()
    sync_order_allocations()
    return redirect(url_for('packing'))


@app.route('/exceptions', methods=['GET'])
def exceptions():
    conn = get_db()
    rows = conn.execute(
        '''
        SELECT e.*, o.order_number, o.customer, o.product_name AS order_product
        FROM exceptions e
        LEFT JOIN orders o ON e.order_id = o.id
        ORDER BY e.id DESC
        '''
    ).fetchall()
    conn.close()
    return render_template('exceptions.html', exceptions=rows)


@app.route('/exceptions/add', methods=['POST'])
def add_exception():
    order_id = parse_int(request.form.get('order_id'), 0)
    product_name = request.form.get('product_name', '').strip()
    exception_type = request.form.get('exception_type', '').strip()
    severity = request.form.get('severity', 'MEDIUM').upper()
    recommended_resolution = request.form.get('recommended_resolution', '').strip()

    if not exception_type:
        return redirect(url_for('exceptions'))

    conn = get_db()
    conn.execute(
        '''
        INSERT INTO exceptions (order_id, product_name, exception_type, severity, recommended_resolution)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (order_id or None, product_name or None, exception_type, severity, recommended_resolution),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('exceptions'))


@app.route('/exceptions/resolve/<int:exception_id>', methods=['POST'])
def resolve_exception(exception_id):
    conn = get_db()
    conn.execute("UPDATE exceptions SET status = 'RESOLVED' WHERE id = ?", (exception_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('exceptions'))


@app.route('/dispatch', methods=['GET'])
def dispatch():
    conn = get_db()
    rows = conn.execute(
        '''
        SELECT o.id, o.order_number, o.customer, o.product_name, o.quantity, o.dispatch_status, o.dispatch_time
        FROM orders o
        ORDER BY o.id DESC
        '''
    ).fetchall()
    conn.close()
    return render_template('dispatch.html', orders=rows)


@app.route('/dispatch/update/<int:order_id>', methods=['POST'])
def update_dispatch(order_id):
    status = request.form.get('status', 'PENDING').upper()
    valid_statuses = {'PENDING', 'READY FOR DISPATCH', 'DISPATCHED'}
    if status not in valid_statuses:
        return redirect(url_for('dispatch'))
    dispatch_time = None
    if status == 'DISPATCHED':
        dispatch_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute(
        'UPDATE orders SET dispatch_status = ?, dispatch_time = ?, status = ? WHERE id = ?',
        (status, dispatch_time, status, order_id),
    )
    conn.commit()
    conn.close()
    sync_order_allocations()
    return redirect(url_for('dispatch'))


@app.route('/calendar')
def calendar():
    conn = get_db()
    rows = conn.execute(
        '''
        SELECT activity_type AS type, title, order_id, product_name, status, created_at AS time
        FROM activities
        ORDER BY id DESC
        '''
    ).fetchall()
    conn.close()
    return render_template('calendar.html', activities=rows)


@app.route('/alerts')
def alerts():
    conn = get_db()
    low_stock = conn.execute("SELECT * FROM inventory WHERE stock > 0 AND (stock - reserved) <= reorder_level ORDER BY name").fetchall()
    out_of_stock = conn.execute('SELECT * FROM inventory WHERE stock = 0 ORDER BY name').fetchall()
    critical_orders = conn.execute("SELECT * FROM orders WHERE priority = 'CRITICAL' ORDER BY priority_score DESC").fetchall()
    shortage_orders = conn.execute("SELECT o.*, i.stock, i.reserved, (COALESCE(i.stock, 0) - COALESCE(i.reserved, 0)) AS available_stock FROM orders o LEFT JOIN inventory i ON o.sku = i.sku WHERE o.quantity > (COALESCE(i.stock, 0) - COALESCE(i.reserved, 0)) ORDER BY o.priority_score DESC").fetchall()
    delayed_orders = conn.execute("SELECT * FROM orders WHERE status IN ('PENDING', 'PICKING', 'PACKING') AND due_date < date('now') ORDER BY due_date").fetchall()
    conn.close()
    return render_template(
        'alerts.html',
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        critical_orders=critical_orders,
        shortage_orders=shortage_orders,
        delayed_orders=delayed_orders,
    )


@app.route('/analytics')
def analytics():
    metrics = get_metric_summary()
    conn = get_db()
    status_counts = conn.execute("SELECT status, COUNT(*) AS total FROM orders GROUP BY status ORDER BY total DESC").fetchall()
    inventory_status_counts = conn.execute("SELECT CASE WHEN stock = 0 THEN 'OUT OF STOCK' WHEN (stock - reserved) <= reorder_level THEN 'LOW STOCK' ELSE 'IN STOCK' END AS label, COUNT(*) AS total FROM inventory GROUP BY label ORDER BY total DESC").fetchall()
    conn.close()
    return render_template('analytics.html', metrics=metrics, status_counts=status_counts, inventory_status_counts=inventory_status_counts)


@app.route('/chat', methods=['GET'])
def chat():
    conn = get_db()
    messages = conn.execute('SELECT * FROM messages ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('chat.html', messages=messages)


@app.route('/chat/add', methods=['POST'])
def add_chat_message():
    sender = request.form.get('sender', 'Operator').strip() or 'Operator'
    category = request.form.get('category', 'GENERAL').upper()
    message = request.form.get('message', '').strip()
    if not message:
        return redirect(url_for('chat'))
    conn = get_db()
    conn.execute('INSERT INTO messages (sender, category, message) VALUES (?, ?, ?)', (sender, category, message))
    conn.commit()
    conn.close()
    return redirect(url_for('chat'))


@app.route('/settings')
def settings():
    metrics = get_metric_summary()
    return render_template('settings.html', metrics=metrics)


@app.route('/smart-alerts')
def smart_alerts_alias():
    return redirect(url_for('alerts'))


@app.route('/warehouse-chat')
def warehouse_chat_alias():
    return redirect(url_for('chat'))


@app.errorhandler(404)
def not_found(_error):
    return 'Page not found', 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)