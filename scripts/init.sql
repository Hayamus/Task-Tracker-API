-- 1. Пользователи
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    bio TEXT,
    is_admin BOOLEAN DEFAULT FALSE
);

-- 2. Команды
CREATE TABLE IF NOT EXISTS teams (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    members_count INTEGER DEFAULT 0 NOT NULL,
    CONSTRAINT teams_members_count_check CHECK (members_count >= 0),
    CONSTRAINT teams_name_check CHECK (length(TRIM(BOTH FROM name)) > 0)
);

-- 3. Функция и триггер для авто-подсчёта участников команды
CREATE OR REPLACE FUNCTION update_team_members_count() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE teams 
        SET members_count = members_count + 1 
        WHERE id = NEW.team_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE teams 
        SET members_count = members_count - 1 
        WHERE id = OLD.team_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$;

-- 4. Участники команд
CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member' NOT NULL,
    CONSTRAINT team_members_team_id_user_id_key UNIQUE (team_id, user_id)
);

CREATE TRIGGER trg_team_members_count
AFTER INSERT OR DELETE ON team_members
FOR EACH ROW
EXECUTE FUNCTION update_team_members_count();

CREATE INDEX IF NOT EXISTS idx_team_members_team_id ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user_id ON team_members(user_id);

-- 5. Задачи
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    title TEXT NOT NULL UNIQUE,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    version INTEGER DEFAULT 1,
    deadline TIMESTAMP WITH TIME ZONE,
    is_personal BOOLEAN DEFAULT TRUE,
    CONSTRAINT chk_task_type CHECK (
        ((is_personal = true) AND (team_id IS NULL)) OR 
        ((is_personal = false) AND (team_id IS NOT NULL))
    ),
    CONSTRAINT tasks_title_check CHECK (length(TRIM(BOTH FROM title)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id);
CREATE INDEX IF NOT EXISTS idx_tasks_team_id ON tasks(team_id);

-- 6. Сессии и Refresh-токены
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- 7. Вложения (Attachments)
CREATE TABLE IF NOT EXISTS attachments (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    owner_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    size BIGINT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    storage_key VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attachments_task_id ON attachments(task_id);

-- 8. Фоновые задачи аналитики
CREATE TABLE IF NOT EXISTS analytics_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    scope VARCHAR(50) DEFAULT 'user' NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    params JSONB DEFAULT '{}'::jsonb NOT NULL,
    result JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_jobs_user_scope ON analytics_jobs(user_id, scope, created_at DESC);

-- 9. Журнал аудита действий
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(50),
    target_id INTEGER,
    target_name VARCHAR(255),
    changes JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);