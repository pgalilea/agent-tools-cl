from click.testing import CliRunner

from agent_tools_cl.cli import main


def test_uf_help():
    result = CliRunner().invoke(main, ["financial", "uf", "--help"])
    assert result.exit_code == 0
    assert "CLP" in result.output


def test_financial_group_lists_uf():
    result = CliRunner().invoke(main, ["financial", "--help"])
    assert "uf" in result.output


def test_groups_are_registered():
    result = CliRunner().invoke(main, ["--help"])
    assert "calendar" in result.output
