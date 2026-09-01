# Fabric notebook source

# PARAMETERS CELL ********************
pipeline_run_id = "manual"
run_date = ""
stage = "pipeline"
result = "Succeeded"
error_message = ""
raise_after_log = False
workspace_id = ""
audit_lakehouse_id = ""

# CELL ********************
"""Idempotent success/failure logger used by pipeline dependency paths."""
from datetime import datetime, timezone
from delta.tables import DeltaTable
from pyspark.sql import Row
from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

if not workspace_id or not audit_lakehouse_id:
    raise ValueError("workspace_id and audit_lakehouse_id are required deployment parameters")
if not pipeline_run_id or not stage or not result:
    raise ValueError("pipeline_run_id, stage, and result cannot be empty")

now = datetime.now(timezone.utc)
schema = StructType([
    StructField("pipeline_run_id", StringType(), False), StructField("run_date", StringType(), True),
    StructField("stage", StringType(), False), StructField("status", StringType(), False),
    StructField("rows_read", LongType(), False), StructField("rows_written", LongType(), False),
    StructField("started_at", TimestampType(), False), StructField("ended_at", TimestampType(), False),
    StructField("duration_seconds", LongType(), False), StructField("error_message", StringType(), True)])
row = Row(pipeline_run_id=pipeline_run_id, run_date=run_date or None, stage=stage, status=result,
          rows_read=0, rows_written=0, started_at=now, ended_at=now, duration_seconds=0,
          error_message=(error_message or None))
incoming = spark.createDataFrame([row], schema)
audit_path = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{audit_lakehouse_id}/Tables/control_pipeline_run_log"
if DeltaTable.isDeltaTable(spark, audit_path):
    (DeltaTable.forPath(spark, audit_path).alias("t").merge(incoming.alias("s"),
      "t.pipeline_run_id=s.pipeline_run_id AND t.stage=s.stage")
     .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
else:
    incoming.write.format("delta").mode("overwrite").save(audit_path)

should_raise = raise_after_log if isinstance(raise_after_log, bool) else str(raise_after_log).strip().lower() in {"1", "true", "yes"}
if should_raise:
    raise RuntimeError(error_message or f"Pipeline stage '{stage}' reported result '{result}'")

