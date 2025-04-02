import os
import platform
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, HiddenField, SelectField, RadioField
from wtforms.validators import DataRequired
import threading

if platform.system() == 'Windows':
    import win32gui
    import win32process

from selit.main import ConfigManager, PromptManager, GeminiAPI, OpenAIAPI, DeepSeekAPI, ClipboardMonitor, process_call
from selit.utils import get_window_info

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')
app.static_folder = os.path.join(os.path.dirname(__file__), 'static')

# Initialize managers
config_manager = ConfigManager()
prompt_manager = PromptManager()

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

def get_all_windows():
    """Get a list of all visible windows with their titles and process names."""
    return get_window_info(get_active_only=False)

@app.route('/')
def index():
    return render_template('index.html', 
                          api_key=config_manager.get_api_key(),
                          openai_api_key=config_manager.get_openai_api_key(),
                          deepseek_api_key=config_manager.get_deepseek_api_key(),
                          ai_service=config_manager.get_ai_service(),
                          openai_model=config_manager.get_openai_model(),
                          deepseek_model=config_manager.get_deepseek_model(),
                          trigger_word=config_manager.get_trigger_word(),
                          default_prompt=config_manager.get_default_prompt(),
                          prompts=prompt_manager.prompts)

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
    return render_template('prompts.html', 
                          prompts=prompt_manager.prompts, 
                          prompt_form=prompt_form,
                          delete_form=delete_form)

@app.route('/prompts/add_page', methods=['GET'])
def add_prompt_page():
    form = PromptForm()
    return render_template('add_prompt.html', form=form)

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
    
    if not context:
        return jsonify({
            'success': False,
            'message': 'Context is required'
        }), 400
    
    try:
        ai_service = config_manager.get_ai_service()
        
        # Prepare the system prompt for generating a template
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
