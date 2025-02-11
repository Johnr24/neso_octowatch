# Neso Octowatch for Home Assistant 🏠⚡

A Home Assistant integration for monitoring Octopus Energy Neso trading platform.

## Available Sensors 📊

### Octopus Neso Status 🟢
- **Description**: Displays the current status of the Neso trading platform
- **Type**: Text status indicator
- **Example Values**: "Open", "Closed", etc.

### Octopus Neso Utilization 📈
- **Description**: Shows the current utilization level of the platform
- **Unit**: Percentage (%)
- **Type**: Measurement
- **Example**: "75.5%"
- **Notes**: May also display text status when numerical value isn't available

### Octopus Neso Delivery Date 📅
- **Description**: The delivery date for the energy contracts
- **Type**: Timestamp
- **Format**: UTC datetime
- **Example**: "2025-02-11"
- **Notes**: Supports multiple date formats including ISO format and human-readable dates

### Octopus Neso Time Window ⏰
- **Description**: The trading time window information
- **Type**: Text
- **Example**: "14:00-14:30"
- **Notes**: Indicates the current or next trading period

### Octopus Neso Price 💰
- **Description**: Current energy price on the platform
- **Unit**: GBP/MWh (British Pounds per Megawatt Hour)
- **Type**: Monetary value
- **Precision**: 2 decimal places
- **Example**: "123.45 GBP/MWh"

### Octopus Neso Volume ⚡
- **Description**: Trading volume measurement
- **Unit**: MW (Megawatts)
- **Type**: Power measurement
- **Precision**: 1 decimal place
- **Example**: "50.5 MW"

### Octopus Neso Highest Accepted 📊
- **Description**: Highest accepted price in the current trading period
- **Unit**: GBP/MWh (when numerical)
- **Type**: Monetary value or text status
- **Precision**: 2 decimal places when monetary
- **Example**: "145.50 GBP/MWh"
- **Notes**: May display text status when numerical value isn't available

## Technical Details 🔧

- **Update Interval**: 5 minutes by default
- **Data Coordination**: Uses Home Assistant's DataUpdateCoordinator
- **Error Handling**: Graceful handling of various data formats and potential API issues
- **Timezone**: All timestamps are in UTC

## Installation 💻

1. Install via HACS (Home Assistant Community Store)
2. Add the integration through the Home Assistant interface
3. Configure your credentials
4. The sensors will be automatically created and start updating

## Support 🤝

If you encounter any issues or have questions, please open an issue on GitHub.
