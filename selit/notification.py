import subprocess
import platform
import os
import threading

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
        try:
            from win10toast import ToastNotifier
            
            # Create toaster and show notification in a non-blocking way
            def show_toast():
                toaster = ToastNotifier()
                toaster.show_toast(
                    title,
                    message,
                    duration=5,
                    threaded=True
                )
            
            # Run in a separate thread to prevent blocking
            threading.Thread(target=show_toast, daemon=True).start()
            
        except Exception as e:
            # Fallback if something goes wrong with the Windows notification
            print(f"Desktop Notification: {title} - {message}")
            print(f"Error displaying Windows notification: {e}")
    else:
        # Fallback for unsupported systems
        print(f"Desktop Notification: {title} - {message}")
