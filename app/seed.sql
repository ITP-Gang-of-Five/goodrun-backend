-- Development seed data. Run after schema.sql. Safe to re-run.

TRUNCATE users, volunteer_preferences, locations, runs,
         orders, order_events, order_images, volunteer_locations
RESTART IDENTITY CASCADE;

INSERT INTO users (email, name, password_hash, role, created_at) VALUES
    ('admin',                  'Admin',                    'admin',        'ADMIN',        '2026-09-01T09:00:00Z'),
    ('tara@example.com',       'Tara Nguyen',              'volunteer',    'VOLUNTEER',    '2026-09-01T09:00:00Z'),
    ('stores@rmh.example.com', 'Royal Melbourne Hospital', 'organisation', 'ORGANISATION', '2026-09-01T09:00:00Z');

-- only the volunteer gets a preferences row
INSERT INTO volunteer_preferences (volunteer_id, car_size) VALUES
    (2, 'MEDIUM');

INSERT INTO locations (name, latitude, longitude) VALUES
    ('Royal Melbourne Hospital',    -37.798670, 144.955970),
    ('Pantry Warehouse, Brunswick', -37.767000, 144.960000);

-- Tara is part way through a run
INSERT INTO runs (volunteer_id, status, created_at, started_at) VALUES
    (2, 'IN_PROGRESS', '2026-09-20T08:54:19Z', '2026-09-20T08:54:19Z');

-- order 1 is on that run, order 2 is still in the available pool (run_id null)
INSERT INTO orders (
    run_id, from_organisation_id, to_organisation_id,
    from_location_id, to_location_id, created_by_id,
    description, size, urgency, status,
    pickup_notes, dropoff_notes, due_at, sequence, created_at
) VALUES
    (1, 3, NULL, 1, 2, 1,
     '2 sealed boxes, surgical consumables', 'MEDIUM', 'MEDIUM', 'IN_TRANSIT',
     'Loading dock B, ask for stores', 'Roller door, ask for Priya',
     '2026-09-20T13:54:19Z', 1, '2026-09-20T07:54:19Z'),
    (NULL, 3, NULL, 1, 2, 1,
     'Sterile gloves, assorted sizes', 'SMALL', 'HIGH', 'READY_FOR_PICKUP',
     'Loading dock B, ask for stores', 'Roller door, ask for Priya',
     '2026-09-21T12:54:19Z', NULL, '2026-09-21T02:54:19Z');

INSERT INTO order_events (order_id, new_status, created_at) VALUES
    (1, 'READY_FOR_PICKUP', '2026-09-20T07:54:19Z'),
    (1, 'IN_TRANSIT',       '2026-09-20T08:54:19Z'),
    (2, 'READY_FOR_PICKUP', '2026-09-21T02:54:19Z');

INSERT INTO volunteer_locations (volunteer_id, latitude, longitude, updated_at) VALUES
    (2, -37.795000, 144.958000, '2026-09-20T09:10:00Z');
