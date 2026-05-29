-- PostgreSQL Row-Level Security Migration Template
-- Enable multi-tenant data isolation at database level
-- 
-- Usage: Copy relevant sections into your Alembic migration

-- =============================================================================
-- Step 1: Add tenant_id columns to existing tables
-- =============================================================================

-- Add tenant_id column to users table (if not exists)
ALTER TABLE swx_users 
ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- Create index for tenant filtering
CREATE INDEX IF NOT EXISTS ix_swx_users_tenant_id ON swx_users(tenant_id);

-- Add foreign key constraint (optional, requires swx_team table)
-- ALTER TABLE swx_users 
-- ADD CONSTRAINT fk_swx_users_tenant_id 
-- FOREIGN KEY (tenant_id) REFERENCES swx_team(id) ON DELETE SET NULL;

-- =============================================================================
-- Step 2: Enable Row-Level Security
-- =============================================================================

-- Enable RLS on tenant-scoped tables
ALTER TABLE swx_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE swx_users FORCE ROW LEVEL SECURITY;

-- Force RLS applies to table owner as well (critical for security)
-- Without FORCE, superusers bypass RLS

-- =============================================================================
-- Step 3: Create RLS Policies
-- =============================================================================

-- Policy: Users can only see records in their tenant
CREATE POLICY users_tenant_isolation ON swx_users
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- Policy: Super admins can see all records (optional)
CREATE POLICY users_super_admin_bypass ON swx_users
    FOR ALL
    USING (
        current_setting('app.is_super_admin', true)::boolean = true
    );

-- Policy: Allow NULL tenant_id for records that are not tenant-scoped
CREATE POLICY users_null_tenant ON swx_users
    FOR ALL
    USING (tenant_id IS NULL);

-- =============================================================================
-- Step 4: Composite Index for Performance
-- =============================================================================

-- Critical: tenant_id should be leading column in composite indexes
-- This ensures queries filter by tenant first, then by other columns

-- Example: For queries filtering by tenant + created_at
CREATE INDEX IF NOT EXISTS ix_swx_users_tenant_created 
    ON swx_users(tenant_id, created_at DESC);

-- Example: For queries filtering by tenant + email
CREATE INDEX IF NOT EXISTS ix_swx_users_tenant_email 
    ON swx_users(tenant_id, email);

-- =============================================================================
-- Step 5: Session Variable for RLS
-- =============================================================================

-- The application must set session variable on each connection:
-- SET LOCAL app.current_tenant_id = '<tenant-uuid>';
-- SET LOCAL app.is_super_admin = 'true' or 'false';

-- This is done via SQLAlchemy event listener in:
-- swx_core/database/rls.py

-- =============================================================================
-- Rollback Template
-- =============================================================================

/*
-- Drop policies
DROP POLICY IF EXISTS users_tenant_isolation ON swx_users;
DROP POLICY IF EXISTS users_super_admin_bypass ON swx_users;
DROP POLICY IF EXISTS users_null_tenant ON swx_users;

-- Disable RLS
ALTER TABLE swx_users DISABLE ROW LEVEL SECURITY;
ALTER TABLE swx_users NO FORCE ROW LEVEL SECURITY;

-- Drop indexes
DROP INDEX IF EXISTS ix_swx_users_tenant_id;
DROP INDEX IF EXISTS ix_swx_users_tenant_created;
DROP INDEX IF EXISTS ix_swx_users_tenant_email;

-- Drop column (optional - may want to keep for future use)
-- ALTER TABLE swx_users DROP COLUMN IF EXISTS tenant_id;
*/

-- =============================================================================
-- Additional Tables Template
-- =============================================================================

-- Template for enabling RLS on other tables:
/*
-- Enable RLS
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table_name> FORCE ROW LEVEL SECURITY;

-- Tenant isolation policy
CREATE POLICY <table_name>_tenant_isolation ON <table_name>
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- Super admin bypass (optional)
CREATE POLICY <table_name>_super_admin_bypass ON <table_name>
    FOR ALL
    USING (current_setting('app.is_super_admin', true)::boolean = true);

-- Performance indexes
CREATE INDEX IF NOT EXISTS ix_<table_name>_tenant_id ON <table_name>(tenant_id);
CREATE INDEX IF NOT EXISTS ix_<table_name>_tenant_created ON <table_name>(tenant_id, created_at DESC);
*/