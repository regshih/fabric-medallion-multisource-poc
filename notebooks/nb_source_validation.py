# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# PARAMETERS CELL ********************

# Values are supplied by the deployment pipeline. Empty defaults are deliberate:
# no tenant-specific identifiers or credentials belong in source control.
pipeline_run_id = "manual"
run_date = ""
source = "all"  # Pipeline branches pass "databricks" or "cosmos".
workspace_id = ""
databricks_source_lakehouse_id = ""
databricks_source_schema = ""
cosmos_source_lakehouse_id = ""
cosmos_source_schema = ""
audit_lakehouse_id = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from datetime import datetime, timezone
from delta.tables import DeltaTable
from pyspark.sql import Row
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

_started = datetime.now(timezone.utc)


def _required(name, value):
    if not str(value).strip():
        raise ValueError(f"Required deployment parameter is empty: {name}")


if source.lower() not in {"all", "databricks", "cosmos"}:
    raise ValueError("source must be one of: all, databricks, cosmos")
source = source.lower()
STAGE = f"source_validation_{source}"

for _name in ("workspace_id", "audit_lakehouse_id"):
    _required(_name, globals()[_name])
if source in {"all", "databricks"}:
    _required("databricks_source_lakehouse_id", databricks_source_lakehouse_id)
    _required("databricks_source_schema", databricks_source_schema)
if source in {"all", "cosmos"}:
    _required("cosmos_source_lakehouse_id", cosmos_source_lakehouse_id)
    _required("cosmos_source_schema", cosmos_source_schema)


def table_path(lakehouse_id, table_name, schema_name=""):
    object_path = f"{schema_name}/{table_name}" if schema_name else table_name
    return f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{object_path}"


AUDIT_SCHEMA = StructType([
    StructField("pipeline_run_id", StringType(), False), StructField("run_date", StringType(), True),
    StructField("stage", StringType(), False), StructField("status", StringType(), False),
    StructField("rows_read", LongType(), False), StructField("rows_written", LongType(), False),
    StructField("started_at", TimestampType(), False), StructField("ended_at", TimestampType(), False),
    StructField("duration_seconds", LongType(), False), StructField("error_message", StringType(), True),
])


def write_audit(status, rows_read=0, rows_written=0, error_message=None):
    ended = datetime.now(timezone.utc)
    row = Row(pipeline_run_id=pipeline_run_id, run_date=run_date or None, stage=STAGE,
              status=status, rows_read=int(rows_read), rows_written=int(rows_written),
              started_at=_started, ended_at=ended,
              duration_seconds=int((ended - _started).total_seconds()), error_message=error_message)
    incoming = spark.createDataFrame([row], AUDIT_SCHEMA)
    path = table_path(audit_lakehouse_id, "control_pipeline_run_log")
    if DeltaTable.isDeltaTable(spark, path):
        (DeltaTable.forPath(spark, path).alias("t").merge(
            incoming.alias("s"), "t.pipeline_run_id=s.pipeline_run_id AND t.stage=s.stage")
         .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        incoming.write.format("delta").mode("overwrite").save(path)


EXPECTED = {
    "databricks": (databricks_source_lakehouse_id, databricks_source_schema, {
        "transactions": {"TransactionID", "CustomerID", "AccountID", "MerchantID", "TransactionTimestamp", "Amount"},
        "transaction_risk": {"TransactionID", "RiskScore", "RiskBand", "ScoredTimestamp"},
        "merchants": {"MerchantID", "MerchantName", "MerchantRiskCategory"},
    }),
    "cosmos": (cosmos_source_lakehouse_id, cosmos_source_schema, {
        "digitalSessions": {"sessionId", "customerId", "device", "loginTimestamp", "authentication"},
        "devices": {"deviceId", "customerId", "trusted", "operatingSystem"},
        "fraudAlerts": {"alertId", "customerId", "createdTimestamp", "severity", "status"},
    }),
}

results = []
total_rows = 0
try:
    selected_sources = EXPECTED if source == "all" else {source: EXPECTED[source]}
    for source_name, (lakehouse_id, schema_name, tables) in selected_sources.items():
        for object_name, expected_columns in tables.items():
            try:
                df = spark.read.format("delta").load(table_path(lakehouse_id, object_name, schema_name))
                count = df.count()
                missing = sorted(expected_columns - set(df.columns))
                status = "PASS" if not missing else "FAIL"
                notes = "schema and read succeeded" if not missing else "missing columns: " + ", ".join(missing)
                total_rows += count
            except Exception as exc:
                count, status, notes = 0, "FAIL", f"read failed: {type(exc).__name__}: {str(exc)[:500]}"
            results.append((pipeline_run_id, run_date, source_name, object_name, count, "source_read_and_schema", status, notes))

    validation_df = spark.createDataFrame(results, [
        "pipeline_run_id", "run_date", "source", "object", "source_count",
        "validation_type", "status", "notes",
    ])
    output = table_path(audit_lakehouse_id, "source_validation_results")
    if DeltaTable.isDeltaTable(spark, output):
        (DeltaTable.forPath(spark, output).alias("t").merge(
            validation_df.alias("s"),
            "t.pipeline_run_id=s.pipeline_run_id AND t.source=s.source AND t.object=s.object")
         .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        validation_df.write.format("delta").mode("overwrite").save(output)
    failed = validation_df.filter("status = 'FAIL'").count()
    if failed:
        raise RuntimeError(f"Source validation failed for {failed} object(s); inspect source_validation_results")
    write_audit("Succeeded", total_rows, len(results))
except Exception as exc:
    write_audit("Failed", total_rows, len(results), str(exc)[:2000])
    raise

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
