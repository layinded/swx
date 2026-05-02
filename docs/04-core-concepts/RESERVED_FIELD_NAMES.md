# Reserved Field Names

SQLModel has internal attributes that conflict with field names in your models. Using these names will cause errors.

## Reserved Names

The following field names **cannot be used** in SQLModel table classes:

| Reserved Name | Reason |
|---------------|--------|
| `metadata` | SQLAlchemy `MetaData` collection - causes `ValueError: <class 'dict'> has no matching SQLAlchemy type` |
| `registry` | SQLModel's `ModelMeta` registry |
| `table` | SQLAlchemy `Table` class reference |
| `id` | Reserved for primary key (mapped to `RowID` internally) |

## Error Example

```python
# ❌ BAD - Will fail
class Product(SQLModel, table=True):
    name: str
    metadata: dict  # ERROR: conflicts with SQLAlchemy metadata attribute
    registry: str   # ERROR: conflicts with SQLModel registry

# ✅ GOOD
class Product(SQLModel, table=True):
    name: str
    meta: dict     # OK - different name
    data: str      # OK - different name
```

## Workarounds

If you need to store metadata or similar data:

```python
# Option 1: Rename field
class Product(SQLModel, table=True):
    name: str
    meta: dict = {}  # Store as 'meta' instead of 'metadata'

# Option 2: Use JSON column
import json
class Product(SQLModel, table=True):
    name: str
    extra_data: str = ""  # Store JSON as string
    
    @property
    def metadata(self) -> dict:
        return json.loads(self.extra_data) if self.extra_data else {}
```

## Best Practice

Avoid these names entirely in table models:
- `metadata`, `registry`, `table`
- Python reserved words: `class`, `def`, `lambda`, etc.
- SQL keywords: `select`, `from`, `where`, etc.