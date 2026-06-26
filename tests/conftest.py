import os
import sys
import tempfile
from pathlib import Path


# Point all agent state (worklogs, session history, todo_list, component plans) at
# a throwaway temp dir so the test suite never writes into the real agent-state/
# tree. This must run before langbridge_cli.config is imported, since config
# derives every state path from this env var at import time.
os.environ["LANGBRIDGE_AGENT_STATE_DIR"] = tempfile.mkdtemp(prefix="langbridge-test-state-")

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
