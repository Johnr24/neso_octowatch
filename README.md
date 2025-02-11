# Neso Octowatch Home Assistant Integration

This custom integration allows you to monitor Neso Octowatch data in Home Assistant.

## Installation

### Manual Installation

1. Copy the `custom_components/neso_octowatch` directory to your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.
3. Go to Settings -> Devices & Services
4. Click "Add Integration"
5. Search for "Neso Octowatch"

### HACS Installation

1. Open HACS in your Home Assistant instance
2. Click on "Custom Repositories"
3. Add this repository URL with category "Integration"
4. Install through HACS
5. Restart Home Assistant

## Configuration

The integration can be configured through the Home Assistant UI. The following options are available:

- Scan Interval: How often to fetch new data (in seconds, default: 300)

## Available Sensors

This integration provides the following sensors:

- Octopus Neso Status
- Octopus Neso Utilization (%)
- Octopus Neso Highest Accepted (W)

## Development

If you want to contribute to this integration, please read the [Contributing guidelines](CONTRIBUTING.md).

1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
