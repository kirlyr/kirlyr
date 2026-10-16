"""Offline validation for SVG animations and READMEs."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "chess_replay.py"
spec = importlib.util.spec_from_file_location("chess_replay", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ChessReplayTests(unittest.TestCase):
    def test_svg_has_valid_xml_move_frames_and_animation(self):
        states, meta = mod.demo_game("kirlur")
        text = mod.render_svg(states, meta)
        root = ET.fromstring(text)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(text.count('class="frame frame-'), 7)
        self.assertIn("@keyframes slide-1", text)
        self.assertIn("infinite", text)
        self.assertIn("DEMO ONLY", text)

    def test_flipped_coordinates(self):
        self.assertEqual(mod.square_xy('a1', False), (65, 670))
        self.assertEqual(mod.square_xy('a1', True), (597, 138))

    def test_readme_link_updates_only_marked_section(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'README.md'
            path.write_text('Top\n<!-- chess-replay:start -->\nold\n<!-- chess-replay:end -->\nBottom', encoding='utf-8')
            states, meta = mod.demo_game('kirlur')
            meta['username'] = 'kirlur'
            meta['game_url'] = 'https://www.chess.com/game/live/123456'
            self.assertTrue(mod.replace_readme_block(path, meta))
            self.assertIn('Top\n', path.read_text())
            self.assertIn('\nBottom', path.read_text())
            self.assertIn('https://www.chess.com/game/live/123456', path.read_text())
            self.assertFalse(mod.replace_readme_block(path, meta))


if __name__ == '__main__':
    unittest.main()
