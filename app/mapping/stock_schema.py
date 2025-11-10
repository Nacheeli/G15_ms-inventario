from marshmallow import fields, Schema, post_load, validate
from app.models import Stock

class StockSchema(Schema):
    id = fields.Integer(dump_only=True)  # Solo se devuelve, no se requiere para crear
    producto_id = fields.Integer(required=True)  
    fecha_transaccion = fields.DateTime(required=True) 
    cantidad = fields.Float(required=True)  
    entrada_salida = fields.Integer(
        required=True, validate=validate.OneOf([1, 2]) 
    )

    @post_load
    def make_stock(self, data, **kwargs):

        return Stock(**data)
