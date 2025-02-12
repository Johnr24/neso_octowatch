# Plan: Merging Sensor Data for DFS Session Watch

## Overview
We need to modify how three specific sensors handle their data:
- `sensor.octopus_dfs_session_time_window` (pairs grouped by time)
- `sensor.octopus_dfs_session_volume` (pairs grouped by time)
- `sensor.octopus_dfs_session_price` (average of all octopus bids)

## Implementation Details

### 1. Data Processing Changes (DfsSessionWatchCoordinator)
Location: `_check_utilization` method in DfsSessionWatchCoordinator class

#### For Time Window and Volume sensors
- Group entries by time in pairs
- Sort data by delivery date and time
- Store pairs in semicolon-separated format
- Preserve individual values in attributes

#### For Price sensor
- Calculate average of all Octopus bids from that day, 
- Store individual prices in attributes for reference #perfect! 

### 2. Code Changes Required

#### a. Data Processing Updates
```python
# In _check_utilization method
if not octopus_df.empty:
    # Sort by delivery date and time
    octopus_df = octopus_df.sort_values(['Delivery Date', 'From'])
    time_windows = []
    volumes = []
    for _, row in octopus_df.iterrows():
        time_windows.append(f"{row['From']} - {row['To']}")
        volumes.append(row['DFS Volume MW'])
    
    # Join pairs with semicolon
    time_window_state = "; ".join(time_windows)
    volume_state = "; ".join(str(v) for v in volumes)
    
    # Calculate average price
    price_state = octopus_df['Utilisation Price GBP per MWh'].mean()
```

#### b. States Dictionary Updates
```python
states = {
    ...
    "octopus_dfs_session_time_window": {
        "state": time_window_state,
        "attributes": {
            "individual_windows": time_windows
        }
    },
    "octopus_dfs_session_volume": {
        "state": volume_state,
        "attributes": {
            "individual_volumes": volumes
        }
    },
    "octopus_dfs_session_price": {
        "state": price_state,
        "attributes": {
            "individual_prices": octopus_df['Utilisation Price GBP per MWh'].tolist()
        }
    }
}
```

### 3. Benefits
1. Maintains data integrity by preserving individual values
2. Clear presentation of grouped data
3. Preserves existing functionality
4. No changes needed to sensor entity class

### 4. Testing Considerations
1. Verify correct grouping of time windows and volumes
2. Ensure accurate price averaging
3. Check attribute data persistence
4. Validate sensor state updates