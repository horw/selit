import os
import platform
import subprocess
import psutil

def get_window_info(get_active_only=False):
    """
    Get window information using platform-specific methods.
    
    Args:
        get_active_only (bool): If True, return only the active window. If False, return all windows.
    
    Returns:
        If get_active_only is True: A dictionary with window info or None if no active window found.
        If get_active_only is False: A list of dictionaries with window info.
    """
    if platform.system() == 'Windows':
        # Import here to avoid issues on non-Windows platforms
        import win32gui
        import win32process
        
        if get_active_only:
            # Windows implementation for active window
            try:
                hwnd = win32gui.GetForegroundWindow()
                _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                window_title = win32gui.GetWindowText(hwnd)
                
                try:
                    process = psutil.Process(process_id)
                    process_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = "Unknown"
                
                return {
                    "hwnd": hwnd,
                    "title": window_title,
                    "process_id": process_id,
                    "process_name": process_name,
                }
            except Exception as e:
                print(f"Error getting active window: {e}")
                return None
        else:
            # Get all windows
            windows = []
            
            def enum_windows_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    try:
                        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                        process = psutil.Process(process_id)
                        process_name = process.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        process_name = "Unknown"
                    
                    if window_title and window_title not in [w["title"] for w in results]:
                        results.append({
                            "hwnd": hwnd,
                            "title": window_title,
                            "process_id": process_id,
                            "process_name": process_name
                        })
                return True
            
            win32gui.EnumWindows(enum_windows_callback, windows)
            return windows
            
    elif platform.system() == 'Linux':
        if get_active_only:
            # Try to use xdotool to get the active window (more reliable than wmctrl for active window)
            active_window = _get_active_window_with_xdotool()
            if active_window:
                return active_window
                
            # Try with xprop as an alternative
            active_window = _get_active_window_with_xprop()
            if active_window:
                return active_window
            
            # Try the combined wmctrl approach as a last resort
            active_window = _get_active_window_with_wmctrl()
            if active_window:
                return active_window
                
            # Fallback to the most active process
            return _get_most_active_process()
        else:
            # Get all windows
            windows = _get_all_windows_with_wmctrl()
            
            # If wmctrl didn't work, try xdotool
            if not windows:
                windows = _get_all_windows_with_xdotool()
                
            # If still no windows, use process-based fallback
            if not windows:
                windows = _get_all_processes_as_windows()
                
            return windows
    else:
        # Unsupported platform
        if get_active_only:
            return {
                "hwnd": None,
                "title": f"Unsupported platform: {platform.system()}",
                "process_id": None,
                "process_name": "Unknown",
            }
        else:
            return [{
                "hwnd": 0,
                "title": f"Unsupported platform: {platform.system()}",
                "process_name": "Unknown"
            }]

def _get_active_window_with_xprop():
    """
    Try to get the active window info using xprop.
    Returns window info dict or None if failed.
    """
    try:
        # Check if xprop is installed
        xprop_check = subprocess.run(
            ["which", "xprop"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if xprop_check.returncode == 0:
            # Get active window
            xprop_output = subprocess.run(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if xprop_output.returncode == 0 and xprop_output.stdout:
                # Parse window ID (format: _NET_ACTIVE_WINDOW(WINDOW): window id # 0x...)
                window_id_match = xprop_output.stdout.strip().split()[-1]
                if window_id_match and window_id_match != "0x0":
                    # Get window name
                    name_output = subprocess.run(
                        ["xprop", "-id", window_id_match, "WM_NAME"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # Get window PID
                    pid_output = subprocess.run(
                        ["xprop", "-id", window_id_match, "_NET_WM_PID"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    window_title = "Unknown"
                    pid = None
                    
                    if name_output.returncode == 0 and "WM_NAME" in name_output.stdout:
                        # Format: WM_NAME(STRING) = "Window Title"
                        title_parts = name_output.stdout.split("=", 1)
                        if len(title_parts) > 1:
                            window_title = title_parts[1].strip().strip('"')
                    
                    if pid_output.returncode == 0 and "_NET_WM_PID" in pid_output.stdout:
                        # Format: _NET_WM_PID(CARDINAL) = 12345
                        pid_parts = pid_output.stdout.split("=", 1)
                        if len(pid_parts) > 1:
                            try:
                                pid = int(pid_parts[1].strip())
                            except ValueError:
                                pid = None
                    
                    if pid:
                        try:
                            process = psutil.Process(pid)
                            process_name = process.name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            process_name = "Unknown"
                    else:
                        process_name = "Unknown"
                    
                    return {
                        "hwnd": window_id_match,
                        "title": window_title,
                        "process_id": pid,
                        "process_name": process_name,
                    }
    except Exception as e:
        print(f"Error using xprop: {e}")
    
    return None

def _get_active_window_with_wmctrl():
    """
    Try to get the active window info using wmctrl.
    Returns window info dict or None if failed.
    """
    try:
        # Check if wmctrl is installed
        wmctrl_check = subprocess.run(
            ["which", "wmctrl"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if wmctrl_check.returncode == 0:
            # First, get window ID with xprop if available
            active_window_id = None
            
            try:
                xprop_output = subprocess.run(
                    ["xprop", "-root", "_NET_ACTIVE_WINDOW"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if xprop_output.returncode == 0 and xprop_output.stdout:
                    # Parse window ID (format: _NET_ACTIVE_WINDOW(WINDOW): window id # 0x...)
                    window_id_match = xprop_output.stdout.strip().split()[-1]
                    if window_id_match and window_id_match != "0x0":
                        active_window_id = window_id_match
            except:
                pass
                
            # List all windows to find the active one by ID or pick the first one
            wmctrl_output = subprocess.run(
                ["wmctrl", "-l", "-p"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if wmctrl_output.returncode == 0:
                lines = wmctrl_output.stdout.strip().split('\n')
                
                # First search for the active window by ID if we have it
                if active_window_id:
                    for line in lines:
                        if line.strip().startswith(active_window_id):
                            # Found the active window
                            parts = line.split(None, 4)
                            if len(parts) >= 5:
                                window_id = parts[0]
                                try:
                                    pid = int(parts[2])
                                    window_title = parts[4]
                                    
                                    try:
                                        process = psutil.Process(pid)
                                        process_name = process.name()
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        process_name = "Unknown"
                                        
                                    return {
                                        "hwnd": window_id,
                                        "title": window_title,
                                        "process_id": pid,
                                        "process_name": process_name,
                                    }
                                except (ValueError, IndexError):
                                    pass
                
                # If we couldn't find by ID or don't have an ID, just take the first visible window
                for line in lines:
                    if line.strip():
                        parts = line.split(None, 4)
                        if len(parts) >= 5:
                            window_id = parts[0]
                            try:
                                pid = int(parts[2])
                                window_title = parts[4]
                                
                                try:
                                    process = psutil.Process(pid)
                                    process_name = process.name()
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    process_name = "Unknown"
                                    
                                return {
                                    "hwnd": window_id,
                                    "title": window_title,
                                    "process_id": pid,
                                    "process_name": process_name,
                                }
                            except (ValueError, IndexError):
                                pass
    except Exception as e:
        print(f"Error using wmctrl: {e}")
    
    return None

def _get_active_window_with_xdotool():
    """
    Try to get the active window info using xdotool.
    Returns window info dict or None if failed.
    """
    try:
        # Check if xdotool is installed
        xdotool_check = subprocess.run(
            ["which", "xdotool"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if xdotool_check.returncode == 0:
            # Get active window ID
            window_id_output = subprocess.run(
                ["xdotool", "getactivewindow"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if window_id_output.returncode == 0:
                window_id = window_id_output.stdout.strip()
                
                # Get window title
                title_output = subprocess.run(
                    ["xdotool", "getwindowname", window_id], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Get window PID
                pid_output = subprocess.run(
                    ["xdotool", "getwindowpid", window_id], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if title_output.returncode == 0 and pid_output.returncode == 0:
                    window_title = title_output.stdout.strip()
                    pid = int(pid_output.stdout.strip())
                    
                    try:
                        process = psutil.Process(pid)
                        process_name = process.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        process_name = "Unknown"
                    
                    return {
                        "hwnd": window_id,
                        "title": window_title,
                        "process_id": pid,
                        "process_name": process_name,
                    }
    except Exception as e:
        print(f"Error using xdotool: {e}")
    
    return None

def _get_most_active_process():
    """
    Fallback method to get the most active process as a window.
    Returns window info dict or a fallback if none found.
    """
    try:
        processes = []
        
        # Get our own PID to exclude it
        current_pid = os.getpid()
        
        # Collect processes with their CPU times to find active ones
        for proc in psutil.process_iter(['pid', 'name', 'cpu_times']):
            if proc.info['pid'] != current_pid:
                try:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu_time': sum(proc.info['cpu_times']) if proc.info['cpu_times'] else 0
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        # Sort by CPU time (descending) to get most active processes first
        processes.sort(key=lambda p: p['cpu_time'], reverse=True)
        
        if processes:
            # Take the most active process
            active_proc = processes[0]
            pid = active_proc['pid']
            
            try:
                # Get more detailed info
                process = psutil.Process(pid)
                process_name = process.name()
                
                # Try to get command line for a better title
                try:
                    cmdline = process.cmdline()
                    cmd_str = ' '.join(cmdline[:2]) if len(cmdline) > 1 else cmdline[0] if cmdline else ""
                    window_title = f"{process_name}: {cmd_str[:40]}"
                except:
                    window_title = process_name
                    
                return {
                    "hwnd": pid,
                    "title": window_title,
                    "process_id": pid,
                    "process_name": process_name,
                }
            except:
                pass
    except Exception as e:
        print(f"Error getting most active process: {e}")
    
    # Fallback if nothing else works
    return {
        "hwnd": 0,
        "title": "Linux Session",
        "process_id": 0,
        "process_name": "Unknown",
    }

def _get_all_windows_with_wmctrl():
    """
    Get all windows using wmctrl.
    Returns a list of window info dicts or empty list if failed.
    """
    windows = []
    
    try:
        # Check if wmctrl is installed
        wmctrl_check = subprocess.run(
            ["which", "wmctrl"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if wmctrl_check.returncode == 0:
            # List all windows
            wmctrl_output = subprocess.run(
                ["wmctrl", "-l", "-p"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )

            if wmctrl_output.returncode == 0:
                lines = wmctrl_output.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        # Parse window info: format is typically "WINDOW_ID DESKTOP_ID PID HOSTNAME WINDOW_TITLE"
                        parts = line.split(None, 4)
                        if len(parts) >= 5:
                            window_id = parts[0]
                            try:
                                pid = int(parts[2])
                                window_title = parts[4]
                                
                                try:
                                    process = psutil.Process(pid)
                                    process_name = process.name()
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    process_name = "Unknown"
                                
                                if window_title and window_title not in [w["title"] for w in windows]:
                                    windows.append({
                                        "hwnd": window_id,
                                        "title": window_title,
                                        "process_id": pid,
                                        "process_name": process_name
                                    })
                            except (ValueError, IndexError):
                                pass
    except Exception as e:
        print(f"Error using wmctrl for listing windows: {e}")
    
    return windows

def _get_all_windows_with_xdotool():
    """
    Get all windows using xdotool.
    Returns a list of window info dicts or empty list if failed.
    """
    windows = []
    
    try:
        # Check if xdotool is installed
        xdotool_check = subprocess.run(
            ["which", "xdotool"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if xdotool_check.returncode == 0:
            # Get window list
            window_list_output = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--name", ""], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if window_list_output.returncode == 0 and window_list_output.stdout.strip():
                window_ids = window_list_output.stdout.strip().split('\n')
                
                for window_id in window_ids:
                    if not window_id.strip():
                        continue
                        
                    # Get window name/title
                    name_output = subprocess.run(
                        ["xdotool", "getwindowname", window_id], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # Try to get PID
                    try:
                        pid_output = subprocess.run(
                            ["xdotool", "getwindowpid", window_id], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        
                        window_title = name_output.stdout.strip() if name_output.returncode == 0 else "Unknown"
                        
                        if pid_output.returncode == 0:
                            pid = int(pid_output.stdout.strip())
                            try:
                                process = psutil.Process(pid)
                                process_name = process.name()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                process_name = "Unknown"
                        else:
                            pid = 0
                            process_name = "Unknown"
                        
                        if window_title and window_title not in [w["title"] for w in windows]:
                            windows.append({
                                "hwnd": window_id,
                                "title": window_title,
                                "process_id": pid,
                                "process_name": process_name
                            })
                    except:
                        pass
    except Exception as e:
        print(f"Error using xdotool for window listing: {e}")
    
    return windows

def _get_all_processes_as_windows():
    """
    Fallback method to get processes as windows.
    Returns a list of process info dicts as window info.
    """
    windows = []
    
    try:
        # Skip our own process
        current_pid = os.getpid()
        
        # Get user processes with a GUI (heuristic)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.info['pid'] == current_pid:
                continue
                
            try:
                info = proc.info
                name = info.get('name', '')
                cmdline = info.get('cmdline', [])
                
                # Skip processes without cmdline (usually system processes)
                if not cmdline:
                    continue
                    
                # Create a descriptive title
                cmd_str = ' '.join(cmdline[:2]) if len(cmdline) > 1 else cmdline[0]
                window_title = f"{name}: {cmd_str[:40]}"
                
                # Skip duplicates
                if window_title and window_title not in [w["title"] for w in windows]:
                    windows.append({
                        "hwnd": info['pid'],  # Use PID as handle
                        "title": window_title,
                        "process_id": info['pid'],
                        "process_name": name
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"Error listing processes as windows: {e}")
        
    # If no windows found, add a fallback
    if not windows:
        windows.append({
            "hwnd": 0,
            "title": "Linux Session",
            "process_id": 0,
            "process_name": "Linux"
        })
    
    return windows
