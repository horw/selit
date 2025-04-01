import subprocess
import platform

def notification(title="SeLit", message="Text generated successfully"):
    """
    Display a desktop notification.
    
    Args:
        title (str): The notification title
        message (str): The notification message
    """
    system = platform.system()
    
    if system == "Linux":
        try:
            # Try using notify-send (common in most Linux distributions)
            subprocess.Popen(['notify-send', title, message])
        except FileNotFoundError:
            try:
                # Try using zenity as a fallback
                subprocess.Popen(['zenity', '--notification', '--text', f"{title}: {message}"])
            except FileNotFoundError:
                # If both methods fail, just print to console
                print(f"Desktop Notification: {title} - {message}")
    elif system == "Darwin":  # macOS
        # Placeholder for macOS notification (if needed in the future)
        # Could use osascript -e 'display notification "message" with title "title"'
        print(f"Desktop Notification: {title} - {message}")
    elif system == "Windows":
        # Placeholder for Windows notification (if needed in the future)
        # Could use Windows toast notifications
        print(f"Desktop Notification: {title} - {message}")
    else:
        # Fallback for unsupported systems
        print(f"Desktop Notification: {title} - {message}")
