#!/bin/bash

# Create necessary directories
mkdir -p data
mkdir -p hassio

# Set up machine-id for dbus
if [ ! -f /etc/machine-id ]; then
    sudo sh -c 'dbus-uuidgen > /etc/machine-id'
fi

# Set up AppArmor (required by supervisor)
if ! command -v apparmor_parser &> /dev/null; then
    echo "Installing AppArmor..."
    sudo apt-get update
    sudo apt-get install -y apparmor apparmor-utils
fi

# Start the development environment
docker-compose -f docker-compose.dev.yml up -d

# Wait for supervisor to be ready
echo "Waiting for Home Assistant to start..."
while ! curl -s localhost:8123 > /dev/null; do
    sleep 5
done

echo "Development environment is ready!"
echo "Access Home Assistant at http://localhost:8123"
echo "Your add-on will be available in the local add-ons section" 