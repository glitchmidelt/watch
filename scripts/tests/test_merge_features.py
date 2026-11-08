"""Tests for cookies, subtitle language picking, and Whisper backend selection."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import download  # noqa: E402
import stt  # noqa: E402


CLEAN_ENV = {k: v for k, v in os.environ.items()
             if not k.startswith("WATCH_") and k not in ("GROQ_API_KEY", "OPENAI_API_KEY")}


class TestCookies(unittest.TestCase):

    def test_no_cookies_by_default(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True):
            self.assertEqual(download.cookie_args(), [])

    def test_browser_flag(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True):
            self.assertEqual(download.cookie_args("firefox"), ["--cookies-from-browser", "firefox"])

    def test_file_wins_over_browser(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f, \
                mock.patch.dict(os.environ, CLEAN_ENV, clear=True):
            args = download.cookie_args("chrome", f.name)
            self.assertEqual(args[0], "--cookies")

    def test_env_fallback(self):
        env = dict(CLEAN_ENV, WATCH_COOKIES_FROM_BROWSER="safari")
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(download.cookie_args(), ["--cookies-from-browser", "safari"])

    def test_missing_file_is_clear_error(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True):
            with self.assertRaises(SystemExit):
                download.cookie_args(None, "/nonexistent/cookies.txt")


class TestJsRuntime(unittest.TestCase):

    def test_forced_none(self):
        with mock.patch.dict(os.environ, dict(CLEAN_ENV, WATCH_JS_RUNTIME="none"), clear=True):
            self.assertEqual(download.js_runtime_args(), [])

    def test_forced_value(self):
        with mock.patch.dict(os.environ, dict(CLEAN_ENV, WATCH_JS_RUNTIME="bun"), clear=True):
            self.assertEqual(download.js_runtime_args(), ["--js-runtimes", "bun"])

    def test_deno_is_default(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True), \
                mock.patch.object(download.shutil, "which", side_effect=lambda n: "/x" if n == "deno" else None):
            self.assertEqual(download.js_runtime_args(), [])

    def test_node_when_no_deno(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True), \
                mock.patch.object(download.shutil, "which", side_effect=lambda n: "/x" if n == "node" else None), \
                mock.patch.object(download, "_ytdlp_supports", return_value=True):
            self.assertEqual(download.js_runtime_args(), ["--js-runtimes", "node"])


class TestPickSubtitle(unittest.TestCase):

    def _dir(self, names):
        d = Path(tempfile.mkdtemp())
        for n in names:
            (d / n).write_text("WEBVTT\n")
        return d

    def test_prefers_video_language_over_english_translation(self):
        d = self._dir(["video.en.vtt", "video.ar.vtt", "video.ar-orig.vtt"])
        self.assertEqual(download._pick_subtitle(d, "ar").name, "video.ar.vtt")

    def test_orig_track_when_language_unknown(self):
        d = self._dir(["video.en.vtt", "video.fr-orig.vtt"])
        self.assertEqual(download._pick_subtitle(d, None).name, "video.fr-orig.vtt")

    def test_english_fallback(self):
        d = self._dir(["video.de.vtt", "video.en-US.vtt"])
        self.assertEqual(download._pick_subtitle(d, None).name, "video.en-US.vtt")

    def test_none_when_empty(self):
        self.assertIsNone(download._pick_subtitle(self._dir([]), "en"))


class TestPickBackend(unittest.TestCase):

    def setUp(self):
        # Keep tests independent of ~/.config/watch/.env and the cwd.
        self._home = tempfile.mkdtemp()
        self._patches = [
            mock.patch.object(stt.Path, "home", return_value=Path(self._home)),
            mock.patch.object(stt.Path, "cwd", return_value=Path(self._home)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_api_key_wins(self):
        env = dict(CLEAN_ENV, GROQ_API_KEY="gsk_test")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(stt, "_local_available", return_value=True):
            self.assertEqual(stt.pick_backend(), ("groq", "gsk_test"))

    def test_local_when_no_key(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True), \
                mock.patch.object(stt, "_local_available", side_effect=lambda b: b == "local"):
            self.assertEqual(stt.pick_backend(), ("local", None))

    def test_nothing_available(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True), \
                mock.patch.object(stt, "_local_available", return_value=False):
            self.assertEqual(stt.pick_backend(), (None, None))

    def test_forced_backend_via_env(self):
        env = dict(CLEAN_ENV, GROQ_API_KEY="gsk_test", WATCH_WHISPER="local")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(stt, "_local_available", return_value=True):
            self.assertEqual(stt.pick_backend(), ("local", None))

    def test_unknown_backend_rejected(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True):
            with self.assertRaises(SystemExit):
                stt.pick_backend("nope")

    def test_config_file_fills_watch_vars_only(self):
        cfg = Path(self._home) / ".config" / "watch"
        cfg.mkdir(parents=True)
        (cfg / ".env").write_text(
            "GROQ_API_KEY=gsk_secret\nWATCH_COOKIES_FROM_BROWSER='firefox'\n"
            "# WATCH_WHISPER=local\nWATCH_WHISPER_MODEL=small\n"
        )
        env = dict(CLEAN_ENV, WATCH_WHISPER_MODEL="medium")
        with mock.patch.dict(os.environ, env, clear=True):
            stt.load_config_defaults()
            self.assertEqual(os.environ["WATCH_COOKIES_FROM_BROWSER"], "firefox")
            self.assertEqual(os.environ["WATCH_WHISPER_MODEL"], "medium")  # real env wins
            self.assertNotIn("WATCH_WHISPER", os.environ)  # commented out
            self.assertNotIn("GROQ_API_KEY", os.environ)  # keys never exported

    def test_local_words_flattened(self):
        fake = mock.MagicMock()
        fake.load_model.return_value.transcribe.return_value = {
            "text": "salam",
            "segments": [{"start": 0.0, "end": 1.0, "text": "salam",
                          "words": [{"word": " salam", "start": 0.1, "end": 0.6}]}],
        }
        with mock.patch.dict(sys.modules, {"whisper": fake}), \
                mock.patch.dict(os.environ, CLEAN_ENV, clear=True):
            out = stt._local_transcribe(Path("a.mp3"), "local", word_timestamps=True)
        self.assertEqual(out["words"][0]["word"], " salam")
        self.assertEqual(stt._segments_from_response(out)[0]["text"], "salam")


if __name__ == "__main__":
    unittest.main()
