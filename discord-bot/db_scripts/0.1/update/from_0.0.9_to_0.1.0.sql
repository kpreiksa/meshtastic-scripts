-- Migration from version 0.0.9 to 0.1.0
-- Add connection_state table to track mesh connection status

CREATE TABLE IF NOT EXISTS connection_state (
    id SERIAL PRIMARY KEY,
    state VARCHAR(20) NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add initial state
INSERT INTO connection_state (state, details)
VALUES ('DISCONNECTED', 'Initial state');

-- Add last_reconnect field to mesh_nodes table
ALTER TABLE mesh_nodes
ADD COLUMN IF NOT EXISTS last_reconnect TIMESTAMP;

-- Add reconnect_count field to mesh_nodes table
ALTER TABLE mesh_nodes
ADD COLUMN IF NOT EXISTS reconnect_count INTEGER DEFAULT 0;

-- Create index on reconnect fields
CREATE INDEX IF NOT EXISTS idx_mesh_nodes_reconnect
ON mesh_nodes (last_reconnect);
