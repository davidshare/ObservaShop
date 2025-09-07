-- Create the monitoring user if it doesn't exist
DO $$
DECLARE
    monitor_user TEXT := current_setting('custom.postgres_monitor_user', true);
    monitor_pass TEXT := current_setting('custom.postgres_monitor_password', true);
BEGIN
    -- Safety check: skip if settings not provided
    IF monitor_user IS NULL OR monitor_pass IS NULL THEN
        RAISE WARNING 'custom.postgres_monitor_user or custom.postgres_monitor_password not set, skipping user creation';
        RETURN;
    END IF;

    -- Create user if not exists
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = monitor_user) THEN
        EXECUTE format('CREATE USER %I WITH PASSWORD %L', monitor_user, monitor_pass);
        RAISE NOTICE 'Created monitoring user: %', monitor_user;
    ELSE
        RAISE NOTICE 'Monitoring user % already exists', monitor_user;
    END IF;
END $$;

-- Dynamically GRANT CONNECT on the current database
DO $$
DECLARE
    current_db TEXT := current_database();
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO postgres_monitor', current_db);
    RAISE NOTICE 'Granted CONNECT on database % to postgres_monitor', current_db;
END $$;

-- Grant pg_monitor role (PostgreSQL 10+) or fallback to individual grants
DO $$
DECLARE
    monitor_user TEXT := current_setting('custom.postgres_monitor_user', true);
BEGIN
    IF monitor_user IS NULL THEN
        RETURN;
    END IF;

    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'pg_monitor') THEN
        EXECUTE format('GRANT pg_monitor TO %I', monitor_user);
        RAISE NOTICE 'Granted pg_monitor to %', monitor_user;
    ELSE
        -- Fallback for older versions
        EXECUTE format('GRANT SELECT ON pg_stat_database TO %I', monitor_user);
        EXECUTE format('GRANT SELECT ON pg_stat_bgwriter TO %I', monitor_user);
        EXECUTE format('GRANT SELECT ON pg_stat_user_tables TO %I', monitor_user);
        EXECUTE format('GRANT SELECT ON pg_stat_user_indexes TO %I', monitor_user);
        EXECUTE format('GRANT SELECT ON pg_statio_user_tables TO %I', monitor_user);
        RAISE NOTICE 'Granted monitoring permissions to % (fallback)', monitor_user;
    END IF;
END $$;