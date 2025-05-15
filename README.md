# FastAPI Project Template

This is a template for a FastAPI project.

It is heavily based on the [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)

## 1 - Development

### 1.1 - Install dependencies

```bash
uv sync
```

### 1.2 - Linting and Formatting

```bash
uv run ruff check
uv run ruff format
```

### 1.3 - Run development server

```bash
uv run fastapi dev main.py
```

### 1.4 - Run Production Server

```bash
uv run fastapi run main.py
```

## 2 - Release

Release tool: Update version number, generate changelog, and create git tag.

See `scripts/release.py` for more details.

```bash
uv run release patch|minor|major [--dry-run] [--push]
```
