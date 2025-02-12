"""The Octopus DFS Session Watch integration."""
from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from urllib import parse
import pandas as pd
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Octopus DFS Session Watch component."""
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Octopus DFS Session Watch from a config entry."""
    coordinator = DfsSessionWatchCoordinator(hass, entry)
    # Force an immediate refresh before setting up sensors
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class DfsSessionWatchCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Octopus DFS Session Watch data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.entry = entry

    async def _async_update_data(self):
        """Fetch data from NESO API."""
        try:
            bids_data = await self.hass.async_add_executor_job(self._check_octopus_bids)
            utilization_data = await self.hass.async_add_executor_job(self._check_utilization)
            # Merge the two dictionaries
            return {**bids_data, **utilization_data}
        except Exception as e:
            LOGGER.error("Error fetching data from NESO API: %s", e)
            return {}

    def _check_utilization(self):
        """Check utilization data from NESO API."""
        sql_query = 'SELECT * FROM "cc36fff5-5f6f-4fde-8932-c935d982ecd8" ORDER BY "_id" ASC LIMIT 1000'
        params = {'sql': sql_query}

        try:
            # Debug log to verify the exact query being sent
            LOGGER.debug("Sending SQL query: %s", sql_query)
            
            response = requests.get(
                'https://api.neso.energy/api/3/action/datastore_search_sql', 
                params=params,
                headers={'User-Agent': 'neso_octowatch/1.0'}
            )
            
            if response.status_code == 409:
                LOGGER.warning("NESO API Conflict error. This might be due to rate limiting or API changes.")
                return {}
                
            response.raise_for_status()
            json_response = response.json()
            
            if not json_response.get('success'):
                LOGGER.error("NESO API Error: %s", json_response.get('error', 'Unknown error'))
                return {}
            
            data = json_response["result"]
            df = pd.DataFrame(data["records"])
            
            if df.empty:
                return {}
            
            # Debug logging for DataFrame contents
            LOGGER.debug("DataFrame columns: %s", df.columns.tolist())
            LOGGER.debug("Status values in DataFrame: %s", df['Status'].unique() if 'Status' in df.columns else "No Status column")
            LOGGER.debug("DataFrame head: %s", df.head().to_dict('records'))
            
            # Get the most recent entry
            latest = df.iloc[0]
            # Convert and sort dates
            df['Delivery Date'] = pd.to_datetime(df['Delivery Date'])
            
            # Filter for dates from today onwards
            today = pd.Timestamp.now().normalize()
            future_df = df[df['Delivery Date'] >= today]
            
            # Use the earliest future date or most recent past date if no future dates
            latest = future_df.iloc[0] if not future_df.empty else df.iloc[0]
            
            # Filter Octopus-specific data
            octopus_df = df[df['Registered DFS Participant'] == 'OCTOPUS ENERGY LIMITED']
            octopus_latest = octopus_df.iloc[0] if not octopus_df.empty else None
            
            # Find highest accepted bid
            # Sort by delivery date in ASCending order
            df = df.sort_values('Delivery Date', ascending=False)
            
            # Get the most recent date
            most_recent_date = df['Delivery Date'].iloc[0] if not df.empty else None
            LOGGER.debug("Most recent date in dataset: %s", most_recent_date)
            
            highest_accepted = None
            
            if most_recent_date is not None:
                # Get all bids for the most recent date
                recent_bids = df[df['Delivery Date'] == most_recent_date]
                # Filter for accepted bids
                accepted_bids = recent_bids[recent_bids['Status'].str.upper().str.contains('ACCEPTED', na=False)]
                
                if not accepted_bids.empty:
                    # Get the highest price among accepted bids
                    highest_accepted = accepted_bids.loc[accepted_bids['Utilisation Price GBP per MWh'].astype(float).idxmax()]

            LOGGER.debug("Recent date bids count: %d, Accepted bids: %d", len(recent_bids) if 'recent_bids' in locals() else 0, len(accepted_bids) if 'accepted_bids' in locals() else 0)

            LOGGER.debug("Initial data fetch. Processing today's bids...")
            LOGGER.debug("Number of accepted bids today: %s", len(accepted_bids))
            LOGGER.debug("Accepted bids participants: %s", accepted_bids['Registered DFS Participant'].unique() if not accepted_bids.empty else "No accepted bids")
            LOGGER.debug("Market accepted bids prices: %s", accepted_bids['Utilisation Price GBP per MWh'].tolist() if not accepted_bids.empty else "No accepted bids")
            LOGGER.debug("Raw DataFrame head: %s", df.head().to_dict())
            
            if highest_accepted is not None:
                LOGGER.debug("Selected highest bid price: %s", highest_accepted['Utilisation Price GBP per MWh'])
                LOGGER.debug("Selected bid delivery date: %s", highest_accepted['Delivery Date'])
                LOGGER.debug("Highest accepted bid from participant: %s", highest_accepted['Registered DFS Participant'])
                LOGGER.debug("Found highest accepted bid: %s GBP/MWh", highest_accepted['Utilisation Price GBP per MWh'])
            else:
                LOGGER.warning("No accepted bids found for the most recent date")
            
            # Get Octopus-specific status
            status = octopus_latest.get('Status', 'UNKNOWN') if octopus_latest is not None else 'UNKNOWN'
                
            LOGGER.debug("All dates in dataset: %s", df['Delivery Date'].unique())
            LOGGER.debug("Today's date: %s", today)
            LOGGER.debug("All Octopus dates: %s", octopus_df['Delivery Date'].unique() if not octopus_df.empty else "No Octopus entries")
            LOGGER.debug("Future dates available: %s", future_df['Delivery Date'].unique() if not future_df.empty else "None")
            LOGGER.debug("Octopus future dates: %s", 
                octopus_df[octopus_df['Delivery Date'] >= today]['Delivery Date'].unique() if not octopus_df.empty else "No future Octopus dates")
            
            # Use the most recent date from any participant for delivery_date
            most_recent_date = df['Delivery Date'].max()
            LOGGER.debug("Most recent session date (any participant): %s", most_recent_date)
            
            # For other fields, still use Octopus-specific data
            delivery_date = most_recent_date
            
            # Get Octopus bid for this date if it exists
            octopus_latest_for_date = octopus_df[octopus_df['Delivery Date'] == most_recent_date].iloc[0] if not octopus_df[octopus_df['Delivery Date'] == most_recent_date].empty else None
            LOGGER.debug("Found Octopus bid for most recent date: %s", "Yes" if octopus_latest_for_date is not None else "No")
            
            if highest_accepted is not None:
                LOGGER.debug("Highest accepted bid date: %s", highest_accepted['Delivery Date'])
            LOGGER.debug(
                "Setting utilization status to: %s (from record: %s)",
                status,
                {k: v for k, v in latest.items() if k in ['Status', 'Delivery Date', 'From', 'To']}
            )
            
            states = {
                "octopus_dfs_session_utilization": {
                    "state": status,
                    "attributes": {
                        "last_checked": datetime.now().isoformat(),
                    }
                },
                "octopus_dfs_session_delivery_date": {
                    "state": self._convert_to_serializable(delivery_date),
                    "attributes": {
                        "raw_date": delivery_date,
                        "time_from": self._convert_to_serializable(latest.get('From')),
                        "time_to": self._convert_to_serializable(latest.get('To')),
                        "volume": self._convert_to_serializable(octopus_latest.get('DFS Volume MW')) if octopus_latest is not None else None,
                        "last_update": datetime.now().isoformat()
                    }
                },
                "octopus_dfs_session_highest_accepted": {
                    "state": (
                        highest_accepted['Utilisation Price GBP per MWh']
                        if highest_accepted is not None and pd.notna(highest_accepted['Utilisation Price GBP per MWh'])
                        else None
                    ),
                    "attributes": {} if highest_accepted is None else {
                        "delivery_date": self._convert_to_serializable(highest_accepted['Delivery Date']) if highest_accepted is not None else None,
                        "time_from": self._convert_to_serializable(highest_accepted['From']) if highest_accepted is not None else None,
                        "time_to": self._convert_to_serializable(highest_accepted['To']) if highest_accepted is not None else None,
                        "volume": self._convert_to_serializable(highest_accepted['DFS Volume MW']) if highest_accepted is not None else None,
                        "last_update": datetime.now().isoformat()
                    }
                }
            }

            # Process group data for time windows, volume, and price
            time_window_state = None
            time_window_attrs = {}
            volume_state = None
            volume_attrs = {}
            price_state = None
            price_attrs = {}
            
            if not octopus_df.empty:
                # Sort by delivery date and time
                octopus_df_sorted = octopus_df.sort_values(['Delivery Date', 'From'])
                time_windows = []
                volumes = []
                
                # Group entries in pairs
                rows = octopus_df_sorted.to_dict('records')
                for i in range(0, len(rows), 2):
                    row1 = rows[i]
                    row2 = rows[i + 1] if i + 1 < len(rows) else None
                    
                    # First entry in pair
                    time_from1 = self._convert_to_serializable(row1['From'])
                    time_to1 = self._convert_to_serializable(row1['To'])
                    volume1 = self._convert_to_serializable(row1['DFS Volume MW'])
                    
                    if row2:
                        # If we have a second entry, combine them
                        time_from2 = self._convert_to_serializable(row2['From'])
                        time_to2 = self._convert_to_serializable(row2['To'])
                        volume2 = self._convert_to_serializable(row2['DFS Volume MW'])
                        
                        time_windows.append(f"{time_from1} - {time_to1}, {time_from2} - {time_to2}")
                        volumes.append(f"{volume1}, {volume2}")
                    else:
                        # Just add the single entry if no pair
                        time_windows.append(f"{time_from1} - {time_to1}")
                        volumes.append(str(volume1))
                
                # Calculate average price from all bids
                avg_price = octopus_df['Utilisation Price GBP per MWh'].mean()
                
                # Set states and attributes
                time_window_state = "; ".join(time_windows)
                time_window_attrs = {
                    "individual_windows": [
                        window.split(", ")
                        for window in time_windows
                    ]
                }
                
                volume_state = "; ".join(volumes)
                volume_attrs = {
                    "individual_volumes": [
                        [float(v.strip()) for v in volume.split(",")]
                        for volume in volumes
                    ]
                }
                
                price_state = self._convert_to_serializable(avg_price)
                price_attrs = {
                    "individual_prices": [
                        self._convert_to_serializable(price)
                        for price in octopus_df['Utilisation Price GBP per MWh'].tolist()
                    ]
                }
                
            # Add to states dictionary
            states.update({
                "octopus_dfs_session_time_window": {
                    "state": time_window_state,
                    "attributes": time_window_attrs
                },
                "octopus_dfs_session_price": {
                    "state": price_state,
                    "attributes": price_attrs
                },
                "octopus_dfs_session_volume": {
                    "state": volume_state,
                    "attributes": volume_attrs
                }
            })
            
            return states
            
        except Exception as e:
            LOGGER.error(
                "Error checking utilization from %s: %s",
                'https://api.neso.energy/api/3/action/datastore_search_sql',
                str(e))
            return {
                "octopus_dfs_session_utilization": {
                    "state": "error",
                    "attributes": {
                        "last_checked": datetime.now().isoformat(),
                        "error": str(e)
                    }
                }
            }
            
    def _check_octopus_bids(self):
        """Check Octopus Energy bids from NESO API."""
        sql_query = 'SELECT COUNT(*) OVER () AS _count, * FROM "f5605e2b-b677-424c-8df7-d0ce4ee03cef" WHERE "Participant Bids Eligible" LIKE \'%OCTOPUS ENERGY LIMITED%\' ORDER BY "_id" ASC LIMIT 1000'
        params = {'sql': sql_query}

        try:
            # Debug log to verify the exact query being sent
            LOGGER.debug("Sending Octopus bids SQL query: %s", sql_query)
            
            response = requests.get('https://api.neso.energy/api/3/action/datastore_search_sql', 
                                params=params,
                                headers={'User-Agent': 'neso_octowatch/1.0'})
            
            if response.status_code == 409:
                LOGGER.warning("API Conflict error. This might be due to rate limiting or API changes.")
                return {}
                
            response.raise_for_status()
            json_response = response.json()
            
            if not json_response.get('success'):
                LOGGER.error("API Error: %s", json_response.get('error', 'Unknown error'))
                return {}
                
            if 'result' not in json_response:
                LOGGER.error("'result' key not found in response")
                return {}
                
            data = json_response["result"]
            df = pd.DataFrame(data["records"])

            if not df.empty:
                # Convert and sort dates
                df['Delivery Date'] = pd.to_datetime(df['Delivery Date'])
                # Filter for dates from today onwards
                today = pd.Timestamp.now().normalize()
                future_df = df[df['Delivery Date'] >= today]
                
                LOGGER.debug("Bids - All dates: %s", df['Delivery Date'].unique())
                LOGGER.debug("Bids - Future dates: %s", future_df['Delivery Date'].unique() if not future_df.empty else "None")
            
            states = {
                "octopus_dfs_session_details": {
                    "state": self._format_time_slots(df) if not df.empty else "No entries found",
                    "attributes": {
                        "raw_data": [{k: self._convert_to_serializable(v) for k, v in record.items()} 
                                  for record in (df[df['Delivery Date'] == df['Delivery Date'].max()].to_dict('records') if not df.empty else [])]
                    }
                }
            }
            
            return states
                
        except Exception as e:
            LOGGER.error(
                "Error checking octopus bids from %s: %s",
                'https://api.neso.energy/api/3/action/datastore_search_sql',
                str(e))
            return {
            }
            
    def _format_time_slots(self, df):
        """Format time slots into a readable summary, only for the most recent date."""
        if df.empty:
            return "No entries found"
            
        # Sort and get most recent date
        df_sorted = df.sort_values(['Delivery Date', 'From'])
        # Convert Delivery Date to datetime if it's not already
        df_sorted['Delivery Date'] = pd.to_datetime(df_sorted['Delivery Date'])
        LOGGER.debug("Available delivery dates: %s", df_sorted['Delivery Date'].unique())
        # Try to get the nearest future date
        future_dates = df_sorted[df_sorted['Delivery Date'] >= pd.Timestamp.now().normalize()]
        if not future_dates.empty:
            most_recent_date = future_dates['Delivery Date'].min()
        else:
            # If no future dates, get the most recent past date
            most_recent_date = df_sorted['Delivery Date'].max()
        LOGGER.debug("Selected delivery date: %s", most_recent_date)
        df_recent = df_sorted[df_sorted['Delivery Date'] == most_recent_date]
        
        time_slots = []
        time_slots.append(f"\n**{most_recent_date}**")
        
        for _, row in df_recent.iterrows():
            period = f"• {row['From']} - {row['To']}"
            if pd.notna(row.get('Service Requirement MW')):
                period += f" ({row['Service Requirement MW']} MW)"
            if pd.notna(row.get('Guaranteed Acceptance Price GBP per MWh')):
                period += f" with a guaranteed acceptance price of £{row['Guaranteed Acceptance Price GBP per MWh']}/MWh"
            time_slots.append(period)
        
        return "\n".join(time_slots)

    @staticmethod
    def _convert_to_serializable(obj):
        """Convert pandas/numpy types to JSON serializable types."""
        if pd.isna(obj):
            return None
        elif isinstance(obj, (pd.Timestamp, datetime)):
            # Ensure consistent UTC timezone
            if obj.tzinfo is None or obj.tzinfo.utcoffset(obj) is None:
                obj = obj.replace(tzinfo=datetime.now().astimezone().tzinfo)
            # Convert to UTC and format without microseconds
            LOGGER.debug("Converting timestamp: %s", obj)
            utc_time = obj.astimezone(datetime.now().astimezone().tzinfo)
            return utc_time.replace(microsecond=0).isoformat()
        elif hasattr(obj, 'item'):  # This catches numpy types like int64
            return obj.item()
        elif isinstance(obj, dict):
            return {k: DfsSessionWatchCoordinator._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [DfsSessionWatchCoordinator._convert_to_serializable(v) for v in obj]
        return obj
