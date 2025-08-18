-- Driftor Enterprise Database Initialization
-- Security-first PostgreSQL setup with row-level security

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For similarity search
CREATE EXTENSION IF NOT EXISTS "vector" WITH SCHEMA extensions;  -- For vector search (if available)

-- Create application user with limited privileges
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'driftor_app') THEN
        CREATE ROLE driftor_app WITH LOGIN PASSWORD 'driftor_app_password';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT CONNECT ON DATABASE driftor TO driftor_app;
GRANT USAGE ON SCHEMA public TO driftor_app;
GRANT CREATE ON SCHEMA public TO driftor_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO driftor_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO driftor_app;

-- Enable row-level security globally
ALTER DATABASE driftor SET row_security = on;

-- Create function to get current tenant ID from session
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS text AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function() RETURNS trigger AS $$
DECLARE
    old_values jsonb;
    new_values jsonb;
    tenant_id_val text;
BEGIN
    -- Get tenant ID
    tenant_id_val := current_tenant_id();
    
    -- Handle different operations
    IF TG_OP = 'DELETE' THEN
        old_values := to_jsonb(OLD);
        INSERT INTO audit_logs (
            event_type,
            tenant_id,
            resource_type,
            resource_id,
            action,
            details,
            timestamp,
            hash_digest
        ) VALUES (
            'data.deleted',
            tenant_id_val,
            TG_TABLE_NAME,
            (OLD.id)::text,
            'DELETE',
            jsonb_build_object('old_values', old_values),
            NOW(),
            encode(sha256(concat(NOW()::text, 'DELETE', tenant_id_val, (OLD.id)::text)::bytea), 'hex')
        );
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        old_values := to_jsonb(OLD);
        new_values := to_jsonb(NEW);
        INSERT INTO audit_logs (
            event_type,
            tenant_id,
            resource_type,
            resource_id,
            action,
            details,
            timestamp,
            hash_digest
        ) VALUES (
            'data.updated',
            tenant_id_val,
            TG_TABLE_NAME,
            (NEW.id)::text,
            'UPDATE',
            jsonb_build_object('old_values', old_values, 'new_values', new_values),
            NOW(),
            encode(sha256(concat(NOW()::text, 'UPDATE', tenant_id_val, (NEW.id)::text)::bytea), 'hex')
        );
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        new_values := to_jsonb(NEW);
        INSERT INTO audit_logs (
            event_type,
            tenant_id,
            resource_type,
            resource_id,
            action,
            details,
            timestamp,
            hash_digest
        ) VALUES (
            'data.created',
            tenant_id_val,
            TG_TABLE_NAME,
            (NEW.id)::text,
            'INSERT',
            jsonb_build_object('new_values', new_values),
            NOW(),
            encode(sha256(concat(NOW()::text, 'INSERT', tenant_id_val, (NEW.id)::text)::bytea), 'hex')
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_timestamp ON audit_logs(tenant_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_compliance ON audit_logs(compliance_relevant, timestamp DESC);

-- Create GIN indexes for JSONB search
CREATE INDEX IF NOT EXISTS idx_audit_logs_details_gin ON audit_logs USING gin(details);

-- Create function for tenant data cleanup
CREATE OR REPLACE FUNCTION cleanup_tenant_data(target_tenant_id text) RETURNS void AS $$
DECLARE
    table_name text;
    sql_statement text;
BEGIN
    -- List of tables with tenant_id column
    FOR table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename != 'audit_logs'  -- Special handling for audit logs
    LOOP
        -- Check if table has tenant_id column
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = table_name AND column_name = 'tenant_id'
        ) THEN
            sql_statement := format('DELETE FROM %I WHERE tenant_id = %L', table_name, target_tenant_id);
            EXECUTE sql_statement;
            RAISE NOTICE 'Cleaned up table: %', table_name;
        END IF;
    END LOOP;
    
    -- Handle audit logs separately (anonymize instead of delete for compliance)
    UPDATE audit_logs 
    SET details = jsonb_build_object('anonymized', true, 'original_tenant', tenant_id)
    WHERE tenant_id = target_tenant_id;
    
    RAISE NOTICE 'Tenant data cleanup completed for: %', target_tenant_id;
END;
$$ LANGUAGE plpgsql;

-- Create function for data retention enforcement
CREATE OR REPLACE FUNCTION enforce_data_retention() RETURNS void AS $$
DECLARE
    cutoff_date timestamp;
BEGIN
    -- Delete old audit logs (except for compliance-relevant ones)
    cutoff_date := NOW() - INTERVAL '90 days';
    
    DELETE FROM audit_logs 
    WHERE created_at < cutoff_date 
    AND compliance_relevant = false;
    
    -- Anonymize old audit logs that must be retained
    cutoff_date := NOW() - INTERVAL '2555 days';  -- 7 years
    
    UPDATE audit_logs 
    SET details = jsonb_build_object('anonymized', true, 'retention_applied', NOW())
    WHERE created_at < cutoff_date
    AND compliance_relevant = true
    AND NOT (details ? 'anonymized');
    
    RAISE NOTICE 'Data retention policies applied';
END;
$$ LANGUAGE plpgsql;

-- Create scheduled job for data retention (requires pg_cron extension)
-- SELECT cron.schedule('data-retention', '0 2 * * *', 'SELECT enforce_data_retention();');

-- Create function to verify audit log integrity
CREATE OR REPLACE FUNCTION verify_audit_integrity(check_tenant_id text DEFAULT NULL) RETURNS TABLE(
    log_id uuid,
    expected_hash text,
    actual_hash text,
    is_valid boolean
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        al.id,
        encode(sha256(concat(al.timestamp::text, al.action, al.tenant_id, al.resource_id)::bytea), 'hex') as expected_hash,
        al.hash_digest as actual_hash,
        encode(sha256(concat(al.timestamp::text, al.action, al.tenant_id, al.resource_id)::bytea), 'hex') = al.hash_digest as is_valid
    FROM audit_logs al
    WHERE (check_tenant_id IS NULL OR al.tenant_id = check_tenant_id)
    ORDER BY al.timestamp DESC;
END;
$$ LANGUAGE plpgsql;

-- Create materialized view for audit log summaries (for performance)
CREATE MATERIALIZED VIEW IF NOT EXISTS audit_summary AS
SELECT 
    tenant_id,
    event_type,
    DATE(timestamp) as event_date,
    COUNT(*) as event_count,
    COUNT(CASE WHEN severity = 'HIGH' THEN 1 END) as high_severity_count,
    COUNT(CASE WHEN severity = 'CRITICAL' THEN 1 END) as critical_severity_count
FROM audit_logs
GROUP BY tenant_id, event_type, DATE(timestamp);

-- Create unique index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_summary_unique 
ON audit_summary(tenant_id, event_type, event_date);

-- Refresh materialized view function
CREATE OR REPLACE FUNCTION refresh_audit_summary() RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY audit_summary;
END;
$$ LANGUAGE plpgsql;

-- Performance optimization: Create partial indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tenants_active ON tenants(id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_tenant_users_active ON tenant_users(tenant_id, id) WHERE is_active = true AND is_deleted = false;

-- Security: Create function to sanitize sensitive data in logs
CREATE OR REPLACE FUNCTION sanitize_log_data(input_jsonb jsonb) RETURNS jsonb AS $$
DECLARE
    result jsonb;
    sensitive_keys text[] := ARRAY['password', 'token', 'secret', 'key', 'credential'];
    key text;
BEGIN
    result := input_jsonb;
    
    FOREACH key IN ARRAY sensitive_keys
    LOOP
        IF result ? key THEN
            result := result || jsonb_build_object(key, '[REDACTED]');
        END IF;
    END LOOP;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions to application user
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO driftor_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO driftor_app;
GRANT SELECT ON audit_summary TO driftor_app;

-- Set default permissions for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO driftor_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO driftor_app;

-- Final security check: Ensure RLS is enabled
DO $$
DECLARE
    table_name text;
BEGIN
    FOR table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename IN ('tenants', 'tenant_users', 'tenant_roles', 'tenant_user_roles', 'audit_logs')
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        RAISE NOTICE 'Enabled RLS for table: %', table_name;
    END LOOP;
END $$;