# Migration Guide: v2.17.0 → v2.18.0

## System Config Value Type: FLOAT + Wrapped-Scalar Unwrapping

This release extends `SettingValueType` with `FLOAT` and alias values (`INTEGER`, `BOOLEAN`), and updates `SettingsService._convert_value()` to unwrap single-key dict values for scalar types.

---

### Migration Required: PostgreSQL Enum Extension

The `settingvaluetype` PostgreSQL enum now includes three new values: `float`, `integer`, `boolean`. Existing databases must be migrated:

```sql
ALTER TYPE settingvaluetype ADD VALUE IF NOT EXISTS 'float';
ALTER TYPE settingvaluetype ADD VALUE IF NOT EXISTS 'integer';
ALTER TYPE settingvaluetype ADD VALUE IF NOT EXISTS 'boolean';
```

#### Alembic Migration Template

Copy `swx_core/database/migrations/v2_18_0_add_setting_value_type_float.py` to your project's `migrations/versions/` directory, set `down_revision` to your current head, and run:

```bash
alembic upgrade head
```

The migration uses `autocommit_block()` because `ALTER TYPE ... ADD VALUE` cannot run inside a transaction in PostgreSQL < 12. `IF NOT EXISTS` (PG 12+) makes it idempotent.

---

### New Enum Values

```python
class SettingValueType(str, Enum):
    INT = "int"
    INTEGER = "integer"    # alias for INT
    BOOL = "bool"
    BOOLEAN = "boolean"    # alias for BOOL
    STRING = "string"
    JSON = "json"
    FLOAT = "float"        # NEW
```

`INTEGER` and `BOOLEAN` are semantic aliases — `_convert_value()` and `validate_setting_value()` treat them identically to `INT` and `BOOL`.

---

### New Method: `get_float()`

```python
service = get_settings_service(session)
threshold = await service.get_float("detection.confidence_threshold", default=0.7)
```

---

### Wrapped-Scalar Unwrapping

`_convert_value()` now unwraps single-key dict values before converting scalar types (`INT`, `INTEGER`, `BOOL`, `BOOLEAN`, `STRING`, `FLOAT`). This supports the FastPII convention of wrapping scalars in JSON objects:

```python
# Stored value: {"threshold": 0.7}, value_type: FLOAT
# Before:  float({"threshold": 0.7})  → TypeError → 0.0
# After:   _unwrap_scalar({"threshold": 0.7}) → 0.7 → float(0.7) → 0.7
```

Only single-key dicts are unwrapped. Multi-key dicts and bare scalars are unaffected — fully backward compatible.

---

### Verification Steps

After upgrading to v2.18.0:

1. **Run migration**: `alembic upgrade head`
2. **Insert a float config**:
   ```sql
   INSERT INTO swx_system_config (key, value, value_type, category, is_active)
   VALUES ('test.float', '0.75'::jsonb, 'float', 'general', true);
   ```
3. **Read it back**:
   ```python
   value = await service.get_float("test.float", default=0.0)
   assert value == 0.75
   ```
4. **Test wrapped-scalar unwrapping**:
   ```python
   # Store: {"max_length": 50000} with value_type "integer"
   value = await service.get_int("test.wrapped_int", default=0)
   assert value == 50000
   ```

### Backward Compatibility

- All existing `INT`, `BOOL`, `STRING`, `JSON` configs work unchanged.
- Bare scalar values are not affected by the unwrapping logic.
- The `downgrade()` is a no-op — PostgreSQL cannot remove individual enum values. The new values are additive and harmless if unused.
