import os
import platform
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, HiddenField, SelectField, RadioField
from wtforms.validators import DataRequired
import threading
import datetime
import json

if platform.system() == 'Windows':
    import win32gui
    import win32process

from selit.main import ConfigManager, PromptManager, GeminiAPI, OpenAIAPI, DeepSeekAPI, ClipboardMonitor, process_call
from selit.utils import get_window_info
from selit.history_logger import get_call_history, generate_day_summary, get_history_dir

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')
app.static_folder = os.path.join(os.path.dirname(__file__), 'static')

# Initialize managers
config_manager = ConfigManager()
prompt_manager = PromptManager()

# Register template filters
@app.template_filter('datetime')
def format_datetime(value):
    if isinstance(value, str):
        try:
            dt = datetime.datetime.fromisoformat(value)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return value
    return value

class ConfigForm(FlaskForm):
    ai_service = RadioField('AI Service', choices=[
        ('gemini', 'Gemini'), 
        ('openai', 'OpenAI'),
        ('deepseek', 'DeepSeek')
    ], validators=[DataRequired()])
    api_key = StringField('Gemini API Key')
    openai_api_key = StringField('OpenAI API Key')
    openai_model = SelectField('OpenAI Model', choices=[
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
        ('gpt-4', 'GPT-4'),
        ('gpt-4-turbo', 'GPT-4 Turbo')
    ])
    deepseek_api_key = StringField('DeepSeek API Key')
    deepseek_model = SelectField('DeepSeek Model', choices=[
        ('deepseek-chat', 'DeepSeek Chat'),
        ('deepseek-reasoner', 'DeepSeek Reasoner')
    ])
    trigger_word = StringField('Trigger Word', validators=[DataRequired()])
    default_prompt = TextAreaField('Default Prompt', validators=[DataRequired()])
    submit = SubmitField('Save Settings')

class PromptForm(FlaskForm):
    window_identifier = StringField('Window Identifier', validators=[DataRequired()])
    prompt_text = TextAreaField('Prompt Template', validators=[DataRequired()])
    submit = SubmitField('Save Prompt')

class DeletePromptForm(FlaskForm):
    window_identifier = HiddenField('Window Identifier', validators=[DataRequired()])
    submit = SubmitField('Delete')

class KeywordTriggerForm(FlaskForm):
    keyword = StringField('Trigger Keyword', validators=[DataRequired()])
    prompt_text = TextAreaField('Prompt Template', validators=[DataRequired()])
    submit = SubmitField('Save Keyword Trigger')

class DeleteKeywordTriggerForm(FlaskForm):
    keyword = HiddenField('Keyword', validators=[DataRequired()])
    submit = SubmitField('Delete')

def get_all_windows():
    """Get a list of all visible windows with their titles and process names."""
    return get_window_info(get_active_only=False)

@app.route('/')
def index():
    # Get today's call history for the dashboard
    today_history = get_call_history(days=1)
    
    return render_template('index.html', 
                          api_key=config_manager.get_api_key(),
                          openai_api_key=config_manager.get_openai_api_key(),
                          deepseek_api_key=config_manager.get_deepseek_api_key(),
                          ai_service=config_manager.get_ai_service(),
                          openai_model=config_manager.get_openai_model(),
                          deepseek_model=config_manager.get_deepseek_model(),
                          trigger_word=config_manager.get_trigger_word(),
                          default_prompt=config_manager.get_default_prompt(),
                          prompts=prompt_manager.prompts,
                          today_history=today_history)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    form = ConfigForm()
    
    if request.method == 'GET':
        form.ai_service.data = config_manager.get_ai_service()
        form.api_key.data = config_manager.get_api_key()
        form.openai_api_key.data = config_manager.get_openai_api_key()
        form.openai_model.data = config_manager.get_openai_model()
        form.deepseek_api_key.data = config_manager.get_deepseek_api_key()
        form.deepseek_model.data = config_manager.get_deepseek_model()
        form.trigger_word.data = config_manager.get_trigger_word()
        form.default_prompt.data = config_manager.get_default_prompt()
    
    if form.validate_on_submit():
        config_manager.set_ai_service(form.ai_service.data)
        config_manager.set_api_key(form.api_key.data)
        config_manager.set_openai_api_key(form.openai_api_key.data)
        config_manager.set_openai_model(form.openai_model.data)
        config_manager.set_deepseek_api_key(form.deepseek_api_key.data)
        config_manager.set_deepseek_model(form.deepseek_model.data)
        config_manager.set_trigger_word(form.trigger_word.data)
        config_manager.set_default_prompt(form.default_prompt.data)
        config_manager._save_config()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('settings.html', form=form)

@app.route('/prompts', methods=['GET'])
def prompts():
    prompt_form = PromptForm()
    delete_form = DeletePromptForm()
    keyword_trigger_form = KeywordTriggerForm()
    delete_keyword_trigger_form = DeleteKeywordTriggerForm()
    return render_template('prompts.html', 
                          prompts=prompt_manager.prompts, 
                          keyword_triggers=prompt_manager.keyword_triggers,
                          prompt_form=prompt_form,
                          delete_form=delete_form,
                          keyword_trigger_form=keyword_trigger_form,
                          delete_keyword_trigger_form=delete_keyword_trigger_form)

@app.route('/prompts/add_page', methods=['GET'])
def add_prompt_page():
    form = PromptForm()
    return render_template('add_prompt.html', form=form)

@app.route('/prompts/add_keyword_trigger_page', methods=['GET'])
def add_keyword_trigger_page():
    form = KeywordTriggerForm()
    return render_template('add_keyword_trigger.html', form=form)

@app.route('/prompts/add', methods=['POST'])
def add_prompt():
    form = PromptForm()
    if form.validate_on_submit():
        window_identifier = form.window_identifier.data
        prompt_text = form.prompt_text.data
        prompt_manager.add_prompt(window_identifier, prompt_text)
        flash(f'Prompt for "{window_identifier}" saved successfully!', 'success')
    return redirect(url_for('prompts'))

@app.route('/prompts/edit/<window_id>', methods=['GET'])
def edit_prompt(window_id):
    form = PromptForm()
    if window_id in prompt_manager.prompts:
        form.window_identifier.data = window_id
        form.prompt_text.data = prompt_manager.prompts[window_id]
    return render_template('edit_prompt.html', form=form, window_id=window_id)

@app.route('/prompts/update/<window_id>', methods=['POST'])
def update_prompt(window_id):
    form = PromptForm()
    if form.validate_on_submit():
        # If window identifier changed, remove the old one
        if window_id != form.window_identifier.data and window_id in prompt_manager.prompts:
            prompt_manager.remove_prompt(window_id)
        
        # Add the prompt with possibly new window identifier
        prompt_manager.add_prompt(form.window_identifier.data, form.prompt_text.data)
        flash(f'Prompt updated successfully!', 'success')
    return redirect(url_for('prompts'))

@app.route('/prompts/delete', methods=['POST'])
def delete_prompt():
    form = DeletePromptForm()
    if form.validate_on_submit():
        window_identifier = form.window_identifier.data
        if prompt_manager.remove_prompt(window_identifier):
            flash(f'Prompt for "{window_identifier}" deleted successfully!', 'success')
        else:
            flash(f'Failed to delete prompt for "{window_identifier}"', 'danger')
    return redirect(url_for('prompts'))

@app.route('/prompts/add_keyword_trigger', methods=['POST'])
def add_keyword_trigger():
    form = KeywordTriggerForm()
    if form.validate_on_submit():
        keyword = form.keyword.data
        prompt_text = form.prompt_text.data
        if prompt_manager.add_keyword_trigger(keyword, prompt_text):
            flash(f'Keyword trigger "{keyword}" added successfully', 'success')
        else:
            flash('Failed to add keyword trigger', 'danger')
    return redirect(url_for('prompts'))

@app.route('/prompts/delete_keyword_trigger', methods=['POST'])
def delete_keyword_trigger():
    form = DeleteKeywordTriggerForm()
    if form.validate_on_submit():
        keyword = form.keyword.data
        if prompt_manager.remove_keyword_trigger(keyword):
            flash(f'Keyword trigger "{keyword}" deleted successfully', 'success')
        else:
            flash('Failed to delete keyword trigger', 'danger')
    return redirect(url_for('prompts'))

@app.route('/prompts/edit_keyword_trigger/<keyword>', methods=['GET'])
def edit_keyword_trigger(keyword):
    """Edit a keyword trigger prompt."""
    if keyword in prompt_manager.keyword_triggers:
        form = KeywordTriggerForm()
        form.keyword.data = keyword
        form.prompt_text.data = prompt_manager.keyword_triggers[keyword]['prompt']
        return render_template('edit_keyword_trigger.html', form=form, keyword=keyword)
    else:
        flash(f'Keyword trigger "{keyword}" not found', 'danger')
        return redirect(url_for('prompts'))

@app.route('/prompts/update_keyword_trigger/<keyword>', methods=['POST'])
def update_keyword_trigger(keyword):
    """Update a keyword trigger prompt."""
    form = KeywordTriggerForm()
    if form.validate_on_submit():
        new_keyword = form.keyword.data
        prompt_text = form.prompt_text.data
        
        # If the keyword has changed, we need to remove the old one and add a new one
        if keyword != new_keyword:
            prompt_manager.remove_keyword_trigger(keyword)
        
        if prompt_manager.add_keyword_trigger(new_keyword, prompt_text):
            flash(f'Keyword trigger "{new_keyword}" updated successfully', 'success')
        else:
            flash('Failed to update keyword trigger', 'danger')
    
    return redirect(url_for('prompts'))

@app.route('/history')
def history():
    # Get the number of days from request, default to 1 (today only)
    try:
        days = int(request.args.get('days', 1))
        if days < 1:
            days = 1
        elif days > 30:  # Limit to 30 days max
            days = 30
    except ValueError:
        days = 1
    
    # Get call history
    call_history = get_call_history(days)
    
    return render_template('history.html', history=call_history, days=days)

@app.route('/history/summary')
def history_summary():
    # Get date parameter, default to today
    date_str = request.args.get('date')
    
    if date_str:
        try:
            # Parse the date string
            date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            # Invalid date format, default to today
            date = datetime.datetime.now().date()
    else:
        # No date specified, use today
        date = datetime.datetime.now().date()
    
    # Generate summary
    summary = generate_day_summary(date)
    
    return jsonify(summary)

@app.route('/history/summary/analyze', methods=['POST'])
def analyze_summary():
    # Get the summary data and date from request
    request_data = request.json
    
    if not request_data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Extract date from the summary data
    date_str = request_data.get('date')
    if not date_str:
        return jsonify({'error': 'No date provided'}), 400
    
    try:
        # Parse the date string
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        # Invalid date format, default to today
        date = datetime.datetime.now().date()
    
    # Get the full interaction data for that date
    history_data = get_detailed_history_for_date(date)
    
    # Format the history data and summary into a meaningful text for AI analysis
    analysis_text = format_detailed_history_for_ai(history_data, request_data)
    
    # Determine which AI service to use
    ai_service = config_manager.get_ai_service()
    
    # Prepare the prompt for AI
    prompt = (
        "You are an assistant analyzing daily usage patterns of an AI assistant tool called 'Select it!'.\n\n"
        "Below is a summary of a user's interactions for a day, followed by the detailed list of all interactions "
        "including input text, output text, and the applications where they were used. "
        "Please provide two distinct sections in your response:\n\n"
        
        "SECTION 1 - USAGE ANALYSIS:\n"
        "Please analyze the data and provide insights about their usage patterns, including:\n"
        "1. When they were most active\n"
        "2. Which applications they used most frequently\n"
        "3. Common themes or topics in their inputs\n"
        "4. Patterns in the types of tasks they're using the assistant for\n"
        "5. Any other interesting observations\n\n"
        
        "SECTION 2 - DAILY WORK REPORT:\n"
        "Based on the interactions and their content, create a professional daily work report that the user could share with their boss. "
        "This report should:\n"
        "1. Summarize the main work activities performed today\n"
        "2. Highlight key accomplishments and progress made\n"
        "3. Identify the main projects or tasks worked on\n"
        "4. Be written in a professional first-person tone (as if the user wrote it)\n"
        "5. Be concise but comprehensive (approximately 150-250 words)\n\n"
        
        f"{analysis_text}\n\n"
        
        "Format both sections with appropriate headers. For the work report section, focus only on professional work-related activities "
        "that would be appropriate to share with management, ignoring any personal conversations or activities."
    )
    
    try:
        # Process with the configured AI service
        if ai_service == 'gemini':
            api = GeminiAPI()
            result = api.generate_text(prompt)
        elif ai_service == 'openai':
            api = OpenAIAPI()
            result = api.generate_text(prompt)
        elif ai_service == 'deepseek':
            api = DeepSeekAPI()
            result = api.generate_text(prompt)
        else:
            # Default to Gemini if service not recognized
            api = GeminiAPI()
            result = api.generate_text(prompt)
            
        return jsonify({'analysis': result})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_detailed_history_for_date(date):
    """Get detailed history data for a specific date"""
    date_str = date.strftime('%Y-%m-%d')
    log_file = os.path.join(get_history_dir(), f'selit_{date_str}.log')
    
    interactions = []
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        interactions.append(entry)
                    except json.JSONDecodeError:
                        # Skip invalid lines
                        continue
        except Exception as e:
            print(f"Error reading history from {log_file}: {str(e)}")
    
    # Sort by timestamp (oldest first for chronological analysis)
    interactions.sort(key=lambda x: x.get('timestamp', ''))
    return interactions


def format_detailed_history_for_ai(history_data, summary_data):
    """Format detailed history and summary data into text for AI analysis"""
    
    # Start with a summary section
    text = "=== DAILY SUMMARY ===\n"
    text += f"Date: {summary_data['date']}\n"
    text += f"Total Interactions: {summary_data['total_interactions']}\n"
    
    # Add busiest hour if available
    if summary_data.get('busiest_hour') is not None:
        hour = summary_data['busiest_hour']
        text += f"Busiest Hour: {hour}:00 - {hour}:59\n"
    
    # Add average lengths
    text += f"Average Input Length: {summary_data['average_input_length']} characters\n"
    text += f"Average Output Length: {summary_data['average_output_length']} characters\n\n"
    
    # Add applications usage
    text += "Most Used Applications:\n"
    for app_name, count in summary_data.get('apps', {}).items():
        text += f"- {app_name}: {count} interactions\n"
    
    # Add hour distribution
    text += "\nActivity by Hour:\n"
    for hour, count in summary_data.get('hour_distribution', {}).items():
        if count > 0:
            text += f"- {hour}:00 - {hour}:59: {count} interactions\n"
    
    # Add detailed interactions
    text += "\n\n=== DETAILED INTERACTIONS ===\n"
    
    for i, entry in enumerate(history_data, 1):
        timestamp = entry.get('timestamp', '')
        try:
            dt = datetime.datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime('%H:%M:%S')
        except (ValueError, TypeError):
            formatted_time = timestamp
            
        text += f"\n--- INTERACTION {i} (Time: {formatted_time}) ---\n"
        
        # Add window information
        window = entry.get('window', {})
        text += f"Application: {window.get('process_name', 'Unknown')}\n"
        text += f"Window Title: {window.get('title', 'Unknown')}\n"
        
        # Add trigger word
        text += f"Triggered by: {entry.get('trigger_word', 'Unknown')}\n\n"
        
        # Add input and output (truncate if too long to avoid hitting context limits)
        input_text = entry.get('input', '')
        output_text = entry.get('output', '')
        
        # Limit input/output length to 1000 chars if needed
        max_length = 1000
        if len(input_text) > max_length:
            input_text = input_text[:max_length] + "... [truncated]"
        if len(output_text) > max_length:
            output_text = output_text[:max_length] + "... [truncated]"
            
        text += f"INPUT:\n{input_text}\n\n"
        text += f"OUTPUT:\n{output_text}\n"
    
    return text


@app.route('/api/windows', methods=['GET'])
def get_windows():
    """API endpoint to get all open windows."""
    windows = get_all_windows()
    return jsonify(windows)

@app.route('/api/generate-prompt', methods=['POST'])
def generate_prompt():
    """Generate a prompt template using AI based on user context."""
    data = request.json
    context = data.get('context', '')
    window_identifier = data.get('window_identifier', '')
    is_keyword_trigger = data.get('is_keyword_trigger', False)
    keyword = data.get('keyword', '')
    
    if not context:
        return jsonify({
            'success': False,
            'message': 'Context is required'
        }), 400
    
    try:
        ai_service = config_manager.get_ai_service()
        
        # Prepare the system prompt for generating a template
        if is_keyword_trigger:
            system_prompt = f"""
            I need to create a prompt template for an AI assistant that will be triggered by a specific keyword. Here's the context:
            
            - Trigger keyword: {keyword}
            - Use case context: {context}
            
            Please generate a well-structured prompt template that will be triggered when this keyword is found in copied text.
            The template should include placeholder {{text}} where the user's input will be inserted.
            Make the prompt clear, specific, and optimized for good AI responses related to the keyword "{keyword}".
            
            Return ONLY the prompt template text without any explanations or additional text.
            """
        else:
            system_prompt = f"""
            I need to create a prompt template for an AI assistant. Here's the context:
            
            - Application/Window: {window_identifier}
            - Context: {context}
            
            Please generate a well-structured prompt template that I can use for this application.
            The template should include placeholder {{text}} where the user's input will be inserted.
            Make the prompt clear, specific, and optimized for good AI responses.
            
            Return ONLY the prompt template text without any explanations or additional text.
            """
        
        if ai_service == "gemini":
            api = GeminiAPI()
        elif ai_service == "openai":
            api = OpenAIAPI()
        else:  # deepseek
            api = DeepSeekAPI()
            
        result = api.generate_text(system_prompt)
        
        if result:
            return jsonify({
                'success': True,
                'prompt': result
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to generate prompt template'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

def run_web_server(host='127.0.0.1', port=5000, debug=False):
    """Run the web server for the UI."""
    # Start clipboard monitor in a background thread
    monitor = ClipboardMonitor(process_call)
    monitor_thread = threading.Thread(target=monitor.monitor_clipboard, daemon=True)
    monitor_thread.start()
    print("Clipboard monitor started in background")
    
    # Run Flask app
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_web_server(debug=True)
