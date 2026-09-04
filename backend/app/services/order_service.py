

def get_order_by_id(order_id: int):
    # Placeholder function to simulate fetching an order from a database
    # In a real application, this would query the database for the order
    mock_orders = {
        1: {"id": 1, "item": "Laptop", "quantity": 1},
        2: {"id": 2, "item": "Smartphone", "quantity": 2},
    }
    return mock_orders.get(order_id)