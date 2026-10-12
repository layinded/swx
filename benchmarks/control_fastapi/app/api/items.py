"""
Control FastAPI Project - API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


# Models
class Item(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None


# In-memory storage
items_db: List[Item] = []
item_id_counter = 1


@router.get("/items", response_model=List[Item])
async def list_items():
    return items_db


@router.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    for item in items_db:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@router.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemCreate):
    global item_id_counter
    new_item = Item(
        id=item_id_counter,
        name=item.name,
        description=item.description,
        price=item.price
    )
    items_db.append(new_item)
    item_id_counter += 1
    return new_item


@router.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item: ItemUpdate):
    for i, existing in enumerate(items_db):
        if existing.id == item_id:
            if item.name is not None:
                existing.name = item.name
            if item.description is not None:
                existing.description = item.description
            if item.price is not None:
                existing.price = item.price
            return existing
    raise HTTPException(status_code=404, detail="Item not found")


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int):
    for i, item in enumerate(items_db):
        if item.id == item_id:
            items_db.pop(i)
            return
    raise HTTPException(status_code=404, detail="Item not found")
