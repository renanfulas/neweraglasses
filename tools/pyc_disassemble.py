from __future__ import annotations

import argparse
import dis
import io
import marshal
from datetime import UTC, datetime
from pathlib import Path
from types import CodeType


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Disassemble a Python 3.12 .pyc file using the standard library."
    )
    parser.add_argument("pyc_path", help="Path to the .pyc file to disassemble.")
    parser.add_argument(
        "--output",
        help="Optional output file. If omitted, writes to stdout.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=8,
        help="Maximum nested code-object depth to print. Defaults to 8.",
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


def emit_header(
    *,
    output: io.StringIO,
    path: Path,
    code: CodeType,
    compiled_at_raw: int | None,
    source_size: int | None,
) -> None:
    output.write(f"# pyc_path: {path.as_posix()}\n")
    output.write(f"# embedded_filename: {code.co_filename}\n")
    output.write(f"# module_name: {module_name_from_embedded_filename(code.co_filename)}\n")
    output.write(f"# first_line: {code.co_firstlineno}\n")
    if compiled_at_raw is not None:
        compiled_at = datetime.fromtimestamp(compiled_at_raw, tz=UTC).isoformat()
        output.write(f"# compiled_at: {compiled_at}\n")
    if source_size is not None:
        output.write(f"# source_size: {source_size}\n")
    output.write("\n")


def module_name_from_embedded_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    if "/src/" in normalized:
        relative = normalized.split("/src/", 1)[1]
    elif "/tests/" in normalized:
        relative = normalized.split("/tests/", 1)[1]
    else:
        relative = normalized
    return relative.removesuffix(".py").replace("/", ".")


def emit_code_object(
    code: CodeType,
    *,
    output: io.StringIO,
    depth: int,
    max_depth: int,
) -> None:
    indent = "  " * depth
    output.write(f"{indent}## code_object: {code.co_name}\n")
    output.write(f"{indent}filename: {code.co_filename}\n")
    output.write(f"{indent}first_line: {code.co_firstlineno}\n")
    output.write(f"{indent}argcount: {code.co_argcount}\n")
    output.write(f"{indent}locals: {code.co_nlocals}\n")
    output.write(f"{indent}stacksize: {code.co_stacksize}\n")
    output.write(f"{indent}flags: {code.co_flags}\n")
    output.write(f"{indent}names: {list(code.co_names)}\n")
    output.write(f"{indent}varnames: {list(code.co_varnames)}\n")
    output.write(f"{indent}cellvars: {list(code.co_cellvars)}\n")
    output.write(f"{indent}freevars: {list(code.co_freevars)}\n")
    output.write(f"{indent}disassembly:\n")

    dis_buffer = io.StringIO()
    dis.dis(code, file=dis_buffer)
    for line in dis_buffer.getvalue().splitlines():
        output.write(f"{indent}{line}\n")
    output.write("\n")

    if depth >= max_depth:
        return

    for const in code.co_consts:
        if isinstance(const, CodeType):
            emit_code_object(const, output=output, depth=depth + 1, max_depth=max_depth)


def main() -> int:
    args = parse_args()
    path = Path(args.pyc_path).resolve()
    code, compiled_at_raw, source_size = read_pyc_code_object(path)
    output = io.StringIO()
    emit_header(
        output=output,
        path=path,
        code=code,
        compiled_at_raw=compiled_at_raw,
        source_size=source_size,
    )
    emit_code_object(code, output=output, depth=0, max_depth=args.max_depth)
    rendered = output.getvalue()

    if args.output:
        destination = Path(args.output).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
