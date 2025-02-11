#!/bin/bash

# Build the addon
docker build -t local/neso_octowatch .

# Restart the addon in supervisor
curl -X POST \
  "http://supervisor/addons/local_neso_octowatch/restart" \
  -H "Authorization: Bearer ${SUPERVISOR_TOKEN}"

# Follow the logs
docker logs -f $(docker ps -q --filter name=addon_local_neso_octowatch) 