"""Read-only resources for source checkout and installed wheels."""
from pathlib import Path
import sysconfig


def resource_root() -> Path:
    source = Path(__file__).resolve().parent.parent
    if (source / 'public/final-project/viewer.html').is_file():
        return source
    installed = Path(sysconfig.get_path('data')) / 'share/coach-auction-final-project'
    if not (installed / 'public/final-project/viewer.html').is_file():
        raise RuntimeError('Final project resources are missing; reinstall the project wheel')
    return installed
