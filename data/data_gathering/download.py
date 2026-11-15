#!/usr/bin/env python3
"""Download an Earthdata-protected file using an access token from .env."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    Request,
    build_opener,
)

if __package__:
    from .config import ENV_PATH, settings
else:
    from config import ENV_PATH, settings


def load_token(env_path: Path | None = None) -> str:
    """Read EARTHDATA_TOKEN; an exported environment value takes precedence."""
    token = settings(env_path).get("EARTHDATA_TOKEN")
    if not token or not token.strip():
        raise ValueError(
            f"Set EARTHDATA_TOKEN in {env_path or ENV_PATH} or your environment."
        )
    token = token.strip()
    if any(character.isspace() for character in token):
        raise ValueError("EARTHDATA_TOKEN must not contain whitespace.")
    return token


class SafeRedirectHandler(HTTPRedirectHandler):
    """Keep bearer credentials off other hosts and reject HTTPS downgrades."""

    def redirect_request(self, request, response, code, message, headers, new_url):
        if urlsplit(new_url).scheme != "https":
            raise ValueError("Refusing a redirect to a non-HTTPS URL.")
        redirected = super().redirect_request(
            request, response, code, message, headers, new_url
        )
        if (
            redirected is not None
            and urlsplit(request.full_url).netloc != urlsplit(new_url).netloc
        ):
            redirected.remove_header("Authorization")
        return redirected


def download(url: str, destination: Path, token: str) -> Path:
    """Stream a file to disk; leave no partial output if the request fails."""
    if urlsplit(url).scheme != "https":
        raise ValueError("Use an HTTPS download URL.")
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")

    opener = build_opener(SafeRedirectHandler(), HTTPCookieProcessor(CookieJar()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        request = Request(url, headers={"Authorization": f"Bearer {token}"})
        with opener.open(request, timeout=120) as response:
            if response.headers.get_content_type() == "text/html":
                raise ValueError(
                    "Server returned an HTML page instead of data. Check the URL "
                    "and authorize the data provider in your Earthdata account."
                )
            with tempfile.NamedTemporaryFile(
                dir=destination.parent, prefix=".download-", delete=False
            ) as output:
                temporary = Path(output.name)
                shutil.copyfileobj(response, output)
                length = response.headers.get("Content-Length")
                if length is not None and output.tell() != int(length):
                    raise ValueError(
                        "Response ended before the declared file size was received."
                    )
            # Exclusive creation also prevents overwriting another download.
            os.link(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Direct HTTPS file URL from a NASA data provider")
    parser.add_argument("-o", "--output", type=Path, help="Destination file path")
    args = parser.parse_args()
    filename = Path(unquote(urlsplit(args.url).path)).name
    if args.output is None and not filename:
        parser.error("This URL has no filename; provide --output.")
    destination = args.output or Path(__file__).parent / "downloads" / filename

    try:
        saved = download(args.url, destination, load_token())
    except HTTPError as error:
        print(f"Download failed: HTTP {error.code} {error.reason}", file=sys.stderr)
        return 1
    except (OSError, ValueError, URLError, EOFError) as error:
        print(f"Download failed: {error}", file=sys.stderr)
        return 1
    print(f"Saved to {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
