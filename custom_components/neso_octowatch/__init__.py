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
            LOGGER.error("Error fetching data from NESO SCADA: %s", e)
            return {}

    def _check_utilization(self):
        """Check utilization data from NESO API."""
        sql_query = '''
            SELECT * 
            FROM "cc36fff5-5f6f-4fde-8932-c935d982ecd8" 
            WHERE _id IS NOT NULL
            ORDER BY "_id" DESC 
            LIMIT 10000
        '''
        params = {'sql': sql_query}

        try:
            response = requests.get(
                'https://api.neso.energy/api/3/action/datastore_search_sql', 
                params=parse.urlencode(params)
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
            today = pd.Timestamp.now().normalize()
            
            # Get all bids for today
            todays_bids = df[df['Delivery Date'].dt.normalize() == today]
            
            LOGGER.debug("Found %d total bids for today from all participants", len(todays_bids))
            
            # Debug logging for bids
            LOGGER.debug("Today's bids found: %d", len(todays_bids))
            LOGGER.debug("Today's bids statuses: %s", todays_bids['Status'].unique() if not todays_bids.empty else "No bids")
            
            accepted_bids = todays_bids[todays_bids['Status'].str.upper() == 'ACCEPTED']
            highest_accepted = None
            
            LOGGER.debug("Initial data fetch. Processing today's bids...")
            LOGGER.debug("Number of accepted bids today: %s", len(accepted_bids))
            LOGGER.debug("Accepted bids participants: %s", accepted_bids['Registered DFS Participant'].unique() if not accepted_bids.empty else "No accepted bids")
            LOGGER.debug("Market accepted bids prices: %s", accepted_bids['Utilisation Price GBP per MWh'].tolist() if not accepted_bids.empty else "No accepted bids")
            
            if not accepted_bids.empty:
                # Get the highest accepted bid from any participant
                highest_accepted_idx = accepted_bids['Utilisation Price GBP per MWh'].idxmax()
                highest_accepted = accepted_bids.loc[highest_accepted_idx]
                LOGGER.debug("Highest accepted bid from participant: %s", highest_accepted['Registered DFS Participant'])
                LOGGER.debug("Found highest accepted bid: %s GBP/MWh", highest_accepted['Utilisation Price GBP per MWh'])
            
            # Get Octopus-specific status
            status = octopus_latest.get('Status', 'UNKNOWN') if octopus_latest is not None else 'UNKNOWN'
                
            LOGGER.debug("All dates in dataset: %s", df['Delivery Date'].unique())
            LOGGER.debug("Today's date: %s", today)
            LOGGER.debug("Future dates available: %s", future_df['Delivery Date'].unique() if not future_df.empty else "None")
            LOGGER.debug("Selected latest date: %s", latest['Delivery Date'])
            if highest_accepted is not None:
                LOGGER.debug("Highest accepted bid date: %s", highest_accepted['Delivery Date'])
            delivery_date = octopus_latest['Delivery Date'] if octopus_latest is not None else None
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
                        "raw_date": octopus_latest.get('Delivery Date') if octopus_latest is not None else None,
                        "time_from": self._convert_to_serializable(octopus_latest.get('From')) if octopus_latest is not None else None,
                        "time_to": self._convert_to_serializable(octopus_latest.get('To')) if octopus_latest is not None else None,
                        "volume": self._convert_to_serializable(octopus_latest.get('DFS Volume MW')) if octopus_latest is not None else None,
                        "last_update": datetime.now().isoformat()
                    }
                },
                "octopus_dfs_session_time_window": {
                    "state": f"{self._convert_to_serializable(octopus_latest.get('From'))} - {self._convert_to_serializable(octopus_latest.get('To'))}" if octopus_latest is not None else None,
                    "attributes": {}
                },
                "octopus_dfs_session_price": {
                    "state": self._convert_to_serializable(octopus_latest.get('Utilisation Price GBP per MWh')) if octopus_latest is not None else None,
                    "attributes": {}
                },
                "octopus_dfs_session_volume": {
                    "state": self._convert_to_serializable(octopus_latest.get('DFS Volume MW')) if octopus_latest is not None else None,
                    "attributes": {}
                },
                "octopus_dfs_session_highest_accepted": {
                    "state": (
                        float(self._convert_to_serializable(highest_accepted['Utilisation Price GBP per MWh'])) 
                        if highest_accepted is not None and pd.notna(highest_accepted['Utilisation Price GBP per MWh']) 
                        else None
                    ),
                    "attributes": {
                        "delivery_date": self._convert_to_serializable(highest_accepted['Delivery Date']) if highest_accepted is not None else None,
                        "time_from": self._convert_to_serializable(highest_accepted['From']) if highest_accepted is not None else None,
                        "time_to": self._convert_to_serializable(highest_accepted['To']) if highest_accepted is not None else None,
                        "volume": self._convert_to_serializable(highest_accepted['DFS Volume MW']) if highest_accepted is not None else None,
                        "last_update": datetime.now().isoformat()
                    }
                }
            }
            
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
        sql_query = '''
            SELECT COUNT(*) OVER () AS _count, * 
            FROM "f5605e2b-b677-424c-8df7-d0ce4ee03cef" 
            WHERE "Participant Bids Eligible" LIKE '%OCTOPUS ENERGY LIMITED%'
            ORDER BY "_id" DESC
            LIMIT 10000
        '''
        params = {'sql': sql_query}

        try:
            response = requests.get('https://api.neso.energy/api/3/action/datastore_search_sql', 
                                params=parse.urlencode(params))
            
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