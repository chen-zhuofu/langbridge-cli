# langbridge-cli

A tiny interactive coding agent CLI backed by a Codex model.

It runs a small ReAct loop and can call local read-only tools to inspect the
current workspace:

- `list_dir`: list files and directories
- `read_file`: read UTF-8 text files

File tools are limited to the directory where you start the CLI.

## Run

```bash
python src/langbridge_cli/main.py
```

On first run, `langbridge-cli` asks for your Codex API key and saves it to `~/.langbridge/config.json`.
You can still override it with `OPENAI_API_KEY`.

Use `LANGBRIDGE_MODEL` to override the default model:

```bash
LANGBRIDGE_MODEL=gpt-5.1-codex python src/langbridge_cli/main.py
```

Install locally to get the `langbridge` command:

```bash
pip install -e .
langbridge
```

Inside the CLI, type `/exit` to quit.
