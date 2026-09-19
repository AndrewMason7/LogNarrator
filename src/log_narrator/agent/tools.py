import itertools
from collections.abc import Callable
from pathlib import Path


def create_code_inspection_tool(
    code_root: Path,
    inspected_files: set[str] | list[str] | None = None,
) -> Callable[[str, int, int], str]:
    resolved_root = code_root.resolve()

    def view_source_code(file_path: str, start_line: int = 1, end_line: int = 50) -> str:
        """Inspects source code files around a line cited in a stack trace or error log.

        Args:
            file_path: Relative or container path to the source code file within the project codebase.
            start_line: Starting line number to view (1-indexed, default 1).
            end_line: Ending line number to view (inclusive, maximum 200 lines per call).

        Returns:
            Formatted source code snippet with line numbers, or an error message if inaccessible.
        """
        try:
            clean_path = file_path.lstrip("/\\")
            parts = Path(clean_path).parts
            target = None

            # Iteratively attempt suffix matching to map container paths (e.g. /app/services/billing.py -> services/billing.py)
            for i in range(len(parts)):
                candidate = (resolved_root / Path(*parts[i:])).resolve()
                if candidate.is_relative_to(resolved_root) and candidate.is_file():
                    target = candidate
                    break

            if target is None:
                target = (resolved_root / clean_path).resolve()

            # Prevent directory traversal escapes outside root
            if not target.is_relative_to(resolved_root):
                return f"Error: Access denied. Cannot inspect files outside {resolved_root}"
            # Ensure target is a regular file, not a FIFO, socket, or device
            if not target.is_file() or target.is_fifo() or target.is_socket():
                return f"Error: Target '{file_path}' is not a valid regular file."

            # Safety guard: cap maximum file inspection size to 10MB
            stat = target.stat()
            if stat.st_size > 10 * 1024 * 1024:
                return f"Error: File '{file_path}' ({stat.st_size / (1024 * 1024):.1f}MB) exceeds safety limit of 10MB."

            # Track successfully inspected file
            if inspected_files is not None:
                rel_path = str(target.relative_to(resolved_root))
                if isinstance(inspected_files, set):
                    inspected_files.add(rel_path)
                elif rel_path not in inspected_files:
                    inspected_files.append(rel_path)

            start = max(1, start_line)
            end = min(start + 200, max(start, end_line))  # Cap at max 200 lines per call

            formatted = [f"--- File: {file_path} (Lines {start}-{end}) ---"]
            # Stream lines with islice instead of loading entire file into memory
            with open(target, encoding="utf-8", errors="replace") as f:
                lines = list(itertools.islice(f, start - 1, end))
                for idx, line in enumerate(lines, start=start):
                    formatted.append(f"{idx:4d} | {line.rstrip()}")
            return "\n".join(formatted)
        except Exception as e:
            return f"Error inspecting file '{file_path}': {e}"

    return view_source_code
