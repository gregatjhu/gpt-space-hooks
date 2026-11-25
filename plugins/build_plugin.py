#!/usr/bin/env python3
"""Build the skills-only plugin from its reviewed source files."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


PLUGIN = "gpt-space-hooks"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
FILES = (
    "LICENSE",
    "plugin.json",
    "skills/space-checkpoint/SKILL.md",
    "skills/space-task-handoff/SKILL.md",
)


def build(source: Path, output_dir: Path) -> Path:
    if source.is_symlink():
        raise ValueError(f"symlinks are excluded: {source}")
    files = {}
    for name in sorted(FILES):
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid archive path: {name}")
        path = source
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise ValueError(f"symlinks are excluded: {path}")
        if not path.is_file():
            raise ValueError(f"expected a plugin source file: {path}")
        files[name] = path.read_bytes()

    manifest = json.loads(files["plugin.json"])
    if not isinstance(manifest, dict):
        raise ValueError("expected a JSON object in plugin.json")
    version = manifest.get("version")
    if manifest.get("$schema") != SCHEMA or manifest.get("name") != PLUGIN:
        raise ValueError("expected the portable GPT Space Hooks manifest")
    if not isinstance(version, str) or not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("expected a release version in plugin.json (major.minor.patch)")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            entry = zipfile.ZipInfo(f"{PLUGIN}/{name}")
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{PLUGIN}-plugin-{version}.zip"
    output.write_bytes(buffer.getvalue())
    return output


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=root / "dist", help="destination for the versioned ZIP")
    args = parser.parse_args()
    try:
        output = build(root / PLUGIN, args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Plugin build failed: {error}\n")
    print(output)
    print(f"SHA-256: {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
