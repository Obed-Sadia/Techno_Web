import pytest
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
from inf349 import app, db, Product, Order


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DB_PATH = os.path.join(BASE_DIR, 'data', 'test_data.db')

@pytest.fixture
def client():
    os.makedirs(os.path.dirname(TEST_DB_PATH), exist_ok=True)
    db.init(TEST_DB_PATH)
    with db:
        db.drop_tables([Product, Order])
        db.create_tables([Product, Order], safe=True)
        if Product.select().count() == 0:
            Product.create(
                id=1,
                name="Brown eggs",
                description="Raw organic brown eggs in a basket",
                price=28.1,
                in_stock=True,
                weight=400,
                image="0.jpg"
            )
            Product.create(
                id=2,
                name="Sweet fresh strawberry",
                description="Sweet fresh strawberry on the wooden table",
                price=29.45,
                in_stock=False,
                weight=299,
                image="1.jpg"
            )
    with app.test_client() as client:
        yield client

def test_get_products(client):
    response = client.get('/')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'products' in data
    assert len(data['products']) >= 2
    assert data['products'][0]['id'] == 1
    assert data['products'][0]['name'] == "Brown eggs"
    assert data['products'][0]['in_stock'] is True

def test_create_order_valid(client):
    response = client.post('/order', 
        data=json.dumps({'product': {'id': 1, 'quantity': 2}}),
        content_type='application/json'
    )
    assert response.status_code == 302
    assert '/order/' in response.headers['Location']

def test_create_order_out_of_stock(client):
    response = client.post('/order', 
        data=json.dumps({'product': {'id': 2, 'quantity': 1}}),
        content_type='application/json'
    )
    assert response.status_code == 422
    data = json.loads(response.data)
    assert 'errors' in data
    assert data['errors']['product']['code'] == 'out-of-inventory'

def test_create_order_missing_fields(client):
    response = client.post('/order', 
        data=json.dumps({'product': {'id': 1}}),
        content_type='application/json'
    )
    assert response.status_code == 422
    data = json.loads(response.data)
    assert 'errors' in data
    assert data['errors']['product']['code'] == 'missing-fields'

def test_get_order(client):
    with db:
        order = Order.create(product_id=1, quantity=1, total_price=28.1, shipping_price=5)
        order_id = order.id
    response = client.get(f'/order/{order_id}')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'order' in data
    assert data['order']['id'] == order_id

def test_update_order_shipping(client):
    with db:
        order = Order.create(product_id=1, quantity=1, total_price=28.1, shipping_price=5)
        order_id = order.id
    response = client.put(f'/order/{order_id}',
        data=json.dumps({
            'email': 'test@example.com',
            'shipping_information': {
                'country': 'Canada',
                'address': '123 Rue Test',
                'postal_code': 'H0H0H0',
                'city': 'Testville',
                'province': 'QC'
            }
        }),
        content_type='application/json'
    )
    assert response.status_code == 200

def test_update_order_payment(client, mocker):
    with db:
        order = Order.create(
            product_id=1, quantity=1, total_price=28.1, shipping_price=5,
            email='test@example.com', shipping_country='Canada',
            shipping_address='123 Rue Test', shipping_postal_code='H0H0H0',
            shipping_city='Testville', shipping_province='QC',
            total_price_tax=(28.1 + 5) * 1.15
        )
        order_id = order.id
    mock_response = mocker.patch('requests.post')
    mock_response.return_value.status_code = 200
    mock_response.return_value.json.return_value = {
        'credit_card': {'name': 'John Doe', 'first_digits': '4242', 'last_digits': '4242', 'expiration_year': 2025, 'expiration_month': 12},
        'transaction': {'id': 'test-transaction-123', 'success': True, 'amount_charged': (28.1 + 5) * 1.15}
    }
    response = client.put(f'/order/{order_id}/pay',
        data=json.dumps({
            'credit_card': {'name': 'John Doe', 'number': '4242424242424242', 'expiration_year': 2025, 'cvv': '123', 'expiration_month': 12}
        }),
        content_type='application/json'
    )
    assert response.status_code == 200