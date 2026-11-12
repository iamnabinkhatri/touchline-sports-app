PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'coach', 'member')),
    club_role TEXT NOT NULL DEFAULT 'Member',
    avatar_tone TEXT NOT NULL DEFAULT 'forest',
    member_since TEXT NOT NULL,
    club_points INTEGER NOT NULL DEFAULT 0,
    email_verified INTEGER NOT NULL DEFAULT 1,
    two_factor_enabled INTEGER NOT NULL DEFAULT 0,
    two_factor_secret TEXT,
    two_factor_pending_secret TEXT,
    two_factor_last_step INTEGER NOT NULL DEFAULT -1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);

CREATE TABLE IF NOT EXISTS google_login_states (
    state_hash TEXT PRIMARY KEY,
    nonce TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    player_invite TEXT,
    community_invite TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS google_login_states_expiry_idx ON google_login_states(expires_at);

CREATE TABLE IF NOT EXISTS user_auth_identities (
    provider TEXT NOT NULL CHECK(provider='google'),
    subject TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(provider, subject),
    UNIQUE(provider, user_id)
);

CREATE TABLE IF NOT EXISTS api_key_requests (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'denied')),
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    claimed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS api_key_requests_one_pending_idx
    ON api_key_requests(user_id) WHERE status='pending';
CREATE INDEX IF NOT EXISTS api_key_requests_status_time_idx
    ON api_key_requests(status, requested_at);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE REFERENCES api_key_requests(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS api_keys_one_active_per_user_idx
    ON api_keys(user_id) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL CHECK (purpose IN ('verify_email', 'password_reset', 'login_2fa')),
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_tokens_user_purpose_idx ON auth_tokens(user_id, purpose);

CREATE TABLE IF NOT EXISTS recovery_codes (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, code_hash)
);

CREATE TABLE IF NOT EXISTS communities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sport TEXT NOT NULL,
    kind TEXT NOT NULL,
    mark TEXT NOT NULL,
    member_count INTEGER NOT NULL DEFAULT 0,
    privacy TEXT NOT NULL,
    accent TEXT NOT NULL,
    description TEXT NOT NULL,
    activity TEXT NOT NULL,
    logo_data TEXT,
    banner_data TEXT,
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_members (
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'Member',
    joined_at TEXT NOT NULL,
    PRIMARY KEY (community_id, user_id)
);

CREATE TABLE IF NOT EXISTS community_settings (
    community_id TEXT PRIMARY KEY REFERENCES communities(id) ON DELETE CASCADE,
    poll_retention_days INTEGER NOT NULL CHECK(poll_retention_days BETWEEN 1 AND 30),
    profile_theme TEXT NOT NULL DEFAULT 'light' CHECK(profile_theme IN ('light','dark')),
    updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_join_requests (
    community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'denied')),
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (community_id, user_id)
);
CREATE INDEX IF NOT EXISTS community_join_requests_pending_idx
    ON community_join_requests(community_id, status, requested_at);

CREATE TABLE IF NOT EXISTS community_invites (
    token_hash TEXT PRIMARY KEY,
    community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS community_invites_expiry_idx ON community_invites(expires_at);

CREATE TABLE IF NOT EXISTS community_deletion_requests (
    id TEXT PRIMARY KEY,
    community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    requested_by TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL CHECK (status IN ('pending_admins', 'pending_super_admin', 'denied')),
    created_at TEXT NOT NULL,
    super_admin_due_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS community_deletion_pending_idx
    ON community_deletion_requests(community_id)
    WHERE status IN ('pending_admins', 'pending_super_admin');

CREATE TABLE IF NOT EXISTS community_deletion_approvals (
    request_id TEXT NOT NULL REFERENCES community_deletion_requests(id) ON DELETE CASCADE,
    admin_user_id TEXT NOT NULL REFERENCES users(id),
    approved_at TEXT,
    PRIMARY KEY (request_id, admin_user_id)
);

CREATE TABLE IF NOT EXISTS community_messages (
    id TEXT PRIMARY KEY,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    edited_at TEXT
);
CREATE INDEX IF NOT EXISTS community_messages_order_idx
    ON community_messages(community_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS community_message_reads (
    community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_rowid INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (community_id, user_id)
);

CREATE INDEX IF NOT EXISTS community_members_user_role_idx
    ON community_members(user_id, role, community_id);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL REFERENCES users(id),
    community_id TEXT NOT NULL REFERENCES communities(id),
    text TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    seed_likes INTEGER NOT NULL DEFAULT 0,
    media_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS posts_created_idx ON posts(created_at DESC);

CREATE TABLE IF NOT EXISTS post_likes (
    post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (post_id, user_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS comments_post_idx ON comments(post_id, created_at);

CREATE TABLE IF NOT EXISTS polls (
    id TEXT PRIMARY KEY,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    category TEXT NOT NULL,
    author_id TEXT NOT NULL REFERENCES users(id),
    closes_at TEXT NOT NULL,
    game_at TEXT,
    location TEXT NOT NULL DEFAULT '',
    feedback_due_at TEXT,
    feedback_completed_at TEXT,
    result_json TEXT,
    featured INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS poll_options (
    id TEXT PRIMARY KEY,
    poll_id TEXT NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    seed_votes INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS poll_options_poll_idx ON poll_options(poll_id, position);

CREATE TABLE IF NOT EXISTS poll_votes (
    poll_id TEXT NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    option_id TEXT NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
    player_id TEXT REFERENCES players(id) ON DELETE SET NULL,
    guest_count INTEGER NOT NULL DEFAULT 0 CHECK(guest_count BETWEEN 0 AND 2),
    created_at TEXT NOT NULL,
    PRIMARY KEY (poll_id, user_id)
);

CREATE TABLE IF NOT EXISTS poll_feedback_deliveries (
    poll_id TEXT NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sent_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    PRIMARY KEY(poll_id,user_id)
);

CREATE TABLE IF NOT EXISTS poll_player_ratings (
    poll_id TEXT NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 10),
    feedback TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(poll_id,player_id,user_id)
);

CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    community_id TEXT REFERENCES communities(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    age_group TEXT NOT NULL,
    league TEXT NOT NULL,
    mark TEXT NOT NULL,
    accent TEXT NOT NULL,
    coach TEXT NOT NULL,
    rank TEXT NOT NULL,
    record_w INTEGER NOT NULL DEFAULT 0,
    record_d INTEGER NOT NULL DEFAULT 0,
    record_l INTEGER NOT NULL DEFAULT 0,
    form_json TEXT NOT NULL DEFAULT '[]',
    formation TEXT NOT NULL,
    lineup_saved_at TEXT,
    starting_xi_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    number INTEGER NOT NULL,
    pos TEXT NOT NULL,
    group_name TEXT NOT NULL,
    foot TEXT NOT NULL,
    status TEXT NOT NULL,
    rating_sum REAL NOT NULL DEFAULT 0,
    rating_count INTEGER NOT NULL DEFAULT 0,
    goals INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    apps INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    date_of_birth TEXT,
    height_cm INTEGER,
    bio TEXT NOT NULL DEFAULT '',
    starts INTEGER NOT NULL DEFAULT 0,
    minutes INTEGER NOT NULL DEFAULT 0,
    yellow_cards INTEGER NOT NULL DEFAULT 0,
    red_cards INTEGER NOT NULL DEFAULT 0,
    clean_sheets INTEGER NOT NULL DEFAULT 0,
    saves INTEGER NOT NULL DEFAULT 0,
    image_data TEXT,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (team_id, number)
);
CREATE INDEX IF NOT EXISTS players_team_idx ON players(team_id, sort_order);
CREATE TABLE IF NOT EXISTS player_invites (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL COLLATE NOCASE,
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    invited_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    player_data_json TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS player_invites_email_team_idx ON player_invites(email,team_id);

CREATE TABLE IF NOT EXISTS player_match_appearances (
    poll_id TEXT NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    played_at TEXT NOT NULL,
    minutes INTEGER NOT NULL DEFAULT 90,
    started INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(poll_id,player_id)
);

CREATE TABLE IF NOT EXISTS player_ratings (
    player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    value REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (player_id, user_id)
);

CREATE TABLE IF NOT EXISTS matchday_rating_requests (
    id TEXT PRIMARY KEY,
    community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
    fixture_id TEXT NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
    requested_by TEXT NOT NULL REFERENCES users(id),
    requested_at TEXT NOT NULL,
    UNIQUE(community_id, fixture_id)
);

CREATE TABLE IF NOT EXISTS matchday_player_ratings (
    request_id TEXT NOT NULL REFERENCES matchday_rating_requests(id) ON DELETE CASCADE,
    player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 10),
    feedback TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY(request_id, player_id, user_id)
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    opponent TEXT NOT NULL,
    opponent_mark TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL,
    venue TEXT NOT NULL,
    competition TEXT NOT NULL,
    formation TEXT NOT NULL,
    status TEXT NOT NULL,
    objective TEXT NOT NULL,
    summary TEXT NOT NULL,
    content_json TEXT NOT NULL,
    checklist_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    icon TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    time_label TEXT NOT NULL,
    unread INTEGER NOT NULL DEFAULT 1,
    route TEXT NOT NULL,
    created_at TEXT NOT NULL,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    post_id TEXT REFERENCES posts(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT '',
    source_key TEXT
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    accent TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fixtures (
    id TEXT PRIMARY KEY,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    opponent TEXT NOT NULL,
    opponent_mark TEXT NOT NULL,
    home_away TEXT NOT NULL,
    date TEXT NOT NULL,
    venue TEXT NOT NULL,
    competition TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS duties (
    id TEXT PRIMARY KEY,
    community_id TEXT REFERENCES communities(id) ON DELETE CASCADE,
    team_id TEXT REFERENCES teams(id) ON DELETE CASCADE,
    event_key TEXT,
    assigned_to TEXT REFERENCES users(id) ON DELETE SET NULL,
    items_json TEXT NOT NULL DEFAULT '[]',
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    claimed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    claimed_at TEXT,
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_duties_starts ON duties(starts_at);
CREATE INDEX IF NOT EXISTS idx_duties_claimed ON duties(claimed_by);
