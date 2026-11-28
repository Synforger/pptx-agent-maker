"""On macOS, LibreOffice converts with the typefaces of the machine, so Japanese is drawn in letters, not boxes.

The fontconfig inside LibreOffice for macOS looks for its settings in a folder a Mac may not have, and then
knows only the typefaces LibreOffice carries. The preview hands it a settings file naming the machine's
folders, keeps one the environment already names, and adds nothing elsewhere than macOS. The last test
converts a line of Japanese for real, where LibreOffice and poppler are installed on a Mac.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from pptx_live_preview import render
from pptx_live_preview.render import RenderError, convert_to_pdfs, soffice_bin, soffice_environment


def _on(platform: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)


def test_on_macos_the_settings_name_the_folders_of_the_machine(tmp_path, monkeypatch):
    _on("darwin", monkeypatch)
    environment = soffice_environment(tmp_path / "profile")
    settings = environment["FONTCONFIG_FILE"]
    text = open(settings, encoding="utf-8").read()
    for folder in render.MACOS_FONT_FOLDERS:
        assert f"<dir>{folder}</dir>" in text
    assert "<cachedir>" in text
    assert settings.startswith(str(tmp_path))


def test_a_settings_file_the_environment_names_is_kept(tmp_path, monkeypatch):
    _on("darwin", monkeypatch)
    monkeypatch.setenv("FONTCONFIG_FILE", "/somewhere/fonts.conf")
    environment = soffice_environment(tmp_path / "profile")
    assert environment is None or environment["FONTCONFIG_FILE"] == "/somewhere/fonts.conf"


def test_elsewhere_than_macos_nothing_is_added(tmp_path, monkeypatch):
    _on("linux", monkeypatch)
    environment = soffice_environment(tmp_path / "profile")
    assert environment is None or "FONTCONFIG_FILE" not in environment


def _can_convert_here() -> bool:
    if sys.platform != "darwin" or shutil.which("pdffonts") is None:
        return False
    try:
        soffice_bin()
    except RenderError:
        return False
    return True


@pytest.mark.skipif(not _can_convert_here(), reason="LibreOffice and poppler on a Mac are needed")
def test_a_line_of_japanese_is_drawn_in_a_japanese_typeface(tmp_path, monkeypatch):
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    line = tmp_path / "line.txt"
    line.write_text("日本語の一行\n", encoding="utf-8")
    pdf = convert_to_pdfs([line], tmp_path / "out", tmp_path / "profile")[0]
    fonts = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=True).stdout
    assert "Hira" in fonts, fonts
