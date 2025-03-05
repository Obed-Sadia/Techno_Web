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

    
# Récuperation des données et initialisation de la base de donnée 
def initialisation():
    db.connect()
    db.create_tables([Product, Order], safe=True)
    
    # Chargement des produits 
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