# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "gitpython",
#   "packaging",
#   "typer",
#   "rich",
# ]
# ///
"""
Release tool.
Update version number, generate changelog, and create git tag.

Usage:
    python -m scripts.release patch [--dry-run] [--push]
    python -m scripts.release minor [--dry-run] [--push]
    python -m scripts.release major [--dry-run] [--push]

    -d, --dry-run: Dry run. Does not make any changes
    -p, --push: Push changes to remote

Dependencies:
    - gitpython
    - packaging
    - typer
    - rich
"""

import platform
import re
import shlex
import subprocess
import sys
import tomllib  # python 3.12+
from enum import Enum
from pathlib import Path
from typing import Annotated

import git
import packaging.version
import typer
from rich import print

ROOT_DIR = Path(__file__).absolute().parents[1]
PYPROJECT_FILE = ROOT_DIR / "pyproject.toml"
BLENDER_MANIFEST_FILE = ROOT_DIR / "animoxtend" / "blender_manifest.toml"
INIT_FILE = ROOT_DIR / "animoxtend" / "__init__.py"
CHANGELOG_FILE = ROOT_DIR / "CHANGELOG.md"

# This commit won't be shown in `CHANGELOG.md`, as configured in `cliff.toml`
COMMIT_MSG = "chore(release): prepare for {version} ({type} version)"


app = typer.Typer()


class ReleaseType(str, Enum):
    major = "major"
    minor = "minor"
    patch = "patch"


DryRun = Annotated[bool, typer.Option(help="Dry run. Does not make any changes")]
Push = Annotated[bool, typer.Option(help="Push changes to remote")]


@app.callback()
def callback():
    """
    Release tool.
    Update version number and create git tag.
    """


@app.command()
def patch(dry_run: DryRun = False, push: Push = True):
    """Update patch version.
    e.g. "x.x.1" -> "x.x.2"

    Args:
        dry_run (DryRun, optional): Dry run. Defaults to False.
        push (bool, optional): Push changes to remote. Defaults to True.
    """
    _release(ReleaseType.patch, dry_run, push)


@app.command()
def minor(dry_run: DryRun = False, push: Push = True):
    """Update minor version.
    e.g. "x.1.x" -> "x.2.0"

    Args:
        dry_run (DryRun, optional): Dry run. Defaults to False.
        push (bool, optional): Push changes to remote. Defaults to True.
    """
    _release(ReleaseType.minor, dry_run, push)


@app.command()
def major(dry_run: DryRun = False, push: Push = True):
    """Update major version.
    e.g. "1.x.x" -> "2.0.0"

    Args:
        dry_run (DryRun, optional): Dry run. Defaults to False.
        push (bool, optional): Push changes to remote. Defaults to True.
    """
    _release(ReleaseType.major, dry_run, push)


def _release(t: ReleaseType, dry_run: DryRun = False, push: Push = True):
    old_version, new_version = _get_version(t)
    # Get repo, and check the workspace
    repo = _prepare_repo(version=new_version)
    if not dry_run:
        print(f"[*] Updated {t.value} version: {old_version} -> {new_version}")
    else:
        print(f"[*] Would update {t.value} version: {old_version} -> {new_version}")

    print(f"[*] Generating changelog for {new_version} ...")
    output = _generate_changelog(t, tag=new_version, dry_run=dry_run)
    if dry_run:
        print("▿" * 30, "\n", output, "\n", "▿" * 30, "\n")
        return
    else:
        if output:
            print(output)
        print("[*] Changelog generated. See", CHANGELOG_FILE)
        _edit_version(new_version=new_version)
        # stage PYPROJECT_FILE, BLENDER_MANIFEST_FILE, CHANGELOG_FILE and commit
        _commit_and_push(
            repo,
            files=[PYPROJECT_FILE, BLENDER_MANIFEST_FILE, INIT_FILE, CHANGELOG_FILE],
            msg=COMMIT_MSG.format(type=t.value, version=new_version),
            version=new_version,
            push=push,
        )


def _prepare_repo(version: str) -> git.Repo:
    repo = git.Repo('.')
    # pull contents from remote
    _ = repo.remotes.origin.fetch(tags=True)
    repo.git.pull()
    repo.git.pull(tags=True)
    # check if tag exists
    if version in repo.tags:
        msg = f'[!] Tag "{version}" already exists. Aborting.'
        print(f"[red]{msg}[/red]")
        sys.exit(-1)
    # Check if modified files exist (exclude untracked files)
    if repo.is_dirty():
        unstaged_mods = [item.a_path for item in repo.index.diff(None)]
        staged_mods = [item.a_path for item in repo.index.diff('HEAD')]
        modified_files = (str(x) for x in (*unstaged_mods, *staged_mods))
        if modified_files:
            msg = (
                f'[!] Found modified files:\n{chr(10).join(modified_files)}\n'
                'Please commit or stash changes before releasing.'
            )
            print(f'[red]{msg}[/red]')
            sys.exit(-1)
    return repo


def _edit_version(new_version: str):
    _edit_pyproject_version(new_version)
    _edit_blender_manifest_version(new_version)
    _edit_bl_info(new_version)


def _get_version(t: ReleaseType) -> tuple[str, str]:
    # Get current version
    try:
        with PYPROJECT_FILE.open("rb") as f:
            project_toml = tomllib.load(f)
            version = project_toml["project"]["version"]
            version = packaging.version.parse(version)
    except Exception as e:
        raise RuntimeError("Error loading pyproject.toml") from e
    # Calculate new version
    match t:
        case ReleaseType.major:
            new_version = f"{version.major + 1}.0.0"
        case ReleaseType.minor:
            new_version = f"{version.major}.{version.minor + 1}.0"
        case ReleaseType.patch:
            new_version = f"{version.major}.{version.minor}.{version.micro + 1}"
    return str(version), new_version


def _edit_pyproject_version(new_version: str):
    sec_pattern = re.compile(r"^\[(.+)\]$")
    sec_name = None

    lines = PYPROJECT_FILE.read_text().splitlines()
    for lino, line in enumerate(lines):
        line = line.strip()
        if line.startswith("[") and (g := sec_pattern.match(line)):
            sec_name = g.group(1)
        if sec_name == "project":
            key_str = line.partition("=")[0]
            if key_str.strip() == "version":
                lines[lino] = f'{key_str.rstrip()} = "{new_version}"'
                _save_lines(PYPROJECT_FILE, lines)
                return
    raise RuntimeError("project.version not found in pyproject.toml")


def _edit_blender_manifest_version(new_version: str):
    lines = BLENDER_MANIFEST_FILE.read_text().splitlines()
    for lino, line in enumerate(lines):
        line = line.strip()
        key_str = line.partition("=")[0]
        if key_str.strip() == "version":
            lines[lino] = f'{key_str.rstrip()} = "{new_version}"'
            _save_lines(BLENDER_MANIFEST_FILE, lines)
            return
    raise RuntimeError("version not found in blender_manifest.toml")


def _edit_bl_info(new_version: str):
    new_version_tuple_str = packaging.version.parse(
        new_version
    ).release.__str__()  # to tuple string
    lines = INIT_FILE.read_text().splitlines()
    if lines[0].strip().startswith("bl_info ="):
        for lino, line in enumerate(lines):
            key_str = line.partition(":")[0]
            if key_str.strip().strip('"\'') == "version":
                lines[lino] = f'{key_str}: {new_version_tuple_str},'
                _save_lines(INIT_FILE, lines)
                return


def _save_lines(filepath: Path, lines: list[str]):
    if lines[-1] != "":
        if lines[-1].strip() == "":
            lines[-1] = ""
        else:
            lines.append("")
    _ = filepath.write_text("\n".join(lines), newline="\n")


def _generate_changelog(_t: ReleaseType, tag: str, dry_run: bool):
    # commit_msg = COMMIT_MSG.format(type=t.value, version=version)
    cmd = [
        "git",
        "cliff",
        # "--with-commit",
        # commit_msg,
        "--tag",
        tag,
    ]
    if not dry_run:
        cmd.extend(["-o", CHANGELOG_FILE.as_posix()])

    print("    >", shlex.join(cmd))
    output = subprocess.check_output(
        cmd, text=True, encoding="utf-8", shell=is_windows()
    )
    return output


def _commit_and_push(
    repo: git.Repo, files: list[str | Path], msg: str, version: str, push: bool
):
    assert msg, "Commit message is empty"
    # commit
    _ = repo.index.add(files)
    try:
        # HACK: Don't use `repo.index.commit` since pre-commit hooks will raise error
        # repo.index.commit(COMMIT_MSG.format(type=t.value, version=new_version))
        commit_output = subprocess.check_output(
            [
                "git",
                "commit",
                "-m",
                msg,
            ],
            shell=is_windows(),
            text=True,
            encoding="utf-8",
        )
        print(commit_output)
    except subprocess.CalledProcessError as e:
        if e.returncode == 8749058:
            msg = '[!] bl_info needs to be updated. Run "python -m cli.bl_info" before commit.'
            print(f"[yellow]{msg}[/yellow]")
        else:
            print(f"[red]{e}[/red]")
            sys.exit(-1)
    # create tag
    _ = repo.create_tag(f"{version}")
    # push commits and tags
    if push:
        _ = repo.remote().push(force=True)
        _ = repo.remote().push(tags=True)


def is_windows():
    return platform.system() == 'Windows'


if __name__ == '__main__':
    app()
