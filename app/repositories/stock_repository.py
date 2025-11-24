from typing import List

from app import db
from app.models import Stock

from .repository import Repository_delete, Repository_get, Repository_add


class StockRepository(Repository_add, Repository_get, Repository_delete):
    def add(self, entity: Stock) -> Stock:
        try:
            db.session.add(entity)  
            db.session.commit()  
            return entity
        except Exception as e:
            db.session.rollback()
            raise e

    def get_all(self) -> List[Stock]:
        return Stock.query.all()

    def get_by_id(self, id: int) -> Stock:
        return Stock.query.get(id)

    def delete(self, id: int) -> bool:
        try:
            Stock = self.get_by_id(id)
            if Stock:
                db.session.delete(Stock)  
                db.session.commit()  
                return True
            return False
        except Exception as e:
            db.session.rollback()
            raise e
