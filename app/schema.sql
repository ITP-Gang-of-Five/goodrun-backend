-- Good Run database schema (Sprint 2). Mirrors the Data Model diagram.

DROP TABLE IF EXISTS
    run_steps, order_images, order_events, orders, runs, invites,
    volunteer_locations, volunteer_preferences, locations, users
CASCADE;


-- Every account: admins, volunteers and organisations. An organisation's account
-- name is its organisation name. There is no sign up, admins create accounts.
-- An invited account starts with just an email. The person sets their own name and
-- password the first time they log in, which is when onboarded_at gets set.
CREATE TABLE users (
    user_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         VARCHAR(255) NOT NULL,
    name          VARCHAR(255) NULL,
    password_hash VARCHAR(255) NULL,
    role          TEXT NOT NULL CHECK (role IN ('ADMIN', 'VOLUNTEER', 'ORGANISATION')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    onboarded_at  TIMESTAMPTZ NULL,
    -- once set up, an account always has a name and a password
    CHECK (onboarded_at IS NULL OR (name IS NOT NULL AND password_hash IS NOT NULL))
);

-- emails are unique across all roles and compared ignoring case, so the index is on
-- lower(email). Enforcing it here means two simultaneous signups cannot both win.
CREATE UNIQUE INDEX users_email_key ON users (lower(email));


-- The one time password emailed to someone who has been invited, where there exists at most one per account.
-- The code itself also only works once so its deleted when used. We store a hash of the code btw, just like passwrods
CREATE TABLE invites (
    user_id         BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    code_hash       VARCHAR(255) NOT NULL,
    failed_attempts INT NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Volunteer only settings, at most one row per volunteer (1 : 0..1 with users).
-- car_size decides which orders a volunteer is offered.
CREATE TABLE volunteer_preferences (
    volunteer_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    car_size     TEXT NOT NULL CHECK (car_size IN ('SMALL', 'MEDIUM', 'LARGE'))
);


-- A named point on the map. Locations exist independently of organisations.
CREATE TABLE locations (
    location_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    latitude    DECIMAL(9, 6) NOT NULL,
    longitude   DECIMAL(9, 6) NOT NULL
);


-- A volunteer's trip through a set of orders. Creating a run is starting it, so
-- there is no unassigned run and volunteer_id is never null.
CREATE TABLE runs (
    run_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    volunteer_id BIGINT NOT NULL REFERENCES users(user_id),
    status       TEXT NOT NULL CHECK (status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL
);

-- a volunteer can only be on one run at a time. The API will check this first
CREATE UNIQUE INDEX runs_one_in_progress ON runs (volunteer_id) WHERE status = 'IN_PROGRESS';


-- A single delivery. run_id is null while the order sits in the available pool.
-- from/to organisation are both optional, an order has 0, 1 or 2 attached.
CREATE TABLE orders (
    order_id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id               BIGINT NULL REFERENCES runs(run_id),
    from_organisation_id BIGINT NULL REFERENCES users(user_id),
    to_organisation_id   BIGINT NULL REFERENCES users(user_id),
    from_location_id     BIGINT NOT NULL REFERENCES locations(location_id),
    to_location_id       BIGINT NOT NULL REFERENCES locations(location_id),
    created_by_id        BIGINT NOT NULL REFERENCES users(user_id),
    description          VARCHAR(1000) NOT NULL,
    size                 TEXT NOT NULL CHECK (size IN ('SMALL', 'MEDIUM', 'LARGE')),
    urgency              TEXT NOT NULL CHECK (urgency IN ('LOW', 'MEDIUM', 'HIGH')),
    status               TEXT NOT NULL CHECK (status IN ('PENDING', 'READY_FOR_PICKUP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
    pickup_notes         TEXT NULL,
    dropoff_notes        TEXT NULL,
    due_at               TIMESTAMPTZ NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- the agreement's INVALID_ORDER case, you cannot deliver somewhere to itself
    CONSTRAINT orders_distinct_endpoints CHECK (from_location_id <> to_location_id)
);

CREATE INDEX orders_run_idx ON orders (run_id);


-- The route of a run. Every order on a run gets one PICKUP and one DROPOFF step in the order
-- the volunteer planned them to be in on the app
CREATE TABLE run_steps (
    run_id       BIGINT NOT NULL REFERENCES runs(run_id),
    order_id     BIGINT NOT NULL REFERENCES orders(order_id),
    type         TEXT NOT NULL CHECK (type IN ('PICKUP', 'DROPOFF')),
    position     INT NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    PRIMARY KEY (run_id, position),
    -- each order is picked up once and dropped off once per run
    CONSTRAINT run_steps_one_of_each UNIQUE (run_id, order_id, type)
);

-- orders/available reads exactly this slice, so index only that slice
CREATE INDEX orders_available_idx ON orders (urgency, created_at)
    WHERE run_id IS NULL AND status = 'READY_FOR_PICKUP';


-- One row per order status change, this is the delivery timeline the frontend shows.
CREATE TABLE order_events (
    event_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES orders(order_id),
    new_status TEXT NOT NULL CHECK (new_status IN ('PENDING', 'READY_FOR_PICKUP', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX order_events_order_idx ON order_events (order_id, created_at);


-- Delivery photos, stored as raw bytes rather than base64. The upload endpoint
-- decodes once on the way in so the download endpoint serves them straight out.
CREATE TABLE order_images (
    image_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id     BIGINT NOT NULL REFERENCES orders(order_id),
    content_type VARCHAR(64) NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png')),
    image_data   BYTEA NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX order_images_order_idx ON order_images (order_id);


-- Latest known position of each volunteer, overwritten on every location ping.
-- One row per volunteer, which is what makes POST location/ an upsert.
CREATE TABLE volunteer_locations (
    volunteer_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    latitude     DECIMAL(9, 6) NOT NULL,
    longitude    DECIMAL(9, 6) NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL
);
