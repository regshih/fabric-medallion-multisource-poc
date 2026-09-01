# Fabric notebook source

# PARAMETERS CELL ********************
pipeline_run_id = "manual"
run_date = ""
workspace_id = ""
databricks_source_lakehouse_id = ""
cosmos_source_lakehouse_id = ""
silver_lakehouse_id = ""
gold_lakehouse_id = ""
audit_lakehouse_id = ""

# CELL ********************
from datetime import datetime, timezone
from delta.tables import DeltaTable
from pyspark.sql import Row
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

STAGE = "reconciliation"
_started = datetime.now(timezone.utc)
for _name in ("workspace_id", "databricks_source_lakehouse_id", "cosmos_source_lakehouse_id",
              "silver_lakehouse_id", "gold_lakehouse_id", "audit_lakehouse_id"):
    if not str(globals()[_name]).strip():
        raise ValueError(f"Required deployment parameter is empty: {_name}")


def path(lakehouse_id, table_name):
    return f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{table_name}"


def read(lakehouse_id, table_name):
    return spark.read.format("delta").load(path(lakehouse_id, table_name))


rows = []


def compare(source, obj, source_lh, silver_name, gold_name=None):
    source_count = read(source_lh, obj).count()
    silver_count = read(silver_lakehouse_id, silver_name).count()
    gold_count = read(gold_lakehouse_id, gold_name).count() if gold_name else None
    quarantine_name = "quarantine_" + silver_name
    quarantine_count = read(silver_lakehouse_id, quarantine_name).count()
    expected_silver = source_count - quarantine_count
    status = "PASS" if silver_count == expected_silver and (gold_count is None or gold_count == silver_count) else "FAIL"
    rows.append((pipeline_run_id, run_date, source, obj, source_count, silver_count, gold_count,
                 quarantine_count, "row_count_minus_quarantine", status,
                 f"expected silver={expected_silver}; Gold comparison applies only at equivalent fact grain"))


try:
    compare("databricks", "transactions", databricks_source_lakehouse_id, "transactions", "FactTransactions")
    compare("databricks", "transaction_risk", databricks_source_lakehouse_id, "transaction_risk")
    compare("databricks", "merchants", databricks_source_lakehouse_id, "merchants", "DimMerchant")
    compare("cosmos", "digitalSessions", cosmos_source_lakehouse_id, "sessions", "FactDigitalSessions")
    compare("cosmos", "devices", cosmos_source_lakehouse_id, "devices", "DimDevice")
    compare("cosmos", "fraudAlerts", cosmos_source_lakehouse_id, "fraud_alerts", "FactFraudAlerts")

    alerts = read(silver_lakehouse_id, "fraud_alerts")
    txns = read(silver_lakehouse_id, "transactions").select("TransactionID")
    linked = alerts.filter(F.col("TransactionID").isNotNull())
    orphan_count = linked.join(txns, "TransactionID", "left_anti").count()
    rows.append((pipeline_run_id, run_date, "cross_source", "fraud_alerts_to_transactions", linked.count(),
                 linked.count() - orphan_count, None, orphan_count, "relationship_validation",
                 "PASS" if orphan_count == 0 else "WARN", "Cosmos alert TransactionID matched to Databricks transactions"))

    result = spark.createDataFrame(rows, ["pipeline_run_id", "run_date", "source", "object", "source_count",
        "silver_count", "gold_count", "quarantine_count", "validation_type", "status", "notes"])
    target = path(gold_lakehouse_id, "reconciliation_results")
    if DeltaTable.isDeltaTable(spark, target):
        (DeltaTable.forPath(spark, target).alias("t").merge(result.alias("s"),
          "t.pipeline_run_id=s.pipeline_run_id AND t.source=s.source AND t.object=s.object")
         .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        result.write.format("delta").mode("overwrite").save(target)
    hard_failures = result.filter("status = 'FAIL'").count()
    status = "Succeeded" if hard_failures == 0 else "Failed"
    error_message = None if hard_failures == 0 else f"{hard_failures} reconciliation checks failed"
except Exception as exc:
    status, error_message = "Failed", str(exc)[:2000]
    hard_failures = 1

ended = datetime.now(timezone.utc)
audit_schema = StructType([
    StructField("pipeline_run_id", StringType(), False), StructField("run_date", StringType(), True),
    StructField("stage", StringType(), False), StructField("status", StringType(), False),
    StructField("rows_read", LongType(), False), StructField("rows_written", LongType(), False),
    StructField("started_at", TimestampType(), False), StructField("ended_at", TimestampType(), False),
    StructField("duration_seconds", LongType(), False), StructField("error_message", StringType(), True)])
audit_df = spark.createDataFrame([Row(pipeline_run_id=pipeline_run_id, run_date=run_date or None, stage=STAGE,
    status=status, rows_read=sum(r[4] for r in rows), rows_written=len(rows), started_at=_started, ended_at=ended,
    duration_seconds=int((ended - _started).total_seconds()), error_message=error_message)], audit_schema)
audit_path = path(audit_lakehouse_id, "control_pipeline_run_log")
if DeltaTable.isDeltaTable(spark, audit_path):
    (DeltaTable.forPath(spark, audit_path).alias("t").merge(audit_df.alias("s"),
      "t.pipeline_run_id=s.pipeline_run_id AND t.stage=s.stage")
     .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
else:
    audit_df.write.format("delta").mode("overwrite").save(audit_path)
if hard_failures:
    raise RuntimeError(error_message)

