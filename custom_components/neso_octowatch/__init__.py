"""The Neso Octowatch integration."""
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

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Neso Octowatch component."""
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Neso Octowatch from a config entry."""
    coordinator = NesoOctowatchCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class NesoOctowatchCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Neso Octowatch data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
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
            _LOGGER.error("Error fetching data: %s", e)
            return {}

    def _check_utilization(self):
        """Check utilization data from NESO API."""
        sql_query = '''
            SELECT * 
            FROM "cc36fff5-5f6f-4fde-8932-c935d982ecd8" 
            WHERE "Registered DFS Participant" = 'OCTOPUS ENERGY LIMITED'
            ORDER BY "_id" DESC 
            LIMIT 100
        '''
        params = {'sql': sql_query}

        try:
            response = requests.get(
                'https://api.neso.energy/api/3/action/datastore_search_sql', 
                params=parse.urlencode(params)
            )
            
            if response.status_code == 409:
                _LOGGER.warning("API Conflict error. This might be due to rate limiting or API changes.")
                return {}
                
            response.raise_for_status()
            json_response = response.json()
            
            if not json_response.get('success'):
                _LOGGER.error("API Error: %s", json_response.get('error', 'Unknown error'))
                return {}
            
            data = json_response["result"]
            df = pd.DataFrame(data["records"])
            
            if df.empty:
                return {}
            
            # Get the most recent entry
            latest = df.iloc[0]
            
            # Find highest accepted bid
            accepted_bids = df[df['Status'] == 'ACCEPTED']
            highest_accepted = None
            if not accepted_bids.empty:
                highest_accepted = accepted_bids.loc[accepted_bids['Utilisation Price GBP per MWh'].idxmax()]
            
            states = {
                "octopus_neso_utilization": {
                    "state": latest.get('Status', 'UNKNOWN'),
                    "attributes": {
                        "last_checked": datetime.now().isoformat(),
                    }
                },
                "octopus_neso_delivery_date": {
                    "state": self._convert_to_serializable(latest.get('Delivery Date')),
                    "attributes": {}
                },
                "octopus_neso_time_window": {
                    "state": f"{self._convert_to_serializable(latest.get('From'))} - {self._convert_to_serializable(latest.get('To'))}",
                    "attributes": {}
                },
                "octopus_neso_price": {
                    "state": self._convert_to_serializable(latest.get('Utilisation Price GBP per MWh')),
                    "attributes": {}
                },
                "octopus_neso_volume": {
                    "state": self._convert_to_serializable(latest.get('DFS Volume MW')),
                    "attributes": {}
                },
                "octopus_neso_highest_accepted": {
                    "state": self._convert_to_serializable(highest_accepted['Utilisation Price GBP per MWh']) if highest_accepted is not None else "No accepted bids",
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
            _LOGGER.error("Error checking utilization: %s", e)
            return {
                "octopus_neso_utilization": {
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
            LIMIT 1000
        '''
        params = {'sql': sql_query}

        try:
            response = requests.get('https://api.neso.energy/api/3/action/datastore_search_sql', 
                                params=parse.urlencode(params))
            
            if response.status_code == 409:
                _LOGGER.warning("API Conflict error. This might be due to rate limiting or API changes.")
                return {}
                
            response.raise_for_status()
            json_response = response.json()
            
            if not json_response.get('success'):
                _LOGGER.error("API Error: %s", json_response.get('error', 'Unknown error'))
                return {}
                
            if 'result' not in json_response:
                _LOGGER.error("'result' key not found in response")
                return {}
                
            data = json_response["result"]
            df = pd.DataFrame(data["records"])
            
            states = {
                "octopus_neso_status": {
                    "state": "active" if not df.empty else "inactive",
                    "attributes": {
                        "last_checked": datetime.now().isoformat(),
                        "entry_count": len(df) if not df.empty else 0,
                        "service_type": self._convert_to_serializable(df['Service Requirement Type'].iloc[0]) if not df.empty else None,
                        "dispatch_type": self._convert_to_serializable(df['Dispatch Type'].iloc[0]) if not df.empty else None,
                        "most_recent_date": self._convert_to_serializable(df['Delivery Date'].max()) if not df.empty else None
                    }
                },
                "octopus_neso_details": {
                    "state": self._format_time_slots(df) if not df.empty else "No entries found",
                    "attributes": {
                        "raw_data": [{k: self._convert_to_serializable(v) for k, v in record.items()} 
                                  for record in (df[df['Delivery Date'] == df['Delivery Date'].max()].to_dict('records') if not df.empty else [])]
                    }
                }
            }
            
            return states
                
        except Exception as e:
            _LOGGER.error("Error checking octopus bids: %s", e)
            return {
                "octopus_neso_status": {
                    "state": "error",
                    "attributes": {
                        "last_checked": datetime.now().isoformat(),
                        "error": str(e)
                    }
                }
            }
            
    def _format_time_slots(self, df):
        """Format time slots into a readable summary, only for the most recent date."""
        if df.empty:
            return "No entries found"
            
        # Sort and get most recent date
        df_sorted = df.sort_values(['Delivery Date', 'From'])
        most_recent_date = df_sorted['Delivery Date'].max()
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
            return obj.isoformat()
        elif hasattr(obj, 'item'):  # This catches numpy types like int64
            return obj.item()
        elif isinstance(obj, dict):
            return {k: NesoOctowatchCoordinator._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [NesoOctowatchCoordinator._convert_to_serializable(v) for v in obj]
        return obj