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

# Add state file path for Home Assistant
STATES_PATH = Path("/data/states.json")

# Get check interval from environment or use default (5 minutes)
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))

def save_states(states):
    """Save states for Home Assistant to read"""
    STATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATES_PATH, 'w') as f:
        json.dump(states, f)

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

def check_octopus_bids():
    # SQL query to filter for Octopus Energy in the participant bids list
    sql_query = f'''
        SELECT COUNT(*) OVER () AS _count, * 
        FROM "f5605e2b-b677-424c-8df7-d0ce4ee03cef" 
        WHERE "Participant Bids Eligible" LIKE '%OCTOPUS ENERGY LIMITED%'
        ORDER BY "_id" ASC
    '''
    params = {'sql': sql_query}

    try:
        response = requests.get('https://api.neso.energy/api/3/action/datastore_search_sql', 
                              params=parse.urlencode(params))
        
        # Only log status if there's an issue
        if response.status_code != 200:
            print(f"Warning: Unexpected response status: {response.status_code}")
        
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
                    "service_type": df['Service Requirement Type'].iloc[0] if not df.empty else None,
                    "dispatch_type": df['Dispatch Type'].iloc[0] if not df.empty else None,
                    "most_recent_date": df['Delivery Date'].max() if not df.empty else None
                }
            },
            "octopus_neso_details": {
                "state": format_time_slots(df) if not df.empty else "No entries found",
                "attributes": {
                    "raw_data": df[df['Delivery Date'] == df['Delivery Date'].max()].to_dict('records') if not df.empty else []
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

def format_utilization_data(df):
    """Format utilization data for Octopus Energy entries"""
    # Filter for Octopus Energy entries
    octopus_df = df[df['Provider Name'] == 'OCTOPUS ENERGY LIMITED']
    
    if octopus_df.empty:
        return "No Octopus Energy utilization data found"
    
    # Sort by date/time if available
    if 'Settlement Date' in octopus_df.columns:
        octopus_df = octopus_df.sort_values('Settlement Date', ascending=False)
    
    utilization_entries = []
    
    for _, row in octopus_df.iterrows():
        entry = f"\n**Settlement Date: {row.get('Settlement Date', 'N/A')}**"
        entry += f"\nSettlement Period: {row.get('Settlement Period', 'N/A')}"
        entry += f"\nStatus: {row.get('Status', 'N/A')}"
        entry += f"\nBid Price: £{row.get('Bid Price', 'N/A')}/MWh"
        entry += f"\nBid Size: {row.get('Bid Size', 'N/A')} MW"
        entry += f"\nAccepted Volume: {row.get('Accepted Volume', 'N/A')} MW"
        utilization_entries.append(entry)
    
    return "\n---".join(utilization_entries)

def check_utilization():
    sql_query = '''
        SELECT * 
        FROM "cc36fff5-5f6f-4fde-8932-c935d982ecd8" 
        WHERE "Provider Name" = 'OCTOPUS ENERGY LIMITED'
        ORDER BY "_id" DESC 
        LIMIT 100
    '''
    params = {'sql': sql_query}

    try:
        response = requests.get('https://api.neso.energy/api/3/action/datastore_search_sql', 
                              params=parse.urlencode(params))
        
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
        
        # Get the most recent entry
        latest = df.iloc[0]
        status = "🟢 Accepted" if latest.get('Status') == 'ACCEPTED' else "🔴 Rejected"
        
        states = {
            "octopus_neso_utilization": {
                "state": latest.get('Status', 'UNKNOWN'),
                "attributes": {
                    "last_checked": datetime.now().isoformat(),
                    "latest_settlement_date": latest.get('Settlement Date'),
                    "latest_settlement_period": latest.get('Settlement Period'),
                    "latest_bid_price": latest.get('Bid Price'),
                    "latest_bid_size": latest.get('Bid Size'),
                    "latest_accepted_volume": latest.get('Accepted Volume')
                }
            },
            "octopus_neso_utilization_details": {
                "state": format_utilization_data(df),
                "attributes": {
                    "raw_data": df.to_dict('records')
                }
            }
        }
        
        # Save states for Home Assistant
        save_states(states)
        
        # Print concise status
        print(f"Status: {status}")
        print(f"Settlement Date: {latest.get('Settlement Date')}")
        print(f"Bid Price: £{latest.get('Bid Price')}/MWh")
        print(f"Bid Size: {latest.get('Bid Size')} MW")
        print(f"Accepted Volume: {latest.get('Accepted Volume')} MW")
        
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
    print(f"⏱️  Check interval: {CHECK_INTERVAL} seconds")
    
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