import os
import json
import datetime
from pathlib import Path

from selit.workdir import get_app_data_dir


def get_history_dir():
    """Get or create the history directory for logs."""
    history_dir = os.path.join(get_app_data_dir(), 'history')
    os.makedirs(history_dir, exist_ok=True)
    return history_dir

def get_current_day_log_file():
    """Get the log file path for the current day."""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    history_dir = get_history_dir()
    return os.path.join(history_dir, f'selit_{today}.log')

def log_call(window_info, input_text, output_text, trigger_word):
    """
    Log a call to the history file.
    
    Args:
        window_info (dict): Information about the window where the call was made
        input_text (str): The original input text
        output_text (str): The generated output text
        trigger_word (str): The magic word/trigger used
    """
    timestamp = datetime.datetime.now().isoformat()
    
    # Create a log entry
    log_entry = {
        'timestamp': timestamp,
        'window': {
            'title': window_info.get('title', 'Unknown'),
            'process_name': window_info.get('process_name', 'Unknown')
        },
        'trigger_word': trigger_word,
        'input': input_text,
        'output': output_text
    }
    
    log_file = get_current_day_log_file()
    
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"Error logging call history: {str(e)}")

def get_call_history(days=1):
    """
    Get call history for the specified number of days.
    
    Args:
        days (int): Number of days to retrieve (default: 1 - current day only)
        
    Returns:
        list: List of log entries, sorted by timestamp (newest first)
    """
    history = []
    history_dir = get_history_dir()
    
    # Calculate date range
    today = datetime.datetime.now().date()
    dates = [today - datetime.timedelta(days=i) for i in range(days)]
    
    # Collect logs for each date
    for date in dates:
        date_str = date.strftime('%Y-%m-%d')
        log_file = os.path.join(history_dir, f'selit_{date_str}.log')
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            # Parse timestamp for sorting
                            entry['timestamp_parsed'] = datetime.datetime.fromisoformat(entry['timestamp'])
                            history.append(entry)
                        except json.JSONDecodeError:
                            # Skip invalid lines
                            continue
            except Exception as e:
                print(f"Error reading history from {log_file}: {str(e)}")
    
    # Sort by timestamp (newest first)
    history.sort(key=lambda x: x['timestamp_parsed'], reverse=True)
    return history

def generate_day_summary(date=None):
    """
    Generate a summary of all interactions for a specific day.
    
    Args:
        date (datetime.date, optional): The date to generate summary for. Defaults to today.
        
    Returns:
        dict: Summary data including total interactions, most used apps, and other statistics
    """
    if date is None:
        date = datetime.datetime.now().date()
    
    date_str = date.strftime('%Y-%m-%d')
    log_file = os.path.join(get_history_dir(), f'selit_{date_str}.log')
    
    if not os.path.exists(log_file):
        return {
            "date": date_str,
            "total_interactions": 0,
            "apps": {},
            "average_input_length": 0,
            "average_output_length": 0,
            "busiest_hour": None,
            "hour_distribution": {}
        }
    
    interactions = []
    apps = {}
    total_input_length = 0
    total_output_length = 0
    hour_distribution = {}
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    interactions.append(entry)
                    
                    # Count app usage
                    app_name = entry['window']['process_name']
                    if app_name in apps:
                        apps[app_name] += 1
                    else:
                        apps[app_name] = 1
                    
                    # Calculate input/output lengths
                    input_length = len(entry['input'])
                    output_length = len(entry['output'])
                    total_input_length += input_length
                    total_output_length += output_length
                    
                    # Track activity by hour
                    timestamp = datetime.datetime.fromisoformat(entry['timestamp'])
                    hour = timestamp.hour
                    if hour in hour_distribution:
                        hour_distribution[hour] += 1
                    else:
                        hour_distribution[hour] = 1
                        
                except json.JSONDecodeError:
                    # Skip invalid lines
                    continue
    except Exception as e:
        print(f"Error reading history from {log_file}: {str(e)}")
    
    total_interactions = len(interactions)
    
    # Calculate averages
    avg_input_length = round(total_input_length / total_interactions) if total_interactions > 0 else 0
    avg_output_length = round(total_output_length / total_interactions) if total_interactions > 0 else 0
    
    # Find busiest hour
    busiest_hour = max(hour_distribution.items(), key=lambda x: x[1])[0] if hour_distribution else None
    
    # Sort apps by usage
    sorted_apps = {k: v for k, v in sorted(apps.items(), key=lambda item: item[1], reverse=True)}
    
    return {
        "date": date_str,
        "total_interactions": total_interactions,
        "apps": sorted_apps,
        "average_input_length": avg_input_length,
        "average_output_length": avg_output_length,
        "busiest_hour": busiest_hour,
        "hour_distribution": dict(sorted(hour_distribution.items()))
    }
