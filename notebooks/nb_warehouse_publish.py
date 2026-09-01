# Fabric notebook source

# PARAMETERS CELL ********************
pipeline_run_id = "manual"
run_date = ""
workspace_id = ""
gold_lakehouse_id = ""
gold_lakehouse_name = ""
warehouse_name = "gold_wh"
audit_lakehouse_id = ""

# CELL ********************
"""Prepare the Warehouse materialization contract.

Fabric Spark sessions do not provide a supported, identity-safe way to execute
Warehouse T-SQL directly. This notebook therefore publishes deterministic T-SQL
statements for a pipeline Script activity connected to the Warehouse. Producing
the contract is explicit; it is not reported as an executed Warehouse publish.
"""
from datetime import datetime, timezone
from delta.tables import DeltaTable
from pyspark.sql import Row
from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

STAGE = "warehouse_publish_contract"
_started = datetime.now(timezone.utc)
for _name in ("workspace_id", "gold_lakehouse_id", "gold_lakehouse_name", "warehouse_name", "audit_lakehouse_id"):
    if not str(globals()[_name]).strip():
        raise ValueError(f"Required deployment parameter is empty: {_name}")


def path(lakehouse_id, table_name):
    return f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{table_name}"


TABLES = ["DimCustomer", "DimMerchant", "DimDevice", "DimDate", "FactTransactions",
          "FactDigitalSessions", "FactFraudAlerts", "AggCustomerRiskProfile"]

# Warehouse Script activity executes each statement independently. DROP+CTAS is
# deterministic for this POC and prevents duplicate facts on a pipeline retry.
contract_rows = []
for ordinal, table_name in enumerate(TABLES, start=1):
    sql = (
        f"DROP TABLE IF EXISTS [dbo].[{table_name}];\n"
        f"CREATE TABLE [dbo].[{table_name}] AS\n"
        f"SELECT * FROM [{gold_lakehouse_name}].[dbo].[{table_name}];"
    )
    contract_rows.append((pipeline_run_id, run_date, warehouse_name, ordinal, table_name, sql, "PendingExecution"))

contract = spark.createDataFrame(contract_rows, ["pipeline_run_id", "run_date", "warehouse_name",
    "execution_order", "object_name", "sql_statement", "execution_status"])
contract_path = path(audit_lakehouse_id, "warehouse_publish_contract")
if DeltaTable.isDeltaTable(spark, contract_path):
    (DeltaTable.forPath(spark, contract_path).alias("t").merge(contract.alias("s"),
      "t.pipeline_run_id=s.pipeline_run_id AND t.object_name=s.object_name")
     .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
else:
    contract.write.format("delta").mode("overwrite").save(contract_path)

ended = datetime.now(timezone.utc)
audit_schema = StructType([
    StructField("pipeline_run_id", StringType(), False), StructField("run_date", StringType(), True),
    StructField("stage", StringType(), False), StructField("status", StringType(), False),
    StructField("rows_read", LongType(), False), StructField("rows_written", LongType(), False),
    StructField("started_at", TimestampType(), False), StructField("ended_at", TimestampType(), False),
    StructField("duration_seconds", LongType(), False), StructField("error_message", StringType(), True)])
audit_row = Row(pipeline_run_id=pipeline_run_id, run_date=run_date or None, stage=STAGE,
                status="ContractReady", rows_read=0, rows_written=len(contract_rows), started_at=_started,
                ended_at=ended, duration_seconds=int((ended - _started).total_seconds()), error_message=None)
audit_df = spark.createDataFrame([audit_row], audit_schema)
audit_path = path(audit_lakehouse_id, "control_pipeline_run_log")
if DeltaTable.isDeltaTable(spark, audit_path):
    (DeltaTable.forPath(spark, audit_path).alias("t").merge(audit_df.alias("s"),
      "t.pipeline_run_id=s.pipeline_run_id AND t.stage=s.stage")
     .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
else:
    audit_df.write.format("delta").mode("overwrite").save(audit_path)

print(f"Prepared {len(contract_rows)} idempotent CTAS statements for Warehouse '{warehouse_name}'.")
print("Execution status is PendingExecution until the Warehouse-connected pipeline Script activity runs them.")

