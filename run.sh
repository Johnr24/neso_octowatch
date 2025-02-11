#!/bin/sh

# Get config values from environment or use default
export CHECK_INTERVAL=${CHECK_INTERVAL:-300}

# Create data directory if it doesn't exist
mkdir -p /data/neso_octowatch

# Run the Python script
python3 /app/nesoscan.py
