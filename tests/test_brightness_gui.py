import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from importlib.machinery import SourceFileLoader
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'brightness-gui')


def load_module():
    """Carrega brightness-gui com um stub de gi (sem precisar de GTK)."""
    if 'brightness_gui' in sys.modules:
        return sys.modules['brightness_gui']
    gi = types.ModuleType('gi')
    gi.require_version = lambda *args, **kwargs: None
    repository = types.ModuleType('gi.repository')
    for name in ('Gtk', 'GLib'):
        setattr(repository, name, type(name, (), {}))
    gi.repository = repository
    saved = {name: sys.modules.get(name) for name in ('gi', 'gi.repository')}
    sys.modules['gi'] = gi
    sys.modules['gi.repository'] = repository
    try:
        loader = SourceFileLoader('brightness_gui', SCRIPT)
        spec = importlib.util.spec_from_loader('brightness_gui', loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules['brightness_gui'] = module
        loader.exec_module(module)
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return module


bg = load_module()


class DdcutilParserTests(unittest.TestCase):
    def test_detect_terse(self):
        stdout = (
            "Display 1\n"
            "   I2C bus:        /dev/i2c-4\n"
            "   DRM connector:  card0-HDMI-A-1\n"
            "   Monitor:        DEL:DELL U2415:ABCDEF12\n"
            "Display 2\n"
            "   I2C bus:        /dev/i2c-6\n"
        )
        self.assertEqual(bg.parse_ddcutil_displays(stdout), [1, 2])

    def test_detect_empty(self):
        self.assertEqual(bg.parse_ddcutil_displays(""), [])

    def test_getvcp_brightness(self):
        stdout = ("VCP code 0x10 (Brightness                    ): "
                  "current value =    50, max value =   100\n")
        self.assertEqual(bg.parse_ddcutil_brightness(stdout), 50)

    def test_getvcp_unreadable(self):
        self.assertIsNone(bg.parse_ddcutil_brightness("Display not found\n"))


class XrandrParserTests(unittest.TestCase):
    OUTPUTS = (
        "Screen 0: minimum 320 x 200, current 1920 x 1080, maximum 16384 x 16384\n"
        "eDP-1 connected primary 1920x1080+0+0 (normal left inverted right) 344mm x 194mm\n"
        "HDMI-1 disconnected (normal left inverted right)\n"
        "DP-1 connected 1920x1080+1920+0 (normal left inverted right) 527mm x 296mm\n"
    )

    def test_detect_outputs(self):
        self.assertEqual(bg.parse_xrandr_outputs(self.OUTPUTS), ['eDP-1', 'DP-1'])

    def test_parse_brightness(self):
        stdout = (
            "Screen 0: minimum 320 x 200, current 1920 x 1080, maximum 16384 x 16384\n"
            "eDP-1 connected primary 1920x1080+0+0 (normal left inverted right) 344mm x 194mm\n"
            "\tBrightness: 0.850000\n"
            "\tGamma:      1.0:1.0:1.0\n"
            "HDMI-1 disconnected (normal left inverted right)\n"
            "DP-1 connected 1920x1080+1920+0 (normal left inverted right) 527mm x 296mm\n"
            "\tBrightness: 0.500000\n"
        )
        self.assertEqual(
            bg.parse_xrandr_brightness(stdout),
            {'eDP-1': 0.85, 'DP-1': 0.5})
        self.assertEqual(bg.parse_xrandr_brightness(stdout, 'eDP-1'), 0.85)
        self.assertIsNone(bg.parse_xrandr_brightness(stdout, 'VGA-1'))

    def test_no_connected_outputs(self):
        self.assertEqual(bg.parse_xrandr_outputs("HDMI-1 disconnected\n"), [])


class ClampTests(unittest.TestCase):
    def test_clamp_hw(self):
        self.assertEqual(bg.clamp_hw(-10), 0)
        self.assertEqual(bg.clamp_hw(150), 100)
        self.assertEqual(bg.clamp_hw('70'), 70)

    def test_clamp_sw(self):
        self.assertEqual(bg.clamp_sw(0), bg.SW_MIN)
        self.assertEqual(bg.clamp_sw(2), bg.SW_MAX)
        self.assertEqual(bg.clamp_sw('0.5'), 0.5)


class ConfigTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                self.assertEqual(bg.load_config(), {})
                bg.save_config({'hw': 30})
                bg.save_config({'sw': 0.4})
                self.assertEqual(bg.load_config(), {'hw': 30, 'sw': 0.4})
                self.assertTrue(
                    os.path.isfile(os.path.join(
                        tmp, 'brightness-control', 'config.json')))

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'brightness-control')
            os.makedirs(path)
            with open(os.path.join(path, 'config.json'), 'w') as handle:
                handle.write('{invalid')
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                self.assertEqual(bg.load_config(), {})

    def test_non_dict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'brightness-control')
            os.makedirs(path)
            with open(os.path.join(path, 'config.json'), 'w') as handle:
                json.dump([1, 2], handle)
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                self.assertEqual(bg.load_config(), {})


class CliActionTests(unittest.TestCase):
    def test_adjust_hw_without_displays(self):
        with mock.patch.object(bg, 'detect_displays', return_value=[]):
            self.assertEqual(bg.run_adjust_hw(10), 1)

    def test_adjust_hw_applies_and_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                with mock.patch.object(bg, 'detect_displays', return_value=[1]):
                    with mock.patch.object(
                            bg, 'read_hw_brightness', return_value=40):
                        with mock.patch.object(
                                bg, 'set_hw_brightness', return_value=True) as setter:
                            self.assertEqual(bg.run_adjust_hw(10), 0)
                self.assertEqual(bg.load_config(), {'hw': 50})
                setter.assert_called_once_with(1, 50)

    def test_adjust_hw_clamps_to_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                with mock.patch.object(bg, 'detect_displays', return_value=[1]):
                    with mock.patch.object(
                            bg, 'read_hw_brightness', return_value=95):
                        with mock.patch.object(
                                bg, 'set_hw_brightness', return_value=True):
                            self.assertEqual(bg.run_adjust_hw(20), 0)
                self.assertEqual(bg.load_config(), {'hw': 100})

    def test_toggle_sw_without_outputs(self):
        with mock.patch.object(bg, 'detect_outputs', return_value=[]):
            self.assertEqual(bg.run_toggle_sw(), 1)

    def test_toggle_sw_alternates(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                with mock.patch.object(bg, 'detect_outputs', return_value=['eDP-1']):
                    with mock.patch.object(
                            bg, 'read_sw_brightness_all',
                            return_value={'eDP-1': 1.0}):
                        with mock.patch.object(
                                bg, 'set_sw_brightness', return_value=True) as setter:
                            self.assertEqual(bg.run_toggle_sw(), 0)
                            setter.assert_called_with('eDP-1', bg.SW_DIM_DEFAULT)
                self.assertEqual(bg.load_config(),
                                 {'sw': bg.SW_DIM_DEFAULT,
                                  'sw_toggle': bg.SW_DIM_DEFAULT})

    def test_restore_last_without_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                self.assertEqual(bg.run_restore_last(), 1)

    def test_restore_last_applies_saved_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp}):
                bg.save_config({'hw': 35, 'sw': 0.6})
                with mock.patch.object(bg, 'detect_displays', return_value=[1, 2]):
                    with mock.patch.object(bg, 'detect_outputs', return_value=['eDP-1']):
                        with mock.patch.object(
                                bg, 'set_hw_brightness', return_value=True) as hw:
                            with mock.patch.object(
                                    bg, 'set_sw_brightness', return_value=True) as sw:
                                self.assertEqual(bg.run_restore_last(), 0)
                self.assertEqual(hw.call_count, 2)
                sw.assert_called_once_with('eDP-1', 0.6)


if __name__ == '__main__':
    unittest.main()
