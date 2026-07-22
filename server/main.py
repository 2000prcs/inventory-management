from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders

app = FastAPI(title="Factory Inventory Management System")

# Restocking orders submitted from the Restocking tab. In-memory only, like every
# other dataset here - cleared on server restart.
submitted_restock_orders = []

# Tasks created from the profile menu's Tasks modal. In-memory only.
user_tasks = []

# The client merges these with per-user mock tasks that use small integer ids,
# so API-created tasks start at 1000 to keep the merged list's ids unique.
TASK_ID_BASE = 1000

def next_task_id() -> int:
    """Return the next unused task id."""
    if not user_tasks:
        return TASK_ID_BASE
    return max(task["id"] for task in user_tasks) + 1

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str
    # Optional so forecast records predating the Restocking feature still validate
    unit_cost: Optional[float] = None
    lead_time_days: Optional[int] = None

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

class RestockOrderItem(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_cost: float
    lead_time_days: int

class RestockOrder(BaseModel):
    id: str
    order_number: str
    items: List[RestockOrderItem]
    budget: float
    total_value: float
    status: str
    submitted_date: str
    lead_time_days: int
    expected_delivery: str

class CreateRestockOrderRequest(BaseModel):
    budget: float
    items: List[RestockOrderItem]

class Task(BaseModel):
    id: int
    title: str
    priority: str
    # camelCase matches the shape the client already uses for its mock tasks,
    # which are merged with these in a single list
    dueDate: str
    status: str

class CreateTaskRequest(BaseModel):
    title: str
    priority: str = "medium"
    dueDate: str

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.post("/api/purchase-orders", response_model=PurchaseOrder)
def create_purchase_order(request: CreatePurchaseOrderRequest):
    """Raise a purchase order against a backlog item to cover its shortage"""
    backlog_item = next((item for item in backlog_items if item["id"] == request.backlog_item_id), None)
    if not backlog_item:
        raise HTTPException(
            status_code=404,
            detail=f"Backlog item {request.backlog_item_id} not found"
        )

    if any(po["backlog_item_id"] == request.backlog_item_id for po in purchase_orders):
        raise HTTPException(
            status_code=400,
            detail=f"Backlog item {request.backlog_item_id} already has a purchase order"
        )

    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

    purchase_order = {
        "id": str(len(purchase_orders) + 1),
        "backlog_item_id": request.backlog_item_id,
        "supplier_name": request.supplier_name,
        "quantity": request.quantity,
        "unit_cost": request.unit_cost,
        "expected_delivery_date": request.expected_delivery_date,
        "status": "Pending",
        "created_date": datetime.now().isoformat(timespec="seconds"),
        "notes": request.notes
    }

    purchase_orders.append(purchase_order)
    return purchase_order

@app.get("/api/purchase-orders/{backlog_item_id}", response_model=PurchaseOrder)
def get_purchase_order_by_backlog_item(backlog_item_id: str):
    """Get the purchase order raised against a given backlog item"""
    purchase_order = next(
        (po for po in purchase_orders if po["backlog_item_id"] == backlog_item_id),
        None
    )
    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail=f"No purchase order found for backlog item {backlog_item_id}"
        )
    return purchase_order

@app.get("/api/tasks", response_model=List[Task])
def get_tasks():
    """Get user tasks, newest first"""
    return list(reversed(user_tasks))

@app.post("/api/tasks", response_model=Task)
def create_task(request: CreateTaskRequest):
    """Create a user task"""
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")

    task = {
        # Mock tasks in the client use small integer ids, so API ids start well
        # above them to avoid collisions in the merged list App.vue renders.
        "id": next_task_id(),
        "title": request.title.strip(),
        "priority": request.priority,
        "dueDate": request.dueDate,
        "status": "pending"
    }

    user_tasks.append(task)
    return task

@app.patch("/api/tasks/{task_id}", response_model=Task)
def toggle_task(task_id: int):
    """Toggle a task between pending and completed"""
    task = next((t for t in user_tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    task["status"] = "pending" if task["status"] == "completed" else "completed"
    return task

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    """Delete a task"""
    task = next((t for t in user_tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    user_tasks.remove(task)
    return {"success": True, "id": task_id}

@app.get("/api/restock-orders", response_model=List[RestockOrder])
def get_restock_orders():
    """Get restocking orders submitted from the Restocking tab, newest first"""
    return list(reversed(submitted_restock_orders))

@app.post("/api/restock-orders", response_model=RestockOrder)
def create_restock_order(request: CreateRestockOrderRequest):
    """Submit a restocking order built from demand forecast recommendations"""
    if not request.items:
        raise HTTPException(status_code=400, detail="A restock order must contain at least one item")

    submitted_at = datetime.now()

    # Totals are recomputed server-side rather than trusted from the client
    total_value = sum(item.quantity * item.unit_cost for item in request.items)

    # The order is only complete once its slowest item arrives, so the order-level
    # lead time is the max across items rather than a sum or average
    order_lead_time = max(item.lead_time_days for item in request.items)

    order = {
        "id": str(len(submitted_restock_orders) + 1),
        "order_number": f"RST-2025-{len(submitted_restock_orders) + 1:04d}",
        "items": [item.model_dump() for item in request.items],
        "budget": request.budget,
        "total_value": round(total_value, 2),
        "status": "Submitted",
        "submitted_date": submitted_at.isoformat(timespec="seconds"),
        "lead_time_days": order_lead_time,
        "expected_delivery": (submitted_at + timedelta(days=order_lead_time)).isoformat(timespec="seconds")
    }

    submitted_restock_orders.append(order)
    return order

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    # Headline KPIs, derived from the filtered order set so they track the
    # global filter bar rather than being fixed figures.
    delivered = [order for order in filtered_orders if order["status"] == "Delivered"]
    orders_fulfilled = len(delivered)

    # Fill rate counts anything that shipped or landed as fulfilled demand;
    # only Backordered represents demand we could not meet from stock.
    unfilled = len([o for o in filtered_orders if o["status"] == "Backordered"])
    fill_rate = round(
        ((len(filtered_orders) - unfilled) / len(filtered_orders)) * 100, 1
    ) if filtered_orders else 0.0

    # Days between placing an order and it being delivered, averaged over
    # delivered orders that carry both timestamps.
    processing_times = []
    for order in delivered:
        placed, arrived = order.get("order_date"), order.get("actual_delivery")
        if placed and arrived:
            try:
                days = (datetime.fromisoformat(arrived) - datetime.fromisoformat(placed)).days
            except ValueError:
                continue
            if days >= 0:
                processing_times.append(days)
    avg_processing_days = round(sum(processing_times) / len(processing_times), 1) if processing_times else 0.0

    # Turnover = revenue shipped against the value of stock held to support it.
    total_orders_value = sum(order["total_value"] for order in filtered_orders)
    inventory_turnover = round(total_orders_value / total_inventory_value, 1) if total_inventory_value else 0.0

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": total_orders_value,
        "orders_fulfilled": orders_fulfilled,
        "total_orders": len(filtered_orders),
        "fill_rate": fill_rate,
        "avg_processing_days": avg_processing_days,
        "inventory_turnover": inventory_turnover
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get quarterly performance reports with optional filtering"""
    # Calculate quarterly statistics from orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    quarters = {}

    for order in filtered_orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get month-over-month trends with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    months = {}

    for order in filtered_orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
