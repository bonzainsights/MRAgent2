"""
MRAgent — File Manager Tool
Read, write, list, move, and delete files.

Created: 2026-02-15
"""

import os
import shutil
from pathlib import Path

from tools.base import Tool
from utils.helpers import format_file_size

# Max file size to read (to avoid loading huge files into context)
MAX_READ_SIZE = 100_000  # ~100KB


class ReadFileTool(Tool):
    """Read the contents of a file."""

    name = "read_file"
    description = (
        "Read the contents of a file. Returns the file text with line numbers. "
        "For large files, returns only the first ~100KB."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional start line (1-indexed)",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional end line (1-indexed, inclusive)",
            },
        },
        "required": ["path"],
    }

    def execute(self, path: str, start_line: int = None,
                end_line: int = None) -> str:
        filepath = Path(path).expanduser().resolve()

        if not filepath.exists():
            return f"❌ File not found: {filepath}"
        if not filepath.is_file():
            return f"❌ Not a file: {filepath}"

        size = filepath.stat().st_size
        if size > MAX_READ_SIZE:
            self.logger.warning(f"Large file ({format_file_size(size)}), truncating")

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"❌ Error reading file: {e}"

        lines = content.split("\n")
        total_lines = len(lines)

        # Apply line range
        if start_line or end_line:
            start = max(1, start_line or 1) - 1
            end = min(total_lines, end_line or total_lines)
            lines = lines[start:end]
            line_prefix = start + 1
        else:
            line_prefix = 1
            if len(content) > MAX_READ_SIZE:
                content = content[:MAX_READ_SIZE]
                lines = content.split("\n")

        # Add line numbers
        numbered = [f"{i + line_prefix:4d} | {line}" for i, line in enumerate(lines)]

        header = f"📄 {filepath} ({total_lines} lines, {format_file_size(size)})"
        return header + "\n" + "\n".join(numbered)


class WriteFileTool(Tool):
    """Write content to a file."""

    name = "write_file"
    description = (
        "Write content to a file. Creates the file and any parent directories "
        "if they don't exist. Overwrites existing content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    }

    def execute(self, path: str, content: str) -> str:
        filepath = Path(path).expanduser().resolve()

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
            size = filepath.stat().st_size
            return f"✅ Written {format_file_size(size)} to {filepath}"
        except Exception as e:
            return f"❌ Error writing file: {e}"


class ListDirectoryTool(Tool):
    """List files and directories in a path."""

    name = "list_directory"
    description = (
        "List files and subdirectories in a directory. "
        "Shows file sizes and types. Like 'ls -la'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to list",
            },
            "recursive": {
                "type": "boolean",
                "description": "If true, list recursively (tree view). Default: false",
            },
            "max_depth": {
                "type": "integer",
                "description": "Max depth for recursive listing (default: 3)",
            },
        },
        "required": ["path"],
    }

    def execute(self, path: str, recursive: bool = False,
                max_depth: int = 3) -> str:
        dirpath = Path(path).expanduser().resolve()

        if not dirpath.exists():
            return f"❌ Directory not found: {dirpath}"
        if not dirpath.is_dir():
            return f"❌ Not a directory: {dirpath}"

        try:
            if recursive:
                return self._tree(dirpath, max_depth=max_depth)
            else:
                return self._flat_list(dirpath)
        except PermissionError:
            return f"❌ Permission denied: {dirpath}"

    def _flat_list(self, dirpath: Path) -> str:
        entries = sorted(dirpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = [f"📁 {dirpath}\n"]

        for entry in entries[:100]:  # Cap at 100 entries
            if entry.is_dir():
                count = sum(1 for _ in entry.iterdir()) if entry.exists() else 0
                lines.append(f"  📂 {entry.name}/ ({count} items)")
            else:
                size = format_file_size(entry.stat().st_size)
                lines.append(f"  📄 {entry.name} ({size})")

        if len(list(dirpath.iterdir())) > 100:
            lines.append(f"  ... and {len(list(dirpath.iterdir())) - 100} more")

        return "\n".join(lines)

    def _tree(self, dirpath: Path, prefix: str = "", depth: int = 0,
              max_depth: int = 3) -> str:
        if depth > max_depth:
            return ""

        entries = sorted(dirpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = []

        if depth == 0:
            lines.append(f"📁 {dirpath}")

        for i, entry in enumerate(entries[:50]):
            is_last = (i == len(entries) - 1) or (i == 49)
            connector = "└── " if is_last else "├── "
            new_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                lines.append(f"{prefix}{connector}📂 {entry.name}/")
                subtree = self._tree(entry, new_prefix, depth + 1, max_depth)
                if subtree:
                    lines.append(subtree)
            else:
                size = format_file_size(entry.stat().st_size)
                lines.append(f"{prefix}{connector}📄 {entry.name} ({size})")

        return "\n".join(lines)


class MoveFileTool(Tool):
    """Move or rename a file or directory."""

    name = "move_file"
    description = "Move or rename a file or directory."
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path"},
            "destination": {"type": "string", "description": "Destination path"},
        },
        "required": ["source", "destination"],
    }

    def execute(self, source: str, destination: str) -> str:
        src = Path(source).expanduser().resolve()
        dst = Path(destination).expanduser().resolve()

        if not src.exists():
            return f"❌ Source not found: {src}"

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"✅ Moved: {src} → {dst}"
        except Exception as e:
            return f"❌ Error moving: {e}"


class DeleteFileTool(Tool):
    """Delete a file or empty directory."""

    name = "delete_file"
    description = "Delete a file. For safety, does not delete non-empty directories."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to delete"},
        },
        "required": ["path"],
    }

    def execute(self, path: str) -> str:
        filepath = Path(path).expanduser().resolve()

        if not filepath.exists():
            return f"❌ Not found: {filepath}"

        try:
            if filepath.is_file():
                filepath.unlink()
                return f"✅ Deleted file: {filepath}"
            elif filepath.is_dir():
                if any(filepath.iterdir()):
                    return f"⚠️ Directory not empty: {filepath}. Use terminal for rm -r."
                filepath.rmdir()
                return f"✅ Deleted empty directory: {filepath}"
        except Exception as e:
            return f"❌ Error deleting: {e}"
