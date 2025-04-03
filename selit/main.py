import os
import time
import pyperclip
import platform
import requests
import json
import argparse

from selit.utils import get_window_info
from selit.notification import notification
from selit.history_logger import log_call, get_app_data_dir

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
        # Add a section for keyword-triggered prompts (works across all windows)
        self.keyword_triggers = self.prompts.get('keyword_triggers', {})
        if 'keyword_triggers' not in self.prompts:
            self.prompts['keyword_triggers'] = {}

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
        # Show window-specific prompts
        for key, prompt in self.prompts.items():
            if key != 'keyword_triggers':  # Skip keyword triggers section
                print(f"Window identifier: {key}")
                print(f"Prompt: {prompt[:50]}..." if len(prompt) > 50 else f"Prompt: {prompt}")
                print("-" * 50)
        
        # Show keyword triggers
        if self.keyword_triggers:
            print("\nKeyword triggers (works in all windows):")
            print("-" * 50)
            for keyword, prompt_info in self.keyword_triggers.items():
                print(f"Trigger word: {keyword}")
                prompt = prompt_info.get('prompt', '')
                print(f"Prompt: {prompt[:50]}..." if len(prompt) > 50 else f"Prompt: {prompt}")
                print("-" * 50)

    def add_prompt(self, window_identifier, prompt_text):
        """Add or update a prompt."""
        self.prompts[window_identifier] = prompt_text
        if self._save_prompts():
            print(f"Prompt for '{window_identifier}' added successfully.")
            return True
        return False
    
    def add_keyword_trigger(self, keyword, prompt_text):
        """Add or update a keyword trigger prompt that works in all windows."""
        if 'keyword_triggers' not in self.prompts:
            self.prompts['keyword_triggers'] = {}
        
        self.prompts['keyword_triggers'][keyword] = {
            'prompt': prompt_text
        }
        self.keyword_triggers = self.prompts['keyword_triggers']
        
        if self._save_prompts():
            print(f"Keyword trigger '{keyword}' added successfully.")
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
    
    def remove_keyword_trigger(self, keyword):
        """Remove a keyword trigger."""
        if 'keyword_triggers' in self.prompts and keyword in self.prompts['keyword_triggers']:
            del self.prompts['keyword_triggers'][keyword]
            self.keyword_triggers = self.prompts['keyword_triggers']
            if self._save_prompts():
                print(f"Keyword trigger '{keyword}' removed successfully.")
                return True
        else:
            print(f"No keyword trigger found for '{keyword}'.")
        return False

    def get_prompt_for_window(self, window_info):
        """Get the appropriate prompt for the current window."""
        for key in sorted(self.prompts, key=lambda k: -len(k)):
            # Skip the keyword_triggers section when checking for window matches
            if key != 'keyword_triggers' and (key in window_info['title'] or key in window_info['process_name']):
                return self.prompts[key]
        # If no prompt matches, return the default prompt from configuration
        return self.config_manager.get_default_prompt()
    
    def find_keyword_trigger(self, text):
        """
        Check if the text contains any registered keyword triggers.
        
        Args:
            text (str): The text to check
            
        Returns:
            tuple: (keyword, prompt) if a match is found, otherwise (None, None)
        """
        for keyword, prompt_info in self.keyword_triggers.items():
            if keyword in text:
                return keyword, prompt_info.get('prompt')
        return None, None


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
                    "default_prompt": ConfigManager.default_prompt,
                    "openai_api_key": "",
                    "ai_service": "gemini",  # default to gemini, options: "gemini", "openai", "deepseek"
                    "openai_model": "gpt-3.5-turbo",  # default model
                    "deepseek_api_key": "",
                    "deepseek_model": "deepseek-chat"  # default model
                }
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            print(f"Error loading configuration: {str(e)}")
            return {"api_key": "", "trigger_word": "aiit", "ai_service": "gemini", "openai_api_key": "", "openai_model": "gpt-3.5-turbo", "deepseek_api_key": "", "deepseek_model": "deepseek-chat"}

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

    def get_openai_api_key(self):
        """Get the OpenAI API key from configuration."""
        return self.config.get("openai_api_key", "")

    def set_openai_api_key(self, api_key):
        """Set the OpenAI API key in configuration."""
        self.config["openai_api_key"] = api_key
        if self._save_config():
            print(f"OpenAI API key updated successfully.")
            return True
        return False

    def get_openai_model(self):
        """Get the OpenAI model from configuration."""
        return self.config.get("openai_model", "gpt-3.5-turbo")

    def set_openai_model(self, model):
        """Set the OpenAI model in configuration."""
        self.config["openai_model"] = model
        if self._save_config():
            print(f"OpenAI model updated to '{model}' successfully.")
            return True
        return False

    def get_deepseek_api_key(self):
        """Get the DeepSeek API key from configuration."""
        return self.config.get("deepseek_api_key", "")

    def set_deepseek_api_key(self, api_key):
        """Set the DeepSeek API key in configuration."""
        self.config["deepseek_api_key"] = api_key
        if self._save_config():
            print(f"DeepSeek API key updated successfully.")
            return True
        return False

    def get_deepseek_model(self):
        """Get the DeepSeek model from configuration."""
        return self.config.get("deepseek_model", "deepseek-chat")

    def set_deepseek_model(self, model):
        """Set the DeepSeek model in configuration."""
        self.config["deepseek_model"] = model
        if self._save_config():
            print(f"DeepSeek model updated to '{model}' successfully.")
            return True
        return False

    def get_ai_service(self):
        """Get the AI service to use (gemini, openai, or deepseek)."""
        return self.config.get("ai_service", "gemini")

    def set_ai_service(self, service):
        """Set the AI service to use (gemini, openai, or deepseek)."""
        if service not in ["gemini", "openai", "deepseek"]:
            print(f"Invalid AI service: {service}. Must be 'gemini', 'openai', or 'deepseek'.")
            return False

        self.config["ai_service"] = service
        if self._save_config():
            print(f"AI service updated to '{service}' successfully.")
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

        openai_api_key = self.config.get("openai_api_key", "")
        masked_openai_key = f"{openai_api_key[:4]}...{openai_api_key[-4:]}" if len(openai_api_key) > 8 else "Not set"

        deepseek_api_key = self.config.get("deepseek_api_key", "")
        masked_deepseek_key = f"{deepseek_api_key[:4]}...{deepseek_api_key[-4:]}" if len(deepseek_api_key) > 8 else "Not set"

        trigger_word = self.config.get("trigger_word", "aiit")
        default_prompt = self.config.get("default_prompt", ConfigManager.default_prompt)
        ai_service = self.config.get("ai_service", "gemini")
        openai_model = self.config.get("openai_model", "gpt-3.5-turbo")
        deepseek_model = self.config.get("deepseek_model", "deepseek-chat")

        print("\nCurrent Configuration:")
        print("-" * 50)
        print(f"AI Service: {ai_service}")
        print(f"Gemini API Key: {masked_key}")
        print(f"OpenAI API Key: {masked_openai_key}")
        print(f"OpenAI Model: {openai_model}")
        print(f"DeepSeek API Key: {masked_deepseek_key}")
        print(f"DeepSeek Model: {deepseek_model}")
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


def get_config_path():
    """Get the path to the config file."""
    return os.path.join(get_app_data_dir(), 'config.json')


def get_prompts_path():
    """Get the path to the prompts file."""
    return os.path.join(get_app_data_dir(), 'prompts.json')


class OpenAIAPI:
    def __init__(self):
        config_manager = ConfigManager()
        self.api_key = config_manager.get_openai_api_key()
        self.model = config_manager.get_openai_model()

        if not self.api_key:
            print("Warning: OpenAI API key not configured. Please set it using 'selit config openai-api-key YOUR_API_KEY'")

        self.url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    def generate_text(self, prompt_text):
        """Generate text using the OpenAI API."""
        if not self.api_key:
            print("Error: OpenAI API key not configured")
            return None

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.7
            }

            response = requests.post(
                self.url,
                headers=self.headers,
                data=json.dumps(data)
            )

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Exception in OpenAI API call: {str(e)}")
            return None


class DeepSeekAPI:
    def __init__(self):
        config_manager = ConfigManager()
        self.api_key = config_manager.get_deepseek_api_key()
        self.model = config_manager.get_deepseek_model()

        if not self.api_key:
            print("Warning: DeepSeek API key not configured. Please set it using 'selit config deepseek-api-key YOUR_API_KEY'")

        self.url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    def generate_text(self, prompt_text):
        """Generate text using the DeepSeek API."""
        if not self.api_key:
            print("Error: DeepSeek API key not configured")
            return None

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.7
            }

            response = requests.post(
                self.url,
                headers=self.headers,
                data=json.dumps(data)
            )

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Exception in DeepSeek API call: {str(e)}")
            return None


def process_call(window_info, current_clipboard):
    """Process clipboard content using the selected AI API."""
    print(f"Processing clipboard from {window_info['process_name']} - {window_info['title']}")

    config_manager = ConfigManager()
    trigger_word = config_manager.get_trigger_word()
    prompt_manager = PromptManager()
    
    # Check for trigger word
    if trigger_word in current_clipboard:
        original_input = current_clipboard
        current_clipboard = current_clipboard.replace(trigger_word, "")
        # Get window-specific prompt or default
        prompt = prompt_manager.get_prompt_for_window(window_info)
        return process_with_prompt(window_info, current_clipboard, original_input, prompt, trigger_word)
    
    # Check for keyword triggers
    keyword, keyword_prompt = prompt_manager.find_keyword_trigger(current_clipboard)
    if keyword and keyword_prompt:
        original_input = current_clipboard
        current_clipboard = current_clipboard.replace(keyword, "")
        return process_with_prompt(window_info, current_clipboard, original_input, keyword_prompt, keyword)
    
    # No triggers found
    return current_clipboard

def process_with_prompt(window_info, text, original_input, prompt, trigger_word):
    """Process text with a specific prompt using the configured AI service."""
    print('Start processing')
    try:
        if isinstance(text, str):
            text = text.encode('utf-8', errors='replace').decode('utf-8')
        else:
            text = str(text)

        # Format the prompt with the text
        if "{text}" in prompt:
            prompt_text = prompt.replace('{text}', text)
        else:
            prompt_text = f"{prompt}{text}"

        print(prompt_text)

        config_manager = ConfigManager()
        ai_service = config_manager.get_ai_service()

        if ai_service == "gemini":
            api = GeminiAPI()
        elif ai_service == "openai":
            api = OpenAIAPI()
        else:  # deepseek
            api = DeepSeekAPI()

        generated_text = api.generate_text(prompt_text)
        
        if generated_text:
            print("Successfully generated text.")
            notification(title="Select it!", message="Text generated successfully")
            # Log the successful call
            log_call(window_info, original_input, generated_text, trigger_word)
            return generated_text
        else:
            print("Failed to generate text. Returning original content.")
            notification(title="Select it!", message="Failed to generate text.")
            return text

    except Exception as e:
        print(f"Exception in processing: {str(e)}")
        return text

def monitor_command():
    """Start the clipboard monitoring service."""
    monitor = ClipboardMonitor(process_call)
    monitor.monitor_clipboard()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="SeLit - Select it! A clipboard monitoring tool to process copied text with AI model assistance")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor the clipboard for changes")

    # Config command
    config_parser = subparsers.add_parser("config", help="Configure the application")
    config_subparsers = config_parser.add_subparsers(dest="config_action", help="Configuration action")

    # Config: show
    config_show = config_subparsers.add_parser("show", help="Show current configuration")

    # Config: API key
    config_api_key = config_subparsers.add_parser("api-key", help="Set the Gemini API key")
    config_api_key.add_argument("key", help="The Gemini API key to set")

    # Config: OpenAI API key
    config_openai_key = config_subparsers.add_parser("openai-api-key", help="Set the OpenAI API key")
    config_openai_key.add_argument("key", help="The OpenAI API key to set")

    # Config: DeepSeek API key
    config_deepseek_key = config_subparsers.add_parser("deepseek-api-key", help="Set the DeepSeek API key")
    config_deepseek_key.add_argument("key", help="The DeepSeek API key to set")

    # Config: AI service
    config_service = config_subparsers.add_parser("ai-service", help="Set the AI service to use (gemini, openai, or deepseek)")
    config_service.add_argument("service", choices=["gemini", "openai", "deepseek"], help="The AI service to use")

    # Config: OpenAI model
    config_openai_model = config_subparsers.add_parser("openai-model", help="Set the OpenAI model to use")
    config_openai_model.add_argument("model", help="The OpenAI model to use (e.g., gpt-3.5-turbo, gpt-4)")

    # Config: DeepSeek model
    config_deepseek_model = config_subparsers.add_parser("deepseek-model", help="Set the DeepSeek model to use")
    config_deepseek_model.add_argument("model", help="The DeepSeek model to use (e.g., deepseek-chat, deepseek-coder)")

    # Config: trigger word
    config_trigger = config_subparsers.add_parser("trigger", help="Set the trigger word")
    config_trigger.add_argument("word", help="The trigger word to set")
    
    # Config: default prompt
    config_prompt = config_subparsers.add_parser("default-prompt", help="Set the default prompt")
    config_prompt.add_argument("prompt", help="The default prompt to set")
    
    # Prompts command
    prompts_parser = subparsers.add_parser("prompts", help="Manage prompts")
    prompts_subparsers = prompts_parser.add_subparsers(dest="prompts_action", help="Prompts action")

    # Prompts: list
    prompts_list = prompts_subparsers.add_parser("list", help="List all available prompts")

    # Prompts: add
    prompts_add = prompts_subparsers.add_parser("add", help="Add a new prompt")
    prompts_add.add_argument("window", help="Window identifier (title or process name)")
    prompts_add.add_argument("prompt", help="The prompt text to add")

    # Prompts: remove
    prompts_remove = prompts_subparsers.add_parser("remove", help="Remove a prompt")
    prompts_remove.add_argument("window", help="Window identifier (title or process name)")

    # Prompts: add keyword trigger
    prompts_add_keyword_trigger = prompts_subparsers.add_parser("add-keyword-trigger", help="Add a new keyword trigger prompt")
    prompts_add_keyword_trigger.add_argument("keyword", help="The keyword to trigger the prompt")
    prompts_add_keyword_trigger.add_argument("prompt", help="The prompt text to add")

    # Prompts: remove keyword trigger
    prompts_remove_keyword_trigger = prompts_subparsers.add_parser("remove-keyword-trigger", help="Remove a keyword trigger prompt")
    prompts_remove_keyword_trigger.add_argument("keyword", help="The keyword to remove")

    # Web interface command
    web_parser = subparsers.add_parser("web", help="Start the web interface")
    web_parser.add_argument("--port", type=int, default=5000, help="Port to run the web interface on (default: 5000)")

    args = parser.parse_args()
    
    if args.command == "monitor":
        monitor_command()
    elif args.command == "config":
        config_manager = ConfigManager()

        if args.config_action == "show":
            config_manager.show_config()
        elif args.config_action == "api-key":
            config_manager.set_api_key(args.key)
        elif args.config_action == "openai-api-key":
            config_manager.set_openai_api_key(args.key)
        elif args.config_action == "deepseek-api-key":
            config_manager.set_deepseek_api_key(args.key)
        elif args.config_action == "ai-service":
            config_manager.set_ai_service(args.service)
        elif args.config_action == "openai-model":
            config_manager.set_openai_model(args.model)
        elif args.config_action == "deepseek-model":
            config_manager.set_deepseek_model(args.model)
        elif args.config_action == "trigger":
            config_manager.set_trigger_word(args.word)
        elif args.config_action == "default-prompt":
            config_manager.set_default_prompt(args.prompt)
        else:
            config_manager.show_config()
    elif args.command == "prompts":
        prompt_manager = PromptManager()

        if args.prompts_action == "list":
            prompt_manager.list_prompts()
        elif args.prompts_action == "add":
            prompt_manager.add_prompt(args.window, args.prompt)
        elif args.prompts_action == "remove":
            prompt_manager.remove_prompt(args.window)
        elif args.prompts_action == "add-keyword-trigger":
            prompt_manager.add_keyword_trigger(args.keyword, args.prompt)
        elif args.prompts_action == "remove-keyword-trigger":
            prompt_manager.remove_keyword_trigger(args.keyword)
        else:
            prompt_manager.list_prompts()
    elif args.command == "web":
        # Import web module here to avoid circular imports
        from selit.web import run_web_server
        print(f"Starting web interface at http://localhost:{args.port}")
        print("Press Ctrl+C to stop the server")
        run_web_server(host="localhost", port=args.port, debug=False)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
