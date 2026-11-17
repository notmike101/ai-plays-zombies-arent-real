"""Repository paths and optional machine-local TOML configuration."""
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'zar.local.toml'


def load_config(path=CONFIG):
    if not path.is_file():
        raise ValueError(f'Create {path.name} from zar.example.toml and set local paths first')
    with path.open('rb') as f:
        return tomllib.load(f)


def config_path(config, section, key, root=ROOT):
    value = config.get(section, {}).get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Set [{section}] {key} in zar.local.toml')
    return (root/Path(value)).resolve()
