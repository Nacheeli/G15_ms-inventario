from app import cache, redis_client  
from app.models import Stock    
from app.repositories import StockRepository
from app.services import StockService
from contextlib import contextmanager
import time
import random

class StockService:

    CACHE_TIMEOUT = 60 
    REDIS_LOCK_TIMEOUT = 10 

    def __init__(self, repository=None):
        self.repository = repository or StockRepository()

    @contextmanager
    def redis_lock(self, stock_id: int):
        lock_key = f"stock_lock_{stock_id}"
        lock_value = str(time.time())

        if redis_client.set(lock_key, lock_value, ex=self.REDIS_LOCK_TIMEOUT, nx=True):
            try:
                yield
            finally:
               
                current = redis_client.get(lock_key)
                if current is not None and isinstance(current, bytes):
                    current = current.decode()
                if current == lock_value:
                    redis_client.delete(lock_key)
        else:
            raise Exception(f"El recurso está bloqueado para el stock {stock_id}.")


    def find(self, stock_id: int) -> Stock:
        cached_stock = cache.get(f'stock_{stock_id}')
        if cached_stock is None:
            stock = self.repository.get_by_id(stock_id)
            if stock:
                cache.set(f'stock_{stock_id}', stock, timeout=self.CACHE_TIMEOUT)
            return stock
        return cached_stock

    def add(self, stock: Stock) -> Stock:
        new_stock = self.repository.add(stock)
        cache.set(f'stock_{new_stock.id}', new_stock, timeout=self.CACHE_TIMEOUT)
        cache.delete('stocks')
        return new_stock

    def update(self, stock_id: int, updated_stock: Stock) -> Stock:
        with self.redis_lock(stock_id):
            existing_stock = self.find(stock_id)
            if not existing_stock:
                raise Exception(f"Stock con ID {stock_id} no encontrado.")

            existing_stock.nombre = updated_stock.nombre
            existing_stock.cantidad = updated_stock.cantidad
            existing_stock.precio = updated_stock.precio
            
            saved_stock = self.repository.save(existing_stock)
            
            cache.set(f'stock_{stock_id}', saved_stock, timeout=self.CACHE_TIMEOUT)
            cache.delete('stocks') 
            return saved_stock


    def delete(self, stock_id: int) -> bool:
        with self.redis_lock(stock_id):
            deleted = self.repository.delete(stock_id)
            if deleted:
                cache.delete(f'stock_{stock_id}')
                cache.delete('stocks')
            return deleted

    def find(self, stock_id: int) -> Stock:
        cached_stock = cache.get(f'stock_{stock_id}')
        if cached_stock is None:
            stock = self.repository.get_by_id(stock_id)
            if stock:
                cache.set(f'stock_{stock_id}', stock, timeout=self.CACHE_TIMEOUT)
            return stock
        return cached_stock

    def manage_stock(self, stock_id: int, cantidad: int) -> Stock:
        with self.redis_lock(stock_id):
            stock = self.find(stock_id)
            if not stock:
                raise Exception(f"Stock con ID {stock_id} no encontrado.")
            
            nuevo_stock = stock.cantidad + cantidad
            if nuevo_stock < 0:
                raise Exception(f"No hay suficiente stock para egresar {abs(cantidad)} unidades.")
            
            stock.cantidad = nuevo_stock
            updated_stock = self.repository.save(stock)

            cache.set(f'stock_{stock_id}', updated_stock, timeout=self.CACHE_TIMEOUT)
            cache.delete('stocks')

            return updated_stock
        
    def reservar_stock(self, data):
        producto_id = int(data.get('producto_id'))
        cantidad = int(data.get('cantidad', 1))

        if random.random() < 0.3:
            print(f"Fallo aleatorio provocado para producto {producto_id}")
            return {"Error": "Fallo de stock simulado"}, 409

        try:
            with self.redis_lock(producto_id):
                stock = self.find(producto_id)
                if not stock:
                    return {"error": "Producto no encontrado"}, 404

                if stock.cantidad < cantidad:
                    return {"error": "Stock insuficiente"}, 409

                stock.cantidad -= cantidad
                updated_stock = self.repository.save(stock)
                
                cache.set(f'stock_{producto_id}', updated_stock, timeout=self.CACHE_TIMEOUT)
                cache.delete('stocks')
                
                return {"mensaje": "Stock reservado", "stock_restante": stock.cantidad}, 200
        except Exception as e:
            return {"error": str(e)}, 500
    
    def compensar_stock(self, data):
        producto_id = int(data.get('producto_id'))
        cantidad = int(data.get('cantidad', 1))

        try:
            with self.redis_lock(producto_id):
                stock = self.find(producto_id)
                if not stock:
                   
                    return {"error": "Producto no encontrado para compensar"}, 404
                
                stock.cantidad += cantidad
                updated_stock = self.repository.save(stock)
                
                cache.set(f'stock_{producto_id}', updated_stock, timeout=self.CACHE_TIMEOUT)
                cache.delete('stocks')
                
                print(f"[Compensación] Stock devuelto para {producto_id}")
                return {"mensaje": "Compensación exitosa"}, 200
        except Exception as e:
            return {"error": str(e)}, 500

stock_service = StockService()

@app.route('/stocks/reservar', methods=['POST'])
def reservar():
    data = request.get_json()
    result, status_code = stock_service.reservar_stock(data)
    return jsonify(result), status_code

@app.route('/stocks/compensar', methods=['POST'])
def compensar():
    data = request.get_json()
    result, status_code = stock_service.compensar_stock(data)
    return jsonify(result), status_code