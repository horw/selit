import os
import time
import pyperclip
import win32gui
import win32process
import psutil
from datetime import datetime
import requests
import json
import argparse


def get_app_data_dir():
    """Get the application data directory in Windows AppData/Local."""
    app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'selit')
    os.makedirs(app_data_dir, exist_ok=True)
    return app_data_dir


def get_config_path():
    """Get the path to the config file."""
    return os.path.join(get_app_data_dir(), 'config.json')


def get_prompts_path():
    """Get the path to the prompts file."""
    return os.path.join(get_app_data_dir(), 'prompts.json')


class ClipboardMonitor:
    def __init__(self, log_callback):
        self.previous_clipboard = ""
        self.log_callback = log_callback
        self.running = True
        self.monitor_thread = None

    def get_active_window_info(self):
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
            return {
                "hwnd": None,
                "title": f"Error: {str(e)}",
                "process_id": None,
                "process_name": "Unknown",
            }

    def monitor_clipboard(self):
        """Monitor the clipboard for changes."""
        print("Clipboard monitor started. Press Ctrl+C to stop.")
        try:
            while self.running:
                try:
                    current_clipboard = pyperclip.paste()
                    if current_clipboard != self.previous_clipboard and current_clipboard.strip():
                        window_info = self.get_active_window_info()

                        current_clipboard = self.log_callback(window_info, current_clipboard)
                        pyperclip.copy(current_clipboard)

                        self.previous_clipboard = current_clipboard
                
                except Exception as e:
                    self.log_callback({"error": str(e)}, "Error monitoring clipboard")
                
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nClipboard monitor stopped.")


class PromptManager:
    def __init__(self, prompts_file=None):
        self.prompts_file = prompts_file or get_prompts_path()
        self.prompts = self._load_prompts()

    def _load_prompts(self):
        """Load prompts from the JSON file."""
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # If prompts.json exists in current directory, migrate it
                local_prompts = 'promts.json'
                if os.path.exists(local_prompts):
                    print(f"Migrating prompts from {local_prompts} to {self.prompts_file}")
                    with open(local_prompts, 'r', encoding='utf-8') as f:
                        prompts = json.load(f)
                    with open(self.prompts_file, 'w', encoding='utf-8') as f:
                        json.dump(prompts, f, ensure_ascii=False, indent=2)
                    return prompts
                return {}
        except Exception as e:
            print(f"Error loading prompts: {str(e)}")
            return {}

    def _save_prompts(self):
        """Save prompts to the JSON file."""
        try:
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving prompts: {str(e)}")
            return False

    def list_prompts(self):
        """List all available prompts."""
        if not self.prompts:
            print("No prompts available.")
            return

        print("\nAvailable prompts:")
        print("-" * 50)
        for key, prompt in self.prompts.items():
            print(f"Window identifier: {key}")
            print(f"Prompt: {prompt[:50]}..." if len(prompt) > 50 else f"Prompt: {prompt}")
            print("-" * 50)

    def add_prompt(self, window_identifier, prompt_text):
        """Add or update a prompt."""
        self.prompts[window_identifier] = prompt_text
        if self._save_prompts():
            print(f"Prompt for '{window_identifier}' added successfully.")
            return True
        return False

    def remove_prompt(self, window_identifier):
        """Remove a prompt."""
        if window_identifier in self.prompts:
            del self.prompts[window_identifier]
            if self._save_prompts():
                print(f"Prompt for '{window_identifier}' removed successfully.")
                return True
        else:
            print(f"No prompt found for '{window_identifier}'.")
        return False

    def get_prompt_for_window(self, window_info):
        """Get the appropriate prompt for the current window."""
        for key in self.prompts:
            if key in window_info['title'] or key in window_info['process_name']:
                return self.prompts[key]
        return None


class ConfigManager:
    def __init__(self, config_file=None):
        self.config_file = config_file or get_config_path()
        self.config = self._load_config()

    def _load_config(self):
        """Load configuration from the JSON file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # If config.json exists in current directory, migrate it
                local_config = 'config.json'
                if os.path.exists(local_config):
                    print(f"Migrating configuration from {local_config} to {self.config_file}")
                    with open(local_config, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2)
                    return config
                
                # Create default config if file doesn't exist
                default_config = {
                    "api_key": "",
                    "trigger_word": "aiit"
                }
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            print(f"Error loading configuration: {str(e)}")
            return {"api_key": "", "trigger_word": "aiit"}

    def _save_config(self):
        """Save configuration to the JSON file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving configuration: {str(e)}")
            return False

    def get_api_key(self):
        """Get the API key from configuration."""
        return self.config.get("api_key", "")

    def set_api_key(self, api_key):
        """Set the API key in configuration."""
        self.config["api_key"] = api_key
        if self._save_config():
            print(f"API key updated successfully.")
            return True
        return False
        
    def get_trigger_word(self):
        """Get the trigger word from configuration."""
        return self.config.get("trigger_word", "aiit")
        
    def set_trigger_word(self, trigger_word):
        """Set the trigger word in configuration."""
        self.config["trigger_word"] = trigger_word
        if self._save_config():
            print(f"Trigger word updated to '{trigger_word}' successfully.")
            return True
        return False

    def show_config(self):
        """Display the current configuration."""
        api_key = self.config.get("api_key", "")
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "Not set"
        trigger_word = self.config.get("trigger_word", "aiit")
        
        print("\nCurrent Configuration:")
        print("-" * 50)
        print(f"API Key: {masked_key}")
        print(f"Trigger Word: {trigger_word}")
        print(f"Config Location: {self.config_file}")
        print(f"Prompts Location: {get_prompts_path()}")
        print("-" * 50)


class GeminiAPI:
    def __init__(self):
        config_manager = ConfigManager()
        self.api_key = config_manager.get_api_key()
        if not self.api_key:
            print("Warning: API key not configured. Please set it using 'selit config api-key YOUR_API_KEY'")
        
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        self.headers = {
            'Content-Type': 'application/json'
        }

    def generate_text(self, prompt_text):
        """Generate text using the Gemini API."""
        if not self.api_key:
            print("Error: API key not configured")
            return None
            
        try:
            data = {
                "contents": [{
                    "parts": [{"text": prompt_text}]
                }]
            }

            response = requests.post(
                self.url, 
                headers=self.headers, 
                data=json.dumps(data, ensure_ascii=True)
            )

            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Exception in Gemini API call: {str(e)}")
            return None


def process_call(window_info, current_clipboard):
    """Process clipboard content using the Gemini API."""
    print(f"Processing clipboard from {window_info['process_name']} - {window_info['title']}")

    config_manager = ConfigManager()
    trigger_word = config_manager.get_trigger_word()
    
    if trigger_word not in current_clipboard:
        return current_clipboard
    
    current_clipboard = current_clipboard.replace(trigger_word, "")

    print('Start processing')
    try:
        if isinstance(current_clipboard, str):
            current_clipboard = current_clipboard.encode('utf-8', errors='replace').decode('utf-8')
        else:
            current_clipboard = str(current_clipboard)

        prompt_manager = PromptManager()
        prompt = prompt_manager.get_prompt_for_window(window_info)
        
        if not prompt:
            print("No matching prompt found for this window.")
            return current_clipboard

        prompt_text = f"{prompt}{current_clipboard}"
        
        gemini_api = GeminiAPI()
        generated_text = gemini_api.generate_text(prompt_text)
        
        if generated_text:
            print("Successfully generated text.")
            return generated_text
        else:
            print("Failed to generate text. Returning original content.")
            return current_clipboard

    except Exception as e:
        print(f"Exception in processing: {str(e)}")
        return current_clipboard


def monitor_command():
    """Start the clipboard monitoring service."""
    monitor = ClipboardMonitor(process_call)
    monitor.monitor_clipboard()


def interactive_add_prompt():
    """Interactive mode for adding prompts by selecting windows."""
    print("\n===== Interactive Prompt Creation Mode =====")
    print("This mode helps you create prompts for specific windows.")
    print("Follow the steps below:")
    
    # Create a monitor to get window info
    monitor = ClipboardMonitor(lambda x, y: y)
    
    # Step 1: Get current window info with a timer
    print("\nStep 1: You to switch to the window you want to create a prompt for and turn back to console...")
    print("Waiting for you to switch windows...")

    stack = [monitor.get_active_window_info()]
    while True:
        if stack[-1] != monitor.get_active_window_info():
            stack.append(monitor.get_active_window_info())
        if len(stack) > 1:
            if stack[-1] == stack[0]:
                break
        time.sleep(0.1)
    
    window_info = stack[-2]
    
    print("\nCurrent window detected:                 ")  # Extra spaces to clear the countdown
    print(f"  Title: {window_info['title']}")
    print(f"  Process: {window_info['process_name']}")
    
    print("\nPlease switch back to this console window to continue...")
    time.sleep(3)
    
    print("\nStep 2: Choose an identifier for this window.")
    print("You can use the window title, process name, or a custom name.")
    print("The identifier will be used to match the window in the future.")
    
    suggestions = []
    if window_info['title']:
        suggestions.append(window_info['title'])
    if window_info['process_name']:
        suggestions.append(window_info['process_name'])
    
    if suggestions:
        print("\nSuggested identifiers:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
    
    identifier = input("\nEnter an identifier (or number from suggestions): ").strip()
    
    if identifier.isdigit() and 1 <= int(identifier) <= len(suggestions):
        identifier = suggestions[int(identifier) - 1]
    
    print("\nStep 3: Enter the prompt to use for this window.")
    print("This is the instruction that will be sent to the AI when you trigger it.")
    print("Write a clear instruction like:")
    print("  'You are a helpful assistant. Please rewrite the following text to be more professional:'")
    prompt = input("\nEnter prompt: ").strip()
    
    prompt_manager = PromptManager()
    success = prompt_manager.add_prompt(identifier, prompt)
    
    if success:
        print(f"\nPrompt for '{identifier}' added successfully!")
    else:
        print("\nFailed to save the prompt. Please try again.")
    
    print("\n===== Interactive Mode Complete =====")


def config_command(args):
    """Handle configuration commands."""
    config_manager = ConfigManager()
    
    if args.action == 'show':
        config_manager.show_config()
    elif args.action == 'api-key':
        if args.value:
            config_manager.set_api_key(args.value)
        else:
            print("Error: API key value is required")
            print("Usage: selit config api-key YOUR_API_KEY")
    elif args.action == 'trigger-word':
        if args.value:
            config_manager.set_trigger_word(args.value)
        else:
            print("Error: Trigger word value is required")
            print("Usage: selit config trigger-word YOUR_TRIGGER_WORD")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Selit - A smart clipboard enhancement tool')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    monitor_parser = subparsers.add_parser('monitor', help='Start clipboard monitoring')
    
    list_parser = subparsers.add_parser('list', help='List all prompts')
    
    add_parser = subparsers.add_parser('add', help='Add or update a prompt')
    add_parser.add_argument('identifier', help='Window title or process name identifier')
    add_parser.add_argument('prompt', help='Prompt text to use')
    
    interactive_parser = subparsers.add_parser('interactive', help='Interactively add a prompt by selecting a window')
    
    remove_parser = subparsers.add_parser('remove', help='Remove a prompt')
    remove_parser.add_argument('identifier', help='Window title or process name identifier to remove')
    
    config_parser = subparsers.add_parser('config', help='Configure settings')
    config_parser.add_argument('action', choices=['show', 'api-key', 'trigger-word'], help='Configuration action to perform')
    config_parser.add_argument('value', nargs='?', help='Value for the configuration (if applicable)')
    
    args = parser.parse_args()
    
    prompt_manager = PromptManager()
    
    if args.command == 'monitor':
        monitor_command()
    elif args.command == 'list':
        prompt_manager.list_prompts()
    elif args.command == 'add':
        prompt_manager.add_prompt(args.identifier, args.prompt)
    elif args.command == 'interactive':
        interactive_add_prompt()
    elif args.command == 'remove':
        prompt_manager.remove_prompt(args.identifier)
    elif args.command == 'config':
        config_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
