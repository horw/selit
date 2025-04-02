import os


def get_app_data_dir():
    """Get the application data directory based on platform."""
    import platform
    if platform.system() == 'Windows':
        # Windows: use AppData/Roaming
        app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'selit')
    else:
        # Linux/macOS: use ~/.selit
        app_data_dir = os.path.join(os.path.expanduser('~'), '.selit')

    os.makedirs(app_data_dir, exist_ok=True)
    return app_data_dir