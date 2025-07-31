-- This adds the pkt_id column to rx_packets

ALTER TABLE rx_packets
ADD pkt_id INTEGER;