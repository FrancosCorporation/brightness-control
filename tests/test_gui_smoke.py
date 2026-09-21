import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from importlib.machinery import SourceFileLoader
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'brightness-gui')

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import GLib
    GTK_AVAILABLE = True
except Exception:
    GLib = None
    GTK_AVAILABLE = False


def pump_until(predicate, timeout=3.0):
    deadline = time.time() + timeout
    context = GLib.MainContext.default()
    while time.time() < deadline:
        while context.iteration(False):
            pass
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError('timeout esperando condicao')


@unittest.skipUnless(GTK_AVAILABLE, 'GTK/gi indisponivel')
@unittest.skipUnless(os.environ.get('DISPLAY'), 'sem DISPLAY (rode com xvfb-run)')
class GuiSmokeTests(unittest.TestCase):
    """Fluxo completo da janela com ddcutil/xrandr mockados."""

    @classmethod
    def setUpClass(cls):
        loader = SourceFileLoader('brightness_gui_real', SCRIPT)
        spec = importlib.util.spec_from_loader('brightness_gui_real', loader)
        cls.bg = importlib.util.module_from_spec(spec)
        sys.modules['brightness_gui_real'] = cls.bg
        loader.exec_module(cls.bg)

    def test_full_flow(self):
        bg = self.bg
        calls = {'hw': [], 'sw': []}
        hw = {'current': 90}

        def fake_set_hw(display, value):
            calls['hw'].append((display, value))
            return True

        def fake_set_sw(output, value):
            calls['sw'].append((output, value))
            return True

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                with mock.patch.object(bg, 'detect_displays', return_value=[1, 2]), \
                        mock.patch.object(bg, 'detect_outputs', return_value=['screen']), \
                        mock.patch.object(bg, 'read_hw_brightness',
                                          side_effect=lambda d: hw['current']), \
                        mock.patch.object(bg, 'read_sw_brightness_all',
                                          return_value={'screen': 1.0}), \
                        mock.patch.object(bg, 'set_hw_brightness',
                                          side_effect=fake_set_hw), \
                        mock.patch.object(bg, 'set_sw_brightness',
                                          side_effect=fake_set_sw), \
                        mock.patch.object(bg.Gtk, 'main_quit'):
                    app = bg.BrightnessWindow()

                    # 1) Carrega valores atuais sem escrever nada
                    pump_until(lambda: app.controls.get_sensitive())
                    self.assertAlmostEqual(app.hw_scale.get_value(), 90, places=2)
                    self.assertAlmostEqual(app.sw_scale.get_value(), 1.0, places=2)
                    self.assertEqual(app.original_hw, {1: 90, 2: 90})
                    self.assertEqual(calls, {'hw': [], 'sw': []})

                    # 2) Hardware aplica nos dois monitores
                    app.hw_scale.set_value(85)
                    pump_until(lambda: (1, 85) in calls['hw'] and (2, 85) in calls['hw'])

                    # 3) Software aplica no release
                    app.sw_scale.set_value(0.5)
                    app.on_sw_release(app.sw_scale, None)
                    pump_until(lambda: ('screen', 0.5) in calls['sw'])

                    # 4) OK persiste a configuracao
                    app.on_ok(None)
                    pump_until(lambda: os.path.isfile(
                        os.path.join(tmp, 'brightness-control', 'config.json')))
                    with open(os.path.join(tmp, 'brightness-control',
                                           'config.json')) as handle:
                        self.assertEqual(json.load(handle), {'hw': 85, 'sw': 0.5})

                    # 5) Cancelar restaura os originais de forma sincrona
                    calls['hw'].clear()
                    calls['sw'].clear()
                    hw['current'] = 70
                    app2 = bg.BrightnessWindow()
                    pump_until(lambda: app2.controls.get_sensitive())
                    app2.hw_scale.set_value(30)
                    pump_until(lambda: (1, 30) in calls['hw'] and (2, 30) in calls['hw'])
                    calls['hw'].clear()
                    app2.on_cancel(None)
                    pump_until(lambda: calls['hw'] == [(1, 70), (2, 70)])
                    self.assertEqual(calls['sw'], [])


if __name__ == '__main__':
    unittest.main()
