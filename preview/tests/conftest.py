"""Keep every test's page store inside its own tmp directory.

キャッシュの既定の置き場は利用者のキャッシュ配下なので、何も指定しないテストは
実際の ~/.cache に書き込んでしまう。全テストで置き場を tmp に向けておく。
"""

from __future__ import annotations

import sys

import pytest

from pptx_live_preview.render import fontconfig_file


@pytest.fixture(scope="session")
def shared_fontconfig(tmp_path_factory):
    """One fontconfig settings file for the whole run on macOS, so the list of typefaces is built once, not per test."""
    if sys.platform != "darwin":
        return None
    return str(fontconfig_file(tmp_path_factory.mktemp("fontconfig")))


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch, shared_fontconfig):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    if shared_fontconfig is not None:
        monkeypatch.setenv("FONTCONFIG_FILE", shared_fontconfig)
