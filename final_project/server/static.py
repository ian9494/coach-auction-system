"""Serve only the isolated Viewer, vendor and images; never the legacy UI/data."""
from pathlib import Path
from fastapi.staticfiles import StaticFiles


def register_static(app):
    public = Path(__file__).resolve().parents[2] / 'public'
    # Source assets are independent of each test/runtime project's isolated DB root.
    for url, folder in (('/final-project','final-project'),('/vendor','vendor'),('/assets','assets')):
        app.mount(url, StaticFiles(directory=public / folder, check_dir=False, follow_symlink=False),
                  name='viewer-' + folder)
