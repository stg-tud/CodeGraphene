"""Black-based source code formatter for CodeGraphene."""

import subprocess
import sys

from .base import BaseCleaner

# Languages that black can format. Used to skip non-Python files gracefully.
_SUPPORTED_LANGUAGES = {"python", "py"}


class BlackFormatter(BaseCleaner):
    """Runs black on Python source before it hits the parser.

    Normalizes formatting to reduce spacing, line breaks
    don't create noise in the graph. Black is idempotent — already clean
    code stays unchanged. Non-Python input is returned as-is.
    """

    name = "BlackFormatter"

    def __init__(self, language: str = "python") -> None:
        self.language = language.lower()

    def clean(self, source_code: str) -> str:
        """Format *source_code* with black and return the result.

        Returns the original source unchanged if:
        - the language is not Python, or
        - black is not installed.

        Raises:
            RuntimeError: if black is installed but exits with a non-zero
                          status code (e.g. the source is syntactically invalid).
        """
        if self.language not in _SUPPORTED_LANGUAGES:
            return source_code

        try:
            result = subprocess.run(
                [sys.executable, "-m", "black", "--quiet", "-"],
                input=source_code,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            # black is not installed — return source unchanged rather than crash.
            return source_code

        if result.returncode != 0:
            if "No module named black" in result.stderr:
                return source_code
            raise RuntimeError(
                f"black failed with exit code {result.returncode}.\n"
                f"stderr: {result.stderr.strip()}"
            )

        return result.stdout

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "name": self.name,
                "language": self.language,
                "capabilities": ["read_text", "write_text", "format_code"],
                "formatter": "black",
            }
        )
        return info
