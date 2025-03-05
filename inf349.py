from flask import Flask, jsonify, request, redirect
import requests
from models import Product, Order, db
from http import HTTPStatus
import os

app = Flask(__name__)

TAUX_IMPOSITION = {
    'QC': 0.15,
    'ON': 0.13,
    'AB': 0.05,
    'BC': 0.12,
    'NS': 0.14
}

def calculate_shipping(weight):
    if weight <= 500:
        return 5
    elif weight <= 2000:
        return 10
    return 25

# Récupération des produits (GET /)
@app.route('/', methods=['GET'])
def get_products():
    with db:
        products = Product.select()
        return jsonify({
            'products': [
                {
                    'id': p.id,
                    'name': p.name,
                    'description': p.description,
                    'price': p.price,
                    'in_stock': p.in_stock,
                    'weight': p.weight,
                    'image': p.image
                } for p in products
            ]
        })

# Création d'une commande (POST /order)
@app.route('/order', methods=['POST'])
def create_order():
    data = request.get_json()
    if not data or 'product' not in data or 'id' not in data['product'] or 'quantity' not in data['product']:
        return jsonify({
            'errors': {
                'product': {
                    'code': 'missing-fields',
                    'name': 'La création d’une commande nécessite un produit'
                }
            }
        }), HTTPStatus.UNPROCESSABLE_ENTITY

    product_id = data['product']['id']
    quantity = data['product']['quantity']
    
    if quantity < 1:
        return jsonify({
            'errors': {
                'product': {
                    'code': 'missing-fields',
                    'name': 'La quantité doit être supérieure ou égale à 1'
                }
            }
        }), HTTPStatus.UNPROCESSABLE_ENTITY

    with db:
        product = Product.get_or_none(Product.id == product_id)
        if not product or not product.in_stock:
            return jsonify({
                'errors': {
                    'product': {
                        'code': 'out-of-inventory',
                        'name': 'Le produit demandé n’est pas en inventaire'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        order = Order.create(
            product_id=product_id,
            quantity=quantity,
            total_price=product.price * quantity,
            shipping_price=calculate_shipping(product.weight * quantity)
        )
        return redirect(f'/order/{order.id}', code=HTTPStatus.FOUND)

# Récupération d'une commande (GET /order/<int:order_id>)
@app.route('/order/<int:order_id>', methods=['GET'])
def get_order(order_id):
    with db:
        order = Order.get_or_none(Order.id == order_id)
        if not order:
            return '', HTTPStatus.NOT_FOUND
        product = Product.get(Product.id == order.product_id) 
        return jsonify({
            'order': {
                'id': order.id,
                'total_price': order.total_price,
                'total_price_tax': order.total_price_tax,
                'email': order.email,
                'shipping_information': None if not order.shipping_country else {
                    'country': order.shipping_country,
                    'address': order.shipping_address,
                    'postal_code': order.shipping_postal_code,
                    'city': order.shipping_city,
                    'province': order.shipping_province
                },
                'credit_card': None if not order.credit_card_name else {
                    'name': order.credit_card_name,
                    'first_digits': order.credit_card_first_digits,
                    'last_digits': order.credit_card_last_digits,
                    'expiration_year': order.credit_card_expiration_year,
                    'expiration_month': order.credit_card_expiration_month
                },
                'paid': order.paid,
                'transaction': None if not order.transaction_id else {
                    'id': order.transaction_id,
                    'success': order.transaction_success,
                    'amount_charged': order.transaction_amount
                },
                'product': {
                    'id': order.product_id,
                    'quantity': order.quantity
                },
                'shipping_price': order.shipping_price
            }
        })

# Mise à jour des informations de livraison (PUT /order/<int:order_id>)
@app.route('/order/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    with db:
        order = Order.get_or_none(Order.id == order_id)
        if not order:
            return '', HTTPStatus.NOT_FOUND

        data = request.get_json()
        if 'shipping_information' not in data or 'email' not in data:
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'missing-fields',
                        'name': 'Il manque un ou plusieurs champs qui sont obligatoires'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        shipping = data['shipping_information']
        required_fields = ['country', 'address', 'postal_code', 'city', 'province']
        if not all(field in shipping for field in required_fields):
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'missing-fields',
                        'name': 'Il manque un ou plusieurs champs qui sont obligatoires'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        order.email = data['email']
        order.shipping_country = shipping['country']
        order.shipping_address = shipping['address']
        order.shipping_postal_code = shipping['postal_code']
        order.shipping_city = shipping['city']
        order.shipping_province = shipping['province']
        taxe = TAUX_IMPOSITION.get(shipping['province'], 0)
        order.total_price_tax = (order.total_price + order.shipping_price) * (1 + taxe)
        order.save()
        return get_order(order_id)

# Paiement d'une commande (PUT /order/<int:order_id>/pay)
@app.route('/order/<int:order_id>/pay', methods=['PUT'])
def pay_order(order_id):
    with db:
        order = Order.get_or_none(Order.id == order_id)
        if not order:
            return '', HTTPStatus.NOT_FOUND

        data = request.get_json()
        if 'credit_card' not in data:
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'missing-fields',
                        'name': 'Les informations de carte de crédit sont requises pour le paiement'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        if not order.email or not order.shipping_country:
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'missing-fields',
                        'name': 'Les informations du client sont nécessaires avant d’appliquer une carte de crédit'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        if order.paid:
            return jsonify({
                'errors': {
                    'order': {
                        'code': 'already-paid',
                        'name': 'La commande a déjà été payée.'
                    }
                }
            }), HTTPStatus.UNPROCESSABLE_ENTITY

        credit_card = data['credit_card']
        amount = order.total_price_tax
        response = requests.post(
            'http://dimensweb.uqac.ca/~jgnault/shops/pay/',
            json={'credit_card': credit_card, 'amount_charged': amount}
        )

        if response.status_code != 200:
            return jsonify(response.json()), HTTPStatus.UNPROCESSABLE_ENTITY

        payment_data = response.json()
        order.credit_card_name = payment_data['credit_card']['name']
        order.credit_card_first_digits = payment_data['credit_card']['first_digits']
        order.credit_card_last_digits = payment_data['credit_card']['last_digits']
        order.credit_card_expiration_year = payment_data['credit_card']['expiration_year']
        order.credit_card_expiration_month = payment_data['credit_card']['expiration_month']
        order.transaction_id = payment_data['transaction']['id']
        order.transaction_success = payment_data['transaction']['success']
        order.transaction_amount = payment_data['transaction']['amount_charged']
        order.paid = True
        order.save()
        return get_order(order_id)

if __name__ == '__main__':
    if not os.path.exists('data'):
        os.makedirs('data')
    with db:
        db.create_tables([Product, Order], safe=True)
    app.run(debug=True)