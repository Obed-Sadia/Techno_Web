from peewee import *
import requests

db = SqliteDatabase('data/data.db')

# Création des tables de la base de donnée 
class BaseModel(Model):
    class Meta:
        database = db

class Product(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = TextField()
    price = FloatField()  
    in_stock = BooleanField(default=True)
    weight = IntegerField() 
    image = CharField()

    def serialisation(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'in_stock': self.in_stock,
            'weight': self.weight,
            'image': self.image
        }

class Order(BaseModel):
    id = AutoField()
    total_price = FloatField(null=True)
    total_price_tax = FloatField(null=True)
    shipping_price = FloatField(null=True)
    email = CharField(null=True)
    shipping_country = CharField(null=True)
    shipping_address = CharField(null=True)
    shipping_postal_code = CharField(null=True)
    shipping_city = CharField(null=True)
    shipping_province = CharField(null=True)
    paid = BooleanField(default=False)
    product_id = IntegerField()
    quantity = IntegerField()
    credit_card_name = CharField(null=True)
    credit_card_first_digits = CharField(null=True)
    credit_card_last_digits = CharField(null=True)
    credit_card_expiration_year = IntegerField(null=True)
    credit_card_expiration_month = IntegerField(null=True)
    transaction_id = CharField(null=True)
    transaction_success = BooleanField(null=True)
    transaction_amount = FloatField(null=True)

    def serialisation(self):
        return {
            'id': self.id,
            'total_price': self.total_price,
            'total_price_tax': self.total_price_tax,
            'email': self.email,
            'shipping_information': None if not self.shipping_country else {
                'country': self.shipping_country,
                'address': self.shipping_address,
                'postal_code': self.shipping_postal_code,
                'city': self.shipping_city,
                'province': self.shipping_province
            },
            'credit_card': None if not self.credit_card_name else {
                'name': self.credit_card_name,
                'first_digits': self.credit_card_first_digits,
                'last_digits': self.credit_card_last_digits,
                'expiration_year': self.credit_card_expiration_year,
                'expiration_month': self.credit_card_expiration_month
            },
            'paid': self.paid,
            'transaction': None if not self.transaction_id else {
                'id': self.transaction_id,
                'success': self.transaction_success,
                'amount_charged': self.transaction_amount
            },
            'product': {
                'id': self.product_id,
                'quantity': self.quantity
            },
            'shipping_price': self.shipping_price
        }
    
# Récuperation des données et initialisation de la base de donnée 
def initialisation():
    db.connect()
    db.create_tables([Product, Order], safe=True)
    # Charger les produits au démarrage si la table est vide
    if Product.select().count() == 0:
        response = requests.get('http://dimensweb.uqac.ca/~jgnault/shops/products/')
        if response.status_code == 200:
            products = response.json()['products']
            with db.atomic():
                for p in products:
                    Product.create(
                        id=p['id'],
                        name=p['name'],
                        description=p['description'],
                        price=p['price'],
                        in_stock=p.get('in_stock', True),
                        weight=p['weight'],
                        image=p['image']
                    )
    db.close()