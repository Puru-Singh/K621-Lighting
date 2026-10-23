"""Explicit hardware smoke: hidden Tk window, real Apply path, temporary settings.

Run manually with a wired original K621 attached. This applies #00FF00.
It does not control other applications or take over the desktop.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from k621_rgb.gui import App
from k621_rgb.service import Settings


def settle(root, app):
    deadline = time.monotonic() + 17
    while app.busy and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    if app.busy:
        raise AssertionError('GUI worker did not finish')


with tempfile.TemporaryDirectory(prefix='k621-gui-test-') as directory:
    settings = Settings(Path(directory) / 'settings.json')
    root = tk.Tk()
    root.withdraw()
    try:
        with patch('k621_rgb.gui.Settings.default', return_value=settings):
            app = App(root)
        settle(root, app)
        assert app.ready, app.status.get()
        assert str(app.apply_button['state']) == 'normal', 'Apply is not enabled'
        assert not settings.path.exists(), 'Opening the app wrote settings'
        app.color.set('#00FF00')
        app.apply()
        settle(root, app)
        assert 'applied' in app.status.get(), app.status.get()
        assert json.loads(settings.path.read_text())['color'] == '#00FF00'
        assert str(app.apply_button['state']) == 'normal'
        print('GUI -> bounded worker -> HID -> hardware readback -> settings: PASS')
        print(app.status.get())
    finally:
        root.destroy()
