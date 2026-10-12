"""
PostgreSQL Row-Level Security Integration
-----------------------------------------
Sets PostgreSQL session variables for RLS-based tenant isolation.
"""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine

from swx_core.core.tenant import get_current_tenant_id, is_super_admin


def setup_rls_event_listeners(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def set_tenant_rls_context(dbapi_conn, connection_record):
        tenant_id = get_current_tenant_id()
        super_admin = is_super_admin()
        
        cursor = dbapi_conn.cursor()
        
        if tenant_id:
            cursor.execute(
                text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'")
            )
        
        cursor.execute(
            text(f"SET LOCAL app.is_super_admin = '{str(super_admin).lower()}'")
        )
        
        cursor.close()


def setup_rls_for_session(connection, tenant_id: str = None, is_super_admin: bool = False) -> None:
    if tenant_id:
        connection.execute(
            text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'")
        )
    
    connection.execute(
        text(f"SET LOCAL app.is_super_admin = '{str(is_super_admin).lower()}'")
    )