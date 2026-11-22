# Third-Party Notices

What this repository uses at run time, at the versions `uv.lock` holds, and what it carries from others.

## Run-time dependencies

Installed with the toolkit, not copied into this repository.

| package | version | license | source |
|---|---|---|---|
| python-pptx | 1.0.2 | MIT | https://github.com/scanny/python-pptx |
| lxml | 6.1.3 | BSD-3-Clause | https://lxml.de/ |
| Pillow | 13.0.0 | MIT-CMU | https://github.com/python-pillow/Pillow |
| XlsxWriter | 3.2.9 | BSD-2-Clause | https://github.com/jmcnamara/XlsxWriter |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |

## Carried in this repository

| what | from | license |
|---|---|---|
| The specimen deck of the project template (`specimen.pptx`) | the default template of python-pptx, changed | MIT, in [`third_party/python-pptx/LICENSE`](third_party/python-pptx/LICENSE) |

## Called, not carried

LibreOffice (MPL-2.0) and poppler (GPL) run as separate programs that the person installs.
