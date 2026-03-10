from __future__ import annotations

import unittest

from mcfind.chatgpt import _extract_cloudflare_url


class ChatgptHelperTests(unittest.TestCase):
    def test_extract_cloudflare_url_from_log_line(self) -> None:
        line = "INF | +--------------------------------------------------------------------------------------------+ https://deaf-telling-puts-few.trycloudflare.com"
        self.assertEqual(
            _extract_cloudflare_url(line),
            "https://deaf-telling-puts-few.trycloudflare.com",
        )

    def test_extract_cloudflare_url_returns_none_when_missing(self) -> None:
        self.assertIsNone(_extract_cloudflare_url("no public url here"))
