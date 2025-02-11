# Neso Octowatch Integration for Home Assistant

[![HACS Default][hacs-shield]][hacs]
[![GitHub Release][releases-shield]][releases]

A Home Assistant integration for monitoring Octopus Energy participation in the National Grid ESO Demand Flexibility Service.

## Installation

### HACS (Recommended)

1. Install HACS if you haven't already (see [HACS installation](https://hacs.xyz/docs/installation/installation))
2. Search for "Neso Octowatch" in HACS
3. Click Install
4. Restart Home Assistant
5. Add the integration via the Home Assistant UI (Settings -> Devices & Services -> Add Integration)

### Manual Installation

1. Download the latest release from the releases page
2. Extract the zip file
3. Copy the `neso_octowatch` directory to your Home Assistant's `custom_components` directory
4. Restart Home Assistant
5. Add the integration via the Home Assistant UI (Settings -> Devices & Services -> Add Integration)

## Features

- Monitor Octopus Energy's participation in ESO Demand Flexibility Service
- Track bid status, prices, and volumes
- View highest accepted bids
- Real-time updates on utilization and delivery windows

## Sensors

The integration provides the following sensors:

- Octopus Neso Status
- Octopus Neso Utilization
- Octopus Neso Delivery Date
- Octopus Neso Time Window
- Octopus Neso Price
- Octopus Neso Volume
- Octopus Neso Highest Accepted

## Support

For bugs and feature requests, please [open an issue](https://github.com/Johnr24/neso_octowatch/issues)

[hacs-shield]: https://img.shields.io/badge/HACS-Default-orange.svg
[hacs]: https://github.com/hacs/integration
[releases-shield]: https://img.shields.io/github/release/Johnr24/neso_octowatch.svg
[releases]: https://github.com/Johnr24/neso_octowatch/releases
