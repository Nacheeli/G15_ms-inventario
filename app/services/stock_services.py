from app import cache, redis_client  
from app.models import Stock    
from app.repositories import StockRepository
from contextlib import contextmanager
import time

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
               
                if redis_client.get(lock_key) == lock_value:
                    redis_client.delete(lock_key)
        else:
            raise Exception(f"El recurso está bloqueado para el stock {stock_id}.")

    def all(self) -> list[Stock]:
        cached_stocks = cache.get('stocks')
        if cached_stocks is None:
            stocks = self.repository.get_all()
            if stocks:
                cache.set('stocks', stocks, timeout=self.CACHE_TIMEOUT)
            return stocks
        return cached_stocks

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