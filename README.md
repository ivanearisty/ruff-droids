# ruff-droids

CLI tool that runs `ruff --fix` on a codebase and dispatches remaining violations to Factory AI droids for resolution.

## Install

```bash
uv tool install .
```

## Usage

```bash
ruff-droids --path /your/project
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--path` | `.` | Target directory |
| `--factory-api-key` | `FACTORY_API_KEY` env | Factory API key |
| `--concurrency` | `4` | Parallel droid workers |
