"""
MRAgent — Code Runner Tool
Execute Python/JS/Bash code in a sandboxed subprocess.

Created: 2026-02-15
"""

import os
import tempfile
import subprocess
from pathlib import Path

from tools.base import Tool

MAX_OUTPUT = 8000


class CodeRunnerTool(Tool):
    """Execute code snippets in a sandboxed subprocess."""

    name = "run_code"
    description = (
        "Execute a code snippet in a subprocess. Supports Python, JavaScript (Node.js), "
        "and Bash. Returns stdout/stderr. Use for testing code, running calculations, "
        "or validating logic."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The code to execute",
            },
            "language": {
                "type": "string",
                "enum": ["python", "javascript", "bash"],
                "description": "Programming language (default: python)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 15)",
            },
        },
        "required": ["code"],
    }

    # Map language → (file extension, interpreter command)
    RUNNERS = {
        "python": (".py", ["python3"]),
        "javascript": (".js", ["node"]),
        "bash": (".sh", ["bash"]),
    }

    def execute(self, code: str, language: str = "python",
                timeout: int = 15) -> str:
        if language not in self.RUNNERS:
            return f"❌ Unsupported language: {language}. Use: {list(self.RUNNERS.keys())}"

        ext, interpreter = self.RUNNERS[language]

        # Write code to temp file
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=ext, delete=False, dir=tempfile.gettempdir()
            ) as f:
                f.write(code)
                temp_path = f.name
        except Exception as e:
            return f"❌ Error creating temp file: {e}"

        self.logger.info(f"Running {language} code ({len(code)} chars, timeout={timeout}s)")

        try:
            result = subprocess.run(
                interpreter + [temp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir(),
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\n--- stderr ---\n"
                output += result.stderr

            if len(output) > MAX_OUTPUT:
                output = output[:MAX_OUTPUT] + f"\n... (truncated)"

            if result.returncode != 0:
                output = f"Exit code: {result.returncode}\n{output}"

            return output.strip() or "(no output)"

        except subprocess.TimeoutExpired:
            return f"⏰ Code timed out after {timeout}s"
        except FileNotFoundError:
            return f"❌ Interpreter not found: {interpreter[0]}"
        except Exception as e:
            return f"❌ Error running code: {e}"
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass
