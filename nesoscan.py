# Install pandas package if you don't have it already
# pip install pandas

# Get data and convert into dataframe
import pandas as pd
import requests
from urllib import parse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import time
import sys

# Add state file path for the integration
STATES_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "custom_components" / "neso_octowatch" / "states.json"

# Get check interval from environment or use default (5 minutes)
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))

def get_config():
    """Load configuration"""
    try:
        config_path = Path(os.path.dirname(os.path.abspath(__file__))) / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        return {}
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return {}

def save_states(states):
    """Save states for Home Assistant to read"""
    STATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert all values to JSON-serializable format
    def convert_dict(d):
        return {
            k: convert_to_serializable(v) if isinstance(v, dict) else v
            for k, v in d.items()
        }
    
    json_states = {}
    for key, value in states.items():
        if isinstance(value, dict):
            json_states[key] = convert_dict(value)
        else:
            json_states[key] = value
    
    # Write states to file
    with open(STATES_PATH, 'w') as f:
        json.dump(json_states, f, indent=2)

def format_time_slots(df):
    """Format time slots into a readable summary, only for the most recent date"""
    time_slots = []
    # Sort by Delivery Date and From time
    df_sorted = df.sort_values(['Delivery Date', 'From'])
    
    # Get the most recent date
    most_recent_date = df_sorted['Delivery Date'].max()
    
    # Filter for most recent date only
    df_recent = df_sorted[df_sorted['Delivery Date'] == most_recent_date]
    
    current_mw = None
    current_price = None
    period_start = None
    period_end = None
    
    def add_period():
        if period_start and period_end:
            period = f"• {period_start} - {period_end}"
            if current_mw is not None:
                period += f" ({current_mw} MW)"
            if current_price is not None:
                period += f" with a guaranteed acceptance price of £{current_price}/MWh"
            time_slots.append(period)
    
    # Add the date header once
    time_slots.append(f"\n**{most_recent_date}**")
    
    for _, row in df_recent.iterrows():
        mw = row.get('Service Requirement MW')
        price = row.get('Guaranteed Acceptance Price GBP per MWh')
        
        # If MW or price changes, start a new period
        if mw != current_mw or price != current_price:
            add_period()  # Close previous period
            period_start = row['From']
            current_mw = mw
            current_price = price
        
        period_end = row['To']
    
    # Add the last period
    add_period()
    
    return "\n".join(time_slots)

def convert_to_serializable(obj):
    """Convert pandas/numpy types to JSON serializable types"""
    if pd.isna(obj):
        return None
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif hasattr(obj, 'item'):  # This catches numpy types like int64
        return obj.item()
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(v) for v in obj]
    return obj

def check_octopus_bids():
    # SQL query to filter for Octopus Energy in the participant bids list
    sql_query = f'''
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
        
        # Add debug logging
        print(f"Debug: API URL: {response.url}")
        print(f"Debug: Response Status: {response.status_code}")
        print(f"Debug: Response Headers: {dict(response.headers)}")
        
        if response.status_code == 409:
            print(f"Debug: Response Body: {response.text}")
            print("Warning: API Conflict error. This might be due to rate limiting or API changes.")
            return
            
        response.raise_for_status()
        json_response = response.json()
        
        if not json_response.get('success'):
            print("API Error:", json_response.get('error', 'Unknown error'))
            return
            
        if 'result' not in json_response:
            print("Error: 'result' key not found in response")
            return
            
        data = json_response["result"]
        df = pd.DataFrame(data["records"])
        
        states = {
            "octopus_neso_status": {
                "state": "active" if not df.empty else "inactive",
                "attributes": {
                    "last_checked": datetime.now().isoformat(),
                    "entry_count": len(df) if not df.empty else 0,
                    "service_type": convert_to_serializable(df['Service Requirement Type'].iloc[0]) if not df.empty else None,
                    "dispatch_type": convert_to_serializable(df['Dispatch Type'].iloc[0]) if not df.empty else None,
                    "most_recent_date": convert_to_serializable(df['Delivery Date'].max()) if not df.empty else None
                }
            },
            "octopus_neso_details": {
                "state": format_time_slots(df) if not df.empty else "No entries found",
                "attributes": {
                    "raw_data": [{k: convert_to_serializable(v) for k, v in record.items()} 
                                for record in (df[df['Delivery Date'] == df['Delivery Date'].max()].to_dict('records') if not df.empty else [])]
                }
            }
        }
        
        # Save states for Home Assistant
        save_states(states)
        
        # Print a concise status update
        status = "🟢 Active" if not df.empty else "⚪ Inactive"
        print(f"Status: {status}")
        if not df.empty:
            print(f"Latest date: {df['Delivery Date'].max()}")
            print(f"Entries: {len(df)}")
                
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        states = {
            "octopus_neso_status": {
                "state": "error",
                "attributes": {
                    "last_checked": datetime.now().isoformat(),
                    "error": str(e)
                }
            }
        }
        save_states(states)
        raise

def check_utilization():
    # Now proceed with the original query
    sql_query = '''
        SELECT * 
        FROM "cc36fff5-5f6f-4fde-8932-c935d982ecd8" 
        WHERE "Registered DFS Participant" = 'OCTOPUS ENERGY LIMITED'
        ORDER BY "_id" DESC 
        LIMIT 1000
    '''
    params = {'sql': sql_query}

    try:
        response = requests.get('https://api.neso.energy/api/3/action/datastore_search_sql', 
                              params=parse.urlencode(params))
        
        # Add debug logging
        print(f"Debug: API URL: {response.url}")
        print(f"Debug: Response Status: {response.status_code}")
        print(f"Debug: Response Headers: {dict(response.headers)}")
        
        if response.status_code == 409:
            print(f"Debug: Response Body: {response.text}")
            print("Warning: API Conflict error. This might be due to rate limiting or API changes.")
            return
            
        response.raise_for_status()
        json_response = response.json()
        
        if not json_response.get('success'):
            print("API Error:", json_response.get('error', 'Unknown error'))
            return
        
        data = json_response["result"]
        df = pd.DataFrame(data["records"])
        
        if df.empty:
            print("⚪ No utilization data found")
            return
        
        # Sort by Delivery Date DESC to get most recent entries first
        df = df.sort_values('Delivery Date', ascending=False)
        
        # Get the most recent entry
        latest = df.iloc[0]
        status = "🟢 Accepted" if latest.get('Status', '').item() == 'ACCEPTED' else "🔴 Rejected"
        
        # Find highest accepted bid from most recent delivery date
        accepted_bids = df[df['Status'] == 'ACCEPTED']
        if not accepted_bids.empty:
            accepted_bids = accepted_bids[accepted_bids['Delivery Date'] == latest['Delivery Date']]
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
                "state": convert_to_serializable(latest.get('Delivery Date')),
                "attributes": {}
            },
            "octopus_neso_time_window": {
                "state": f"{convert_to_serializable(latest.get('From'))} - {convert_to_serializable(latest.get('To'))}",
                "attributes": {}
            },
            "octopus_neso_price": {
                "state": convert_to_serializable(latest.get('Utilisation Price GBP per MWh')),
                "attributes": {}
            },
            "octopus_neso_volume": {
                "state": convert_to_serializable(latest.get('DFS Volume MW')),
                "attributes": {}
            },
            "octopus_neso_highest_accepted": {
                "state": convert_to_serializable(highest_accepted['Utilisation Price GBP per MWh']) if highest_accepted is not None else "No accepted bids",
                "attributes": {
                    "delivery_date": convert_to_serializable(highest_accepted['Delivery Date']) if highest_accepted is not None else None,
                    "time_from": convert_to_serializable(highest_accepted['From']) if highest_accepted is not None else None,
                    "time_to": convert_to_serializable(highest_accepted['To']) if highest_accepted is not None else None,
                    "volume": convert_to_serializable(highest_accepted['DFS Volume MW']) if highest_accepted is not None else None,
                    "last_update": datetime.now().isoformat()
                }
            }
        }
        
        # Save states for Home Assistant
        save_states(states)
        
        # Print concise status
        print(f"Status: {status}")
        print(f"Delivery Date: {latest.get('Delivery Date')}")
        print(f"Time: {latest.get('From')} - {latest.get('To')}")
        print(f"Price: £{latest.get('Utilisation Price GBP per MWh')}/MWh")
        print(f"Volume: {latest.get('DFS Volume MW')} MW")
        
        # Print highest accepted bid info
        print("\n📈 Highest Accepted Bid:")
        if highest_accepted is not None:
            print(f"Price: £{highest_accepted['Utilisation Price GBP per MWh']}/MWh")
            print(f"Date: {highest_accepted['Delivery Date']}")
            print(f"Time: {highest_accepted['From']} - {highest_accepted['To']}")
            print(f"Volume: {highest_accepted['DFS Volume MW']} MW")
        else:
            print("No accepted bids found")
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        states = {
            "octopus_neso_utilization": {
                "state": "error",
                "attributes": {
                    "last_checked": datetime.now().isoformat(),
                    "error": str(e)
                }
            }
        }
        save_states(states)
        raise

def main_loop():
    print("🔄 Starting NESO Octopus Watch")
    config = get_config()
    CHECK_INTERVAL = config.get("scan_interval", 300)
    print(f"⏱️  Check interval: {CHECK_INTERVAL} seconds")
    
    # Check immediately on startup for most recent data
    try:
        check_octopus_bids()
        check_utilization()
    except Exception as e:
        print(f"❌ Error during initial check: {e}", file=sys.stderr)
    
    while True:
        try:
            check_octopus_bids()
            check_utilization()
        except Exception as e:
            print(f"❌ Error in main loop: {e}", file=sys.stderr)
        
        # Sleep until next check
        next_check = datetime.now() + timedelta(seconds=CHECK_INTERVAL)
        print(f"⏰ Next check at: {next_check.strftime('%H:%M:%S')}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main_loop()
