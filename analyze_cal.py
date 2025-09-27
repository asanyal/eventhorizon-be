#!/usr/bin/env python3

import sys
import subprocess
import os
import json
import datetime
from dateutil import parser
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import googleapiclient.discovery
import pytz
from colorama import init, Fore, Style
import pandas as pd
from tabulate import tabulate
import argparse

# Initialize colorama
init()

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
INTERNAL_EMAIL_DOMAIN = "galileo.ai"
EXCLUDED_EMAIL_DOMAINS = ["@resource.calendar.google.com"]

def check_dependencies():
    """Check if all required packages are installed"""
    required_packages = [
        'google-auth',
        'google-auth-oauthlib',
        'google-auth-httplib2',
        'google-api-python-client',
        'pytz',
        'sortedcontainers',
        'colorama',
        'pandas',
        'tabulate',
        'python-dateutil'
    ]
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    deps_file = os.path.join(script_dir, '.deps_checked')
    
    # Check if we've already verified dependencies
    if os.path.exists(deps_file):
        with open(deps_file, 'r') as f:
            checked_packages = json.load(f)
            if set(checked_packages) == set(required_packages):
                return
    
    # If we get here, we need to check dependencies
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Installing missing packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + missing_packages)
        print("All required packages have been installed.")
    
    # Save the list of packages we checked
    with open(deps_file, 'w') as f:
        json.dump(required_packages, f)

def print_status(message, color=Fore.GREEN):
    """Print a status message with color"""
    print(f"{color}{message}{Style.RESET_ALL}")

def login():
    """Handle Google Calendar API authentication"""
    creds = None
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_json = os.path.join(script_dir, "token.json")
    api_credentials_json = os.path.join(script_dir, "credentials.json")
    
    if os.path.exists(token_json):
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(api_credentials_json, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_json, 'w') as token:
            token.write(creds.to_json())
    return creds

def format_date(d):
    """Format date to a readable format"""
    datetime_obj = parser.isoparse(d)
    return datetime_obj.strftime("%b %-d")

def get_start_end_times(date1_str, date2_str):
    """Get formatted start and end times in Pacific timezone"""
    date1 = parser.isoparse(date1_str)
    date2 = parser.isoparse(date2_str)
    pacific_tz = pytz.timezone('US/Pacific')
    
    date1_pacific = date1.astimezone(pacific_tz)
    date2_pacific = date2.astimezone(pacific_tz)
    
    start_time = date1_pacific.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
    end_time = date2_pacific.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
    
    return start_time, end_time

def calculate_duration_in_minutes(date1_str, date2_str):
    """Calculate duration between two dates in minutes"""
    date1 = parser.isoparse(date1_str)
    date2 = parser.isoparse(date2_str)
    duration = abs(date2 - date1)
    total_minutes = duration.total_seconds() // 60
    return f"{int(total_minutes)} min"

def get_time_until_event(event_time):
    """Calculate time until event in a human-readable format"""
    now = datetime.datetime.now(pytz.UTC)
    event_datetime = parser.isoparse(event_time)
    time_diff = event_datetime - now
    
    days = time_diff.days
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    
    # Calculate total hours for color determination
    total_hours = days * 24 + hours + (minutes / 60)
    
    # Choose color based on time until event
    color = Fore.RED if total_hours < 2 else Fore.YELLOW
    
    if days > 0:
        return f"{color}In {days}d {hours}h{Style.RESET_ALL}"
    elif hours > 0:
        return f"{color}In {hours}h {minutes}m{Style.RESET_ALL}"
    else:
        return f"{color}In {minutes}m{Style.RESET_ALL}"

def analyze_meeting_types(events):
    """Analyze meeting types and their distribution"""
    meeting_types = {
        '1:1': 0,
        'Group': 0,
        'Standup': 0,
        'Interview': 0,
        'Other': 0
    }
    
    for event in events:
        summary = event['Event'].lower()
        if '1:1' in summary or '1-1' in summary:
            meeting_types['1:1'] += 1
        elif 'standup' in summary:
            meeting_types['Standup'] += 1
        elif 'interview' in summary:
            meeting_types['Interview'] += 1
        elif any(word in summary for word in ['meeting', 'sync', 'discussion', 'review']):
            meeting_types['Group'] += 1
        else:
            meeting_types['Other'] += 1
    
    return meeting_types

def analyze_time_distribution(events):
    """Analyze time distribution of meetings"""
    time_slots = {
        'Morning (8-12)': 0,
        'Afternoon (12-5)': 0,
        'Evening (5-8)': 0
    }
    
    for event in events:
        # Extract time from the colored string in the Date column
        date_str = event['Date']
        # Find the time part between parentheses
        start_idx = date_str.find('(') + 1
        end_idx = date_str.find(')')
        if start_idx > 0 and end_idx > start_idx:
            time_str = date_str[start_idx:end_idx]
            # Remove color codes to get just the time
            time_str = time_str.replace(Fore.MAGENTA, '').replace(Style.RESET_ALL, '')
            hour = int(time_str.split(':')[0])
            is_pm = 'PM' in time_str
            
            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
            
            if 8 <= hour < 12:
                time_slots['Morning (8-12)'] += 1
            elif 12 <= hour < 17:
                time_slots['Afternoon (12-5)'] += 1
            elif 17 <= hour < 20:
                time_slots['Evening (5-8)'] += 1
            elif hour < 8:  # Early morning meetings
                time_slots['Morning (8-12)'] += 1
    
    return time_slots

def find_free_blocks(events):
    """Find free time blocks between meetings"""
    if not events:
        return []
    
    # Convert events to datetime objects for easier comparison
    event_times = []
    for event in events:
        # Extract time from the colored string in the Date column
        date_str = event['Date']
        # Find the time part between parentheses
        start_idx = date_str.find('(') + 1
        end_idx = date_str.find(')')
        if start_idx > 0 and end_idx > start_idx:
            time_str = date_str[start_idx:end_idx]
            # Remove color codes to get just the time
            time_str = time_str.replace(Fore.MAGENTA, '').replace(Style.RESET_ALL, '')
            # Convert to datetime object
            hour, minute = map(int, time_str.replace(' AM', '').replace(' PM', '').split(':'))
            if 'PM' in time_str and hour != 12:
                hour += 12
            elif 'AM' in time_str and hour == 12:
                hour = 0
            
            # Get duration in minutes
            duration_str = event['Duration'].split(Fore.CYAN)[1].split(Style.RESET_ALL)[0]
            duration_minutes = int(duration_str.split()[0])
            
            # Get the date from the event (extract just the date part before parentheses)
            date_part = date_str.split(' (')[0]
            # Parse the date (format: "Jun 17") with current year to avoid deprecation warning
            current_year = datetime.datetime.now().year
            date_obj = datetime.datetime.strptime(f"{date_part} {current_year}", "%b %d %Y")
            
            event_times.append({
                'date': date_obj,
                'start': datetime.time(hour, minute),
                'duration': duration_minutes
            })
    
    # Sort events by date and start time
    event_times.sort(key=lambda x: (x['date'], x['start']))
    
    # Group events by date
    events_by_date = {}
    for event in event_times:
        date_key = event['date'].strftime("%b %d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)
    
    # Find free blocks for each date
    free_blocks = []
    for date_key, date_events in events_by_date.items():
        # Start at 6 AM for each day
        current_time = datetime.time(6, 0)
        
        # If there are events for this day, check for free block before first event
        if date_events:
            first_event = date_events[0]
            if current_time < first_event['start']:
                # Calculate duration in minutes
                duration_minutes = (first_event['start'].hour * 60 + first_event['start'].minute) - (current_time.hour * 60 + current_time.minute)
                if duration_minutes >= 30:  # Only show blocks of 30 minutes or more
                    hours = duration_minutes // 60
                    minutes = duration_minutes % 60
                    duration_str = f"{hours}h" if hours > 0 else ""
                    duration_str += f" {minutes}min" if minutes > 0 else ""
                    duration_str = duration_str.strip()
                    
                    time_str = current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ')
                    free_blocks.append({
                        'date': date_key,
                        'duration': duration_str,
                        'time': time_str
                    })
            
            # Update current time to end of first event
            end_minutes = (first_event['start'].hour * 60 + first_event['start'].minute + first_event['duration'])
            # Handle hours that exceed 23 by wrapping to next day
            end_hour = end_minutes // 60
            end_minute = end_minutes % 60
            
            # If end time goes past midnight, cap it at 23:59
            if end_hour >= 24:
                current_time = datetime.time(23, 59)
            else:
                current_time = datetime.time(end_hour, end_minute)
            
            # Check for free blocks between remaining events
            for event in date_events[1:]:
                if current_time < event['start']:
                    # Calculate duration in minutes
                    duration_minutes = (event['start'].hour * 60 + event['start'].minute) - (current_time.hour * 60 + current_time.minute)
                    if duration_minutes >= 30:  # Only show blocks of 30 minutes or more
                        hours = duration_minutes // 60
                        minutes = duration_minutes % 60
                        duration_str = f"{hours}h" if hours > 0 else ""
                        duration_str += f" {minutes}min" if minutes > 0 else ""
                        duration_str = duration_str.strip()
                        
                        time_str = current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ')
                        free_blocks.append({
                            'date': date_key,
                            'duration': duration_str,
                            'time': time_str
                        })
                
                # Update current time to end of this event
                end_minutes = (event['start'].hour * 60 + event['start'].minute + event['duration'])
                # Handle hours that exceed 23 by wrapping to next day
                end_hour = end_minutes // 60
                end_minute = end_minutes % 60
                
                # If end time goes past midnight, cap it at 23:59
                if end_hour >= 24:
                    current_time = datetime.time(23, 59)
                else:
                    current_time = datetime.time(end_hour, end_minute)
        
        # Check for free block after last event until 6 PM
        if current_time < datetime.time(18, 0):
            duration_minutes = (18 * 60) - (current_time.hour * 60 + current_time.minute)
            if duration_minutes >= 30:
                hours = duration_minutes // 60
                minutes = duration_minutes % 60
                duration_str = f"{hours}h" if hours > 0 else ""
                duration_str += f" {minutes}min" if minutes > 0 else ""
                duration_str = duration_str.strip()
                
                time_str = current_time.strftime("%I:%M %p").lstrip('0').replace(' 0', ' ')
                free_blocks.append({
                    'date': date_key,
                    'duration': duration_str,
                    'time': time_str
                })
    
    return free_blocks

def print_analytics(events, time_range):
    """Print analytics summary"""
    if not events:
        return
    
    total_events = len(events)
    meeting_types = analyze_meeting_types(events)
    time_dist = analyze_time_distribution(events)
    free_blocks = find_free_blocks(events)
    
    # Filter free blocks based on time range
    if time_range.lower() not in ['today', 'tomorrow', 'this week', 'next week']:
        free_blocks = []
    
    # Prepare meeting types data
    meeting_types_data = []
    for meeting_type, count in meeting_types.items():
        if count > 0:
            percentage = (count / total_events) * 100
            meeting_types_data.append([f"• {meeting_type}", f"{count} ({percentage:.1f}%)"])
    
    # Prepare time distribution data
    time_dist_data = []
    for time_slot, count in time_dist.items():
        if count > 0:
            percentage = (count / total_events) * 100
            time_dist_data.append([f"• {time_slot}", f"{count} ({percentage:.1f}%)"])
    
    # Prepare free blocks data
    free_blocks_data = []
    for block in free_blocks:
        free_blocks_data.append([
            f"• {Fore.GREEN}{block['duration']}{Style.RESET_ALL}",
            f"(at {Fore.GREEN}{block['time']}{Style.RESET_ALL} on {Fore.GREEN}{block['date']}{Style.RESET_ALL})"
        ])
    
    # Create the analytics table
    print_status("\n📊 Summary", Fore.CYAN)
    print()
    
    analytics_table = [
        ["Total Events", "Meeting Types", "Time Distribution", "Free Blocks"],
        ["", "", "", ""],  # Empty row for spacing
        [f"{total_events}", "", "", ""]
    ]
    
    # Add meeting types, time distribution, and free blocks
    max_rows = max(len(meeting_types_data), len(time_dist_data), len(free_blocks_data))
    for i in range(max_rows):
        row = ["", "", "", ""]
        if i < len(meeting_types_data):
            row[1] = " ".join(meeting_types_data[i])
        if i < len(time_dist_data):
            row[2] = " ".join(time_dist_data[i])
        if i < len(free_blocks_data):
            row[3] = " ".join(free_blocks_data[i])
        analytics_table.append(row)
    
    # Print the analytics table
    print(tabulate(analytics_table, tablefmt='simple'))
    print()  # Add a blank line before the main table

def analyze_calendar(start_date, end_date, search_term=None):
    """Fetch and analyze calendar events for the given date range"""
    creds = login()
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)
    
    # Get current time in UTC
    now = datetime.datetime.now(pytz.UTC)
    
    events_result = service.events().list(
        calendarId='primary',
        timeMin=start_date,
        timeMax=end_date,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    if not events:
        print_status("No upcoming events found.", Fore.YELLOW)
        return []
    
    formatted_events = []
    for event in events:
        if event['summary'] == "Block":
            continue
            
        if 'dateTime' in event['start']:
            event_start = parser.isoparse(event['start']['dateTime'])
            # Skip past events
            if event_start < now:
                continue
            
            # Skip if search term is provided and event doesn't match
            if search_term and search_term.lower() not in event['summary'].lower():
                continue
                
            event_date = format_date(event['start'].get('dateTime'))
            start_time, end_time = get_start_end_times(event['start']['dateTime'], event['end']['dateTime'])
            duration = calculate_duration_in_minutes(event['start']['dateTime'], event['end']['dateTime'])
            time_until = get_time_until_event(event['start']['dateTime'])
            
            formatted_events.append({
                'Date': f"{event_date} ({Fore.MAGENTA}{start_time}{Style.RESET_ALL})",
                'Interval': time_until,  # time_until now includes color
                'Event': event['summary'],
                'Duration': f"{Fore.CYAN}{duration}{Style.RESET_ALL}"
            })
    
    return formatted_events

def get_date_range(time_range):
    """Get start and end dates based on the time range argument"""
    now = datetime.datetime.now()
    pacific_tz = pytz.timezone('US/Pacific')
    now = now.astimezone(pacific_tz)
    
    if time_range == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_range == "tomorrow":
        start_date = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now + datetime.timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_range == "day after":
        start_date = (now + datetime.timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now + datetime.timedelta(days=2)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_range == "this week":
        # If today is Sunday, show next week instead
        if now.weekday() == 6:  # Sunday is 6
            start_date = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)  # Monday
            end_date = (now + datetime.timedelta(days=7)).replace(hour=23, minute=59, second=59, microsecond=999999)  # Next Sunday
        else:
            # Get Monday of current week
            start_date = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = (start_date + datetime.timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_range == "next week":
        # Get Monday of next week
        start_date = (now + datetime.timedelta(days=(7-now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (start_date + datetime.timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_range == "this month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Get last day of current month
        if now.month == 12:
            end_date = now.replace(year=now.year+1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            end_date = now.replace(month=now.month+1, day=1) - datetime.timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_range == "next month":
        if now.month == 12:
            start_date = now.replace(year=now.year+1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(year=now.year+1, month=2, day=1) - datetime.timedelta(days=1)
        else:
            start_date = now.replace(month=now.month+1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(month=now.month+2, day=1) - datetime.timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        # Try to parse as a month name
        try:
            month_num = datetime.datetime.strptime(time_range, "%B").month
            year = now.year
            if month_num < now.month:
                year += 1
            start_date = datetime.datetime(year, month_num, 1, tzinfo=pacific_tz)
            if month_num == 12:
                end_date = datetime.datetime(year+1, 1, 1, tzinfo=pacific_tz) - datetime.timedelta(days=1)
            else:
                end_date = datetime.datetime(year, month_num+1, 1, tzinfo=pacific_tz) - datetime.timedelta(days=1)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            print_status(f"Invalid time range: {time_range}", Fore.RED)
            sys.exit(1)
    
    return start_date.isoformat(), end_date.isoformat()

def main():
    parser = argparse.ArgumentParser(description='Analyze Google Calendar events.')
    parser.add_argument('time_range', help='Time range to analyze (today, tomorrow, day after, this week, next week, this month, next month, or month name)')
    parser.add_argument('--search', '-s', help='Search term to filter events', default=None)
    
    args = parser.parse_args()
    time_range = args.time_range.lower()
    start_date, end_date = get_date_range(time_range)
    
    print_status(f"Fetching calendar events for {time_range}...", Fore.YELLOW)
    if args.search:
        print_status(f"Filtering events containing: {args.search}", Fore.YELLOW)
    
    events = analyze_calendar(start_date, end_date, args.search)
    
    if events:
        df = pd.DataFrame(events)
        print_analytics(events, time_range)
        # Reorder columns (Time is now combined with Date)
        df = df[['Date', 'Interval', 'Event', 'Duration']]
        print(tabulate(df, headers='keys', tablefmt='simple', showindex=False))
    else:
        print_status("No events found for the specified time range.", Fore.YELLOW)

if __name__ == "__main__":
    check_dependencies()
    main() 
