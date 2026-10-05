CREATE TABLE IF NOT EXISTS listings (
    id uuid PRIMARY KEY,
    origin varchar(120) NOT NULL CHECK (origin ~ '[^[:space:]]'),
    destination varchar(120) NOT NULL CHECK (destination ~ '[^[:space:]]'),
    cargo_description varchar(2000) NOT NULL CHECK (cargo_description ~ '[^[:space:]]'),
    equipment_type text NOT NULL CHECK (equipment_type IN ('dry_van', 'refrigerated', 'flatbed')),
    status text NOT NULL CHECK (status IN ('available', 'booked', 'delivered')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    search_vector tsvector GENERATED ALWAYS AS
        (to_tsvector('english'::regconfig, cargo_description)) STORED
);
CREATE INDEX IF NOT EXISTS listings_search_idx ON listings USING GIN (search_vector);
