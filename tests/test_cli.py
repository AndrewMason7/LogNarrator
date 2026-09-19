from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from log_narrator.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "LogNarrator" in result.output

def test_cli_executes_with_options_and_assembles_config():
    runner = CliRunner()
    with patch("log_narrator.cli.PipelineCoordinator") as mock_coord_cls, patch("asyncio.run"):
        mock_coord = MagicMock()
        mock_coord_cls.return_value = mock_coord

        result = runner.invoke(main, [
            "--local-url", "http://localhost:11434",
            "--local-model", "deepseek-coder",
            "--compaction-token-threshold", "40000",
            "--structured-output",
            "--sink", "stdout",
            "--max-total-tokens", "8192",
            "--max-retries", "5",
            "-M", "k8s=http://localhost:9090",
        ])

        assert result.exit_code == 0, result.output
        mock_coord_cls.assert_called_once()
        
        cfg = mock_coord_cls.call_args.kwargs["config"]
        assert cfg.local_url == "http://localhost:11434"
        assert cfg.local_model == "deepseek-coder"
        assert cfg.compaction_token_threshold == 40000
        assert cfg.structured_output is True
        assert cfg.sink == "stdout"
        assert cfg.max_total_tokens == 8192
        assert cfg.max_retries == 5
        assert cfg.mcp_servers == ["k8s=http://localhost:9090"]
