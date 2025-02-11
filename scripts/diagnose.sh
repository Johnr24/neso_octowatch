#!/bin/bash

echo "=== NESO Octopus Watch Diagnostics ==="
echo

echo "1. Checking Docker containers..."
docker ps -a | grep -E 'hassio|neso|supervisor'

echo -e "\n2. Checking addon logs..."
ADDON_CONTAINER=$(docker ps -q --filter name=addon_local_neso_octowatch)
if [ ! -z "$ADDON_CONTAINER" ]; then
    docker logs $ADDON_CONTAINER
else
    echo "Addon container not found. Checking supervisor logs..."
    docker logs hassio_supervisor | grep -i "neso"
fi

echo -e "\n3. Checking addon status..."
curl -s -X GET \
  "http://supervisor/addons/local_neso_octowatch/info" \
  -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" | jq '.'

echo -e "\n4. Checking file permissions..."
ls -la /hassio/addons/local/neso_octowatch

echo -e "\n5. Validating configuration..."
echo "config.yaml contents:"
cat config.yaml

echo -e "\nChecking for required files:"
required_files=("Dockerfile" "config.yaml" "run" "nesoscan.py")
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
    fi
done 