import os
import time
import pyperclip
import platform
import requests
import json
import argparse

from selit.utils import get_window_info
from selit.notification import notification


def get_app_data_dir():
    """Get the application data directory based on platform."""
    if platform.system() == 'Windows':
        # Windows: use AppData/Roaming
        app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'selit')
    else:
        # Linux/macOS: use ~/.selit
        app_data_dir = os.path.join(os.path.expanduser('~'), '.selit')
    
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
            window_info = get_window_info(get_active_only=True)
            if window_info:
                return window_info
            
            # Fallback in case the utility returns None
            return {
                "hwnd": None,
                "title": "No active window detected",
                "process_id": None,
                "process_name": "Unknown",
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
        self.config_manager = ConfigManager()

    def _load_prompts(self):
        """Load prompts from the JSON file."""
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # If prompts.json exists in current directory, migrate it
                local_prompts = 'prompts.json'
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
        for key in sorted(self.prompts, key=lambda k: -len(k)):
            if key in window_info['title'] or key in window_info['process_name']:
                return self.prompts[key]
        # If no prompt matches, return the default prompt from configuration
        return self.config_manager.get_default_prompt()


class ConfigManager:
    default_prompt =  (
        "You are a grammar assistant specializing in technical writing. "
        "Carefully check the grammar in the text below. "
        "Correct any grammar, spelling, punctuation, and style errors "
        "while ensuring the original meaning and intent of the text remain unchanged. "
        "Accuracy and attention to detail are crucial. "
        "Output only the corrected text; "
        "do not provide any analysis or additional information.\n{text}"
    )
    
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
                    "trigger_word": "aiit",
                    "default_prompt": ConfigManager.default_prompt
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
        
    def get_default_prompt(self):
        """Get the default prompt from configuration."""
        return self.config.get("default_prompt", ConfigManager.default_prompt)
        
    def set_default_prompt(self, default_prompt):
        """Set the default prompt in configuration."""
        self.config["default_prompt"] = default_prompt
        if self._save_config():
            print(f"Default prompt updated successfully.")
            return True
        return False

    def show_config(self):
        """Display the current configuration."""
        api_key = self.config.get("api_key", "")
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "Not set"
        trigger_word = self.config.get("trigger_word", "aiit")
        default_prompt = self.config.get("default_prompt", ConfigManager.default_prompt)
        
        print("\nCurrent Configuration:")
        print("-" * 50)
        print(f"API Key: {masked_key}")
        print(f"Trigger Word: {trigger_word}")
        print(f"Default Prompt: {default_prompt}")
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
        
        # No need to check for None prompt since we now have a default prompt

        if "{text}" in prompt:
            prompt_text = prompt.replace('{text}', current_clipboard)
        else:
            prompt_text = f"{prompt}{current_clipboard}"

        print(prompt_text)
        gemini_api = GeminiAPI()
        generated_text = gemini_api.generate_text(prompt_text)
        
        if generated_text:
            print("Successfully generated text.")
            notification(title="Select it!", message="Text generated successfully")
            return generated_text
        else:
            print("Failed to generate text. Returning original content.")
            notification(title="Select it!", message="Failed to generate text.")
            return current_clipboard

    except Exception as e:
        print(f"Exception in processing: {str(e)}")
        return current_clipboard


def monitor_command():
    """Start the clipboard monitoring service."""
    monitor = ClipboardMonitor(process_call)
    monitor.monitor_clipboard()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Selit - A smart clipboard enhancement tool')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    monitor_parser = subparsers.add_parser('monitor', help='Start clipboard monitoring')
    
    web_parser = subparsers.add_parser('web', help='Launch the web interface')
    web_parser.add_argument('--host', default="127.0.0.1", help='Host to bind the web server to')
    web_parser.add_argument('--port', type=int, default=5000, help='Port to run the web server on')
    web_parser.add_argument('--debug', action='store_true', help='Run in debug mode')

    args = parser.parse_args()
    
    if args.command == 'monitor':
        monitor_command()
    elif args.command == 'web':
        # Import web module here to avoid circular imports
        from selit.web import run_web_server
        print(f"Starting web interface at http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop the server")
        run_web_server(host=args.host, port=args.port, debug=args.debug)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
