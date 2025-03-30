import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired
import win32gui
import win32process
import psutil

from selit.main import ConfigManager, PromptManager, get_app_data_dir

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')
app.static_folder = os.path.join(os.path.dirname(__file__), 'static')

# Initialize managers
config_manager = ConfigManager()
prompt_manager = PromptManager()

class ConfigForm(FlaskForm):
    api_key = StringField('Gemini API Key', validators=[DataRequired()])
    trigger_word = StringField('Trigger Word', validators=[DataRequired()])
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
                    "process_name": process_name
                })
        return True
    
    win32gui.EnumWindows(enum_windows_callback, windows)
    return sorted(windows, key=lambda w: w["title"].lower())

@app.route('/')
def index():
    return render_template('index.html', 
                          api_key=config_manager.get_api_key(),
                          trigger_word=config_manager.get_trigger_word(),
                          prompts=prompt_manager.prompts)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    form = ConfigForm()
    
    if request.method == 'GET':
        form.api_key.data = config_manager.get_api_key()
        form.trigger_word.data = config_manager.get_trigger_word()
    
    if form.validate_on_submit():
        config_manager.set_api_key(form.api_key.data)
        config_manager.set_trigger_word(form.trigger_word.data)
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

def run_web_server(host='127.0.0.1', port=5000, debug=False):
    """Run the web server for the UI."""
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_web_server(debug=True)
