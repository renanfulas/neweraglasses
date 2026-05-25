from __future__ import annotations

import argparse
import json
import marshal
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import CodeType


@dataclass(slots=True)
class PycInventoryRecord:
    pyc_path: str
    embedded_filename: str
    module_name: str
    first_line: int
    compiled_at: str | None
    source_size: int | None
    names: list[str]
    constant_code_objects: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory Python 3.12 .pyc files for source recovery work."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output.",
    )
    return parser.parse_args()


def read_pyc_code_object(path: Path) -> tuple[CodeType, int | None, int | None]:
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"{path} is too small to be a valid pyc file")
    flags = int.from_bytes(data[4:8], "little")
    if flags & 0x01:
        compiled_at = None
        source_size = None
    else:
        compiled_at = int.from_bytes(data[8:12], "little")
        source_size = int.from_bytes(data[12:16], "little")
    code = marshal.loads(data[16:])
    if not isinstance(code, CodeType):
        raise ValueError(f"{path} does not contain a module code object")
    return code, compiled_at, source_size


def iter_pyc_files(root: Path) -> list[Path]:
    return sorted(root.glob("src/**/*.pyc")) + sorted(root.glob("tests/**/*.pyc"))


def module_name_from_embedded_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    if "/src/" in normalized:
        relative = normalized.split("/src/", 1)[1]
    elif "/tests/" in normalized:
        relative = normalized.split("/tests/", 1)[1]
    else:
        relative = normalized
    return relative.removesuffix(".py").replace("/", ".")


def inventory_pyc(path: Path) -> PycInventoryRecord:
    code, compiled_at_raw, source_size = read_pyc_code_object(path)
    compiled_at = None
    if compiled_at_raw is not None:
        compiled_at = datetime.fromtimestamp(compiled_at_raw, tz=UTC).isoformat()
    constant_code_objects = [
        const.co_name for const in code.co_consts if isinstance(const, CodeType)
    ]
    return PycInventoryRecord(
        pyc_path=str(path.as_posix()),
        embedded_filename=code.co_filename,
        module_name=module_name_from_embedded_filename(code.co_filename),
        first_line=code.co_firstlineno,
        compiled_at=compiled_at,
        source_size=source_size,
        names=list(code.co_names),
        constant_code_objects=constant_code_objects,
    )


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    records = [asdict(inventory_pyc(path)) for path in iter_pyc_files(root)]
    indent = 2 if args.pretty else None
    print(json.dumps(records, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
