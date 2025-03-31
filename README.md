# Selit - Clipboard Monitoring Tool

Selit (Select it!) is a smart clipboard enhancement tool that monitors your clipboard and applies customized AI prompts based on the active window.

## Features

- Monitor clipboard for changes and detect which window is using the clipboard
- Apply different prompts based on the active window or application
- Send text to Gemini AI API with customized prompts
- Store configurations and prompts in Windows AppData directory or Linux home directory

## Installation

### Windows

```bash
# Install from source
pip install -e .

# Or install directly from GitHub
pip install git+https://github.com/yourusername/selit.git
```

### Linux

```bash
# For best window title detection, install wmctrl or xdotool
sudo apt-get install wmctrl xdotool  # Debian/Ubuntu
# OR
sudo dnf install wmctrl xdotool     # Fedora/RHEL
# OR
sudo pacman -S wmctrl xdotool       # Arch Linux

# Install from source
pip install -e .

# Or install directly from GitHub
pip install git+https://github.com/yourusername/selit.git
```

After installation, the `selit` command will be available in your terminal.

## Usage

### Monitoring Clipboard

```bash
# Start the clipboard monitor
selit monitor
```

When the monitor is running, you can trigger AI processing by including the text "aiit" in your clipboard content. The text will be processed using the appropriate prompt for the current window, and the clipboard will be updated with the AI response.

### Managing Prompts

```bash
# List all available prompts
selit list

# Add a new prompt for a window or application
selit add "Window Title" "Your custom prompt text here"

# Example: Add a prompt for WeChat
selit add "WeChat" "You are a Chinese grammar assistant, please help me improve the following text while maintaining its meaning:"

# Remove a prompt
selit remove "Window Title"
```

### Interactive Mode (Recommended)

The interactive mode makes it easy to create prompts without needing to know command-line arguments:

```bash
# Start the interactive prompt creation mode
selit interactive
```

This will:
1. Give you 5 seconds to switch to your target window
2. Automatically capture the window information
3. Let you select from suggested identifiers or create your own
4. Guide you through creating a prompt
5. Offer to test the prompt immediately

This is the easiest way to add new prompts for different applications!

### Testing Prompts

```bash
# Test a prompt with the current active window
selit test "Some text to process"

# Test a prompt with a specific window identifier
selit test "Some text to process" --window "WeChat"
```

### Configuration

```bash
# View current configuration
selit config show

# Set your Gemini API key
selit config api-key YOUR_API_KEY
```

## How It Works

1. The tool monitors your clipboard for changes
2. When you copy text containing the trigger word "aiit", the tool detects it
3. It identifies the current active window and finds a matching prompt
4. The trigger word is removed, and the text is sent to the Gemini API with the appropriate prompt
5. The clipboard is updated with the AI-generated response

## File Locations

### Windows
All configuration files are stored in: `%APPDATA%\selit\`

### Linux
All configuration files are stored in: `~/.selit/`

- `config.json` - Stores your API key and other configuration
- `prompts.json` - Stores your custom prompts for different windows

## Example Prompts

- **WeChat**: "You are a Chinese grammar assistant, please help me improve the following text while maintaining its meaning:"
- **Gmail**: "You are master of email, change my context to a professional email format:"
- **Telegram**: "You are a language assistant helping me improve my text in multiple languages:"
- **Terminal**: "I'm an engineer who needs help with terminal commands. Explain the following:"

## License

MIT License
