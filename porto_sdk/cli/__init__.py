"""
Porto SDK CLI - thin wrapper over PortoClient. No resolver or business logic.
Config: env (PORTO_PROVIDER, etc.) → ~/.porto/config.json → --provider override.

Structure (SOLID/DRY):
  _runner       - Entry point, argument parsing, dispatch
  _bootstrap    - build_cli_config, build_cli_client
  _output       - print_output, is_json_mode
  _validation   - ensure_required_flags, add_provider_flag, add_output_flags
  _config_store - Provider-scoped config read/write
  _commands     - Command handlers (thin wrappers over PortoClient)
"""

from ._config_store import get_config_summary, load_porto_config
from ._runner import main

__all__ = ["get_config_summary", "load_porto_config", "main"]
