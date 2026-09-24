"""Keep every test's page store inside its own tmp directory.

キャッシュの既定の置き場は利用者のキャッシュ配下なので、何も指定しないテストは
実際の ~/.cache に書き込んでしまう。全テストで置き場を tmp に向けておく。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
