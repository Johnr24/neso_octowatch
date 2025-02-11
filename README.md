# Octopus DFS Session Watch for Home Assistant 🏠⚡

A Home Assistant integration for monitoring Octopus Energy DFS Session trading platform.

## Available Sensors 📊

### Octopus DFS Session Utilization 📈
- **Description**: Shows the current utilization level of the platform
- **Unit**: Percentage (%)
- **Type**: Measurement
- **Example**: "75.5%"
- **Notes**: May also display text status when numerical value isn't available

### Octopus DFS Session Delivery Date 📅
- **Description**: The delivery date for the energy contracts
- **Type**: Timestamp
- **Format**: UTC datetime
- **Example**: "2025-02-11"
- **Notes**: Supports multiple date formats including ISO format and human-readable dates

### Octopus DFS Session Time Window ⏰
- **Description**: The Demand Flexibility Service (DFS) session period for Octopus Energy
- **Type**: Text
- **Example**: "16:00-19:00"
- **Notes**: Indicates when the DFS service is scheduled to be active

### Octopus DFS Session Price 💰
- **Description**: Current energy price on the platform
- **Unit**: GBP/MWh (British Pounds per Megawatt Hour)
- **Type**: Monetary value
- **Precision**: 2 decimal places
- **Example**: "123.45 GBP/MWh"

### Octopus DFS Session Volume ⚡
- **Description**: Trading volume measurement
- **Unit**: MW (Megawatts)
- **Type**: Power measurement
- **Precision**: 1 decimal place
- **Example**: "50.5 MW"

### Market Highest Accepted Bid 📊
- **Description**: Highest accepted bid price from any market participant for the current delivery date
- **Unit**: GBP/MWh
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
