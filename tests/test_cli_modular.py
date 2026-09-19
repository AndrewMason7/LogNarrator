from click.testing import CliRunner

from log_narrator.cli import main


def test_cli_options_composition():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--local-url" in result.output
    assert "--compaction-token-threshold" in result.output
    assert "--mcp-server" in result.output
    assert "--structured-output" in result.output
