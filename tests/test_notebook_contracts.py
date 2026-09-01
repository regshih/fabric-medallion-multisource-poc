import ast
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
NOTEBOOKS = ROOT / "notebooks"
NAMES = {
    "nb_source_validation.py",
    "nb_silver_transform.py",
    "nb_gold_build.py",
    "nb_reconciliation.py",
    "nb_gold_consumption_demo.py",
    "nb_warehouse_publish.py",
    "nb_pipeline_log.py",
}


def source(name):
    return (NOTEBOOKS / name).read_text(encoding="utf-8")


def test_all_expected_notebooks_are_valid_python():
    assert {path.name for path in NOTEBOOKS.glob("nb_*.py")} == NAMES
    for name in NAMES:
        ast.parse(source(name), filename=name)


def test_notebooks_include_fabric_kernel_and_cell_metadata():
    for name in NAMES:
        text = source(name)
        assert '"name": "synapse_pyspark"' in text
        assert text.count("# METADATA ********************") >= 3
        assert '"language_group": "synapse_pyspark"' in text
        assert "# PARAMETERS CELL ********************\n\n" in text
        assert "# CELL ********************\n\n" in text


def test_notebooks_use_deploy_time_parameters_and_no_embedded_guids():
    guid = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I)
    for name in NAMES:
        text = source(name)
        assert "workspace_id = \"\"" in text
        assert "pipeline_run_id = \"manual\"" in text
        assert "run_date = \"\"" in text
        assert not guid.search(text)
        assert "AccountKey=" not in text
        assert "Bearer " not in text


def test_core_contracts_are_present():
    silver = source("nb_silver_transform.py")
    gold = source("nb_gold_build.py")
    reconciliation = source("nb_reconciliation.py")
    assert all(token in silver for token in ["digitalSessions", "fraudAlerts", "quarantine_", "ActivitiesJSON", "FailedAttempts"])
    assert all(token in gold for token in ["DimCustomer", "DimMerchant", "FactTransactions", "FactDigitalSessions",
                                           "FactFraudAlerts", "AggCustomerRiskProfile", "CustomerRiskScore"])
    assert "cross_source" in reconciliation
    assert "control_pipeline_run_log" in source("nb_source_validation.py")
    assert "control_pipeline_run_log" in silver
    assert "control_pipeline_run_log" in gold
    source_validation = source("nb_source_validation.py")
    assert 'source = "all"' in source_validation
    assert '{"all", "databricks", "cosmos"}' in source_validation
    assert 'STAGE = f"source_validation_{source}"' in source_validation


def test_pipeline_logging_and_warehouse_contracts():
    logger = source("nb_pipeline_log.py")
    warehouse = source("nb_warehouse_publish.py")
    assert all(f'{name} =' in logger for name in ["pipeline_run_id", "run_date", "stage", "result",
                                                      "error_message", "raise_after_log"])
    assert "whenMatchedUpdateAll" in logger
    assert "if should_raise:" in logger
    assert "warehouse_publish_contract" in warehouse
    assert "PendingExecution" in warehouse
    assert "CREATE TABLE [dbo]" in warehouse
    assert "ContractReady" in warehouse


def test_writes_are_idempotent_at_poc_grain():
    for name in ["nb_silver_transform.py", "nb_gold_build.py"]:
        assert '.mode("overwrite")' in source(name)
    for name in ["nb_source_validation.py", "nb_silver_transform.py", "nb_gold_build.py", "nb_reconciliation.py",
                 "nb_warehouse_publish.py", "nb_pipeline_log.py"]:
        text = source(name)
        assert "whenMatchedUpdateAll" in text
        assert "pipeline_run_id=s.pipeline_run_id" in text
