# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# PARAMETERS CELL ********************

pipeline_run_id = "manual"
run_date = ""
workspace_id = ""
databricks_source_lakehouse_id = ""
databricks_source_schema = ""
cosmos_source_lakehouse_id = ""
cosmos_source_schema = ""
silver_lakehouse_id = ""
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
from pyspark.sql.window import Window

STAGE = "silver_transform"
_started = datetime.now(timezone.utc)


def require_parameters():
    required = ["workspace_id", "databricks_source_lakehouse_id", "databricks_source_schema", "cosmos_source_lakehouse_id", "cosmos_source_schema",
                "silver_lakehouse_id", "audit_lakehouse_id"]
    missing = [name for name in required if not str(globals()[name]).strip()]
    if missing:
        raise ValueError("Missing deployment parameters: " + ", ".join(missing))


require_parameters()


def path(lakehouse_id, table_name):
    return f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{table_name}"


def read_source(lakehouse_id, table_name, schema_name=""):
    object_name = f"{schema_name}/{table_name}" if schema_name else table_name
    return spark.read.format("delta").load(path(lakehouse_id, object_name))


def latest(df, keys, order_column):
    window = Window.partitionBy(*keys).orderBy(F.col(order_column).desc_nulls_last())
    return df.withColumn("_row_number", F.row_number().over(window)).filter("_row_number = 1").drop("_row_number")


def json_text(df, column):
    field = next(item for item in df.schema.fields if item.name == column)
    return F.col(column) if field.dataType.typeName() == "string" else F.to_json(F.col(column))


def with_lineage(df, source_system):
    return (df.withColumn("source_system", F.lit(source_system))
              .withColumn("pipeline_run_id", F.lit(pipeline_run_id))
              .withColumn("run_date", F.to_date(F.lit(run_date)) if run_date else F.current_date())
              .withColumn("silver_loaded_at", F.current_timestamp()))


def replace_table(df, table_name):
    # A deterministic full refresh is appropriate for this POC and makes retries idempotent.
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path(silver_lakehouse_id, table_name))


def split_quality(df, valid_condition, table_name, reason):
    # coalesce is essential: Spark's three-valued logic would otherwise put
    # rows whose rule evaluates to NULL in neither the valid nor invalid set.
    is_valid = F.coalesce(valid_condition, F.lit(False))
    invalid = with_lineage(df.filter(~is_valid).withColumn("quarantine_reason", F.lit(reason)), "quality")
    replace_table(invalid, "quarantine_" + table_name)
    return df.filter(is_valid), invalid.count()


def write_audit(status, rows_read, rows_written, error_message=None):
    ended = datetime.now(timezone.utc)
    schema = StructType([
        StructField("pipeline_run_id", StringType(), False), StructField("run_date", StringType(), True),
        StructField("stage", StringType(), False), StructField("status", StringType(), False),
        StructField("rows_read", LongType(), False), StructField("rows_written", LongType(), False),
        StructField("started_at", TimestampType(), False), StructField("ended_at", TimestampType(), False),
        StructField("duration_seconds", LongType(), False), StructField("error_message", StringType(), True),
    ])
    incoming = spark.createDataFrame([Row(
        pipeline_run_id=pipeline_run_id, run_date=run_date or None, stage=STAGE, status=status,
        rows_read=int(rows_read), rows_written=int(rows_written), started_at=_started, ended_at=ended,
        duration_seconds=int((ended - _started).total_seconds()), error_message=error_message)], schema)
    audit_path = path(audit_lakehouse_id, "control_pipeline_run_log")
    if DeltaTable.isDeltaTable(spark, audit_path):
        (DeltaTable.forPath(spark, audit_path).alias("t").merge(
            incoming.alias("s"), "t.pipeline_run_id=s.pipeline_run_id AND t.stage=s.stage")
         .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        incoming.write.format("delta").mode("overwrite").save(audit_path)


rows_read = rows_written = 0
try:
    raw_txn = read_source(databricks_source_lakehouse_id, "transactions", databricks_source_schema)
    raw_risk = read_source(databricks_source_lakehouse_id, "transaction_risk", databricks_source_schema)
    raw_merchants = read_source(databricks_source_lakehouse_id, "merchants", databricks_source_schema)
    raw_sessions = read_source(cosmos_source_lakehouse_id, "digitalSessions", cosmos_source_schema)
    raw_devices = read_source(cosmos_source_lakehouse_id, "devices", cosmos_source_schema)
    raw_alerts = read_source(cosmos_source_lakehouse_id, "fraudAlerts", cosmos_source_schema)
    rows_read = sum(df.count() for df in [raw_txn, raw_risk, raw_merchants, raw_sessions, raw_devices, raw_alerts])

    transactions = latest(raw_txn, ["TransactionID"], "TransactionTimestamp").select(
        F.trim("TransactionID").alias("TransactionID"), F.trim("AccountID").alias("AccountID"),
        F.trim("CustomerID").alias("CustomerID"), F.trim("MerchantID").alias("MerchantID"),
        F.trim("DeviceID").alias("DeviceID"), F.to_timestamp("TransactionTimestamp").alias("TransactionTimestamp"),
        F.col("Amount").cast("decimal(18,2)").alias("Amount"), F.upper("Currency").alias("Currency"),
        "TransactionType", "MerchantCategory", "Channel", "Country", F.col("CardPresent").cast("boolean").alias("CardPresent"),
        "TransactionStatus", "SourceBatch")
    txn_ok = (F.col("TransactionID").rlike(r"^TXN-[0-9]{9}$") & F.col("CustomerID").isNotNull() &
              F.col("TransactionTimestamp").isNotNull() & (F.col("Amount") >= 0))
    transactions, _ = split_quality(transactions, txn_ok, "transactions", "invalid key, timestamp, or amount")

    risk = latest(raw_risk, ["TransactionID"], "ScoredTimestamp").select(
        F.trim("TransactionID").alias("TransactionID"), F.col("RiskScore").cast("double").alias("RiskScore"),
        "RiskBand", "ModelVersion", F.to_timestamp("ScoredTimestamp").alias("ScoredTimestamp"),
        F.col("RiskFactors").cast("string").alias("RiskFactors"), "SourceBatch")
    valid_txn_ids = transactions.select("TransactionID").withColumn("_transaction_exists", F.lit(True))
    risk = risk.join(valid_txn_ids, "TransactionID", "left")
    risk, _ = split_quality(risk, F.col("RiskScore").between(0, 100) & F.col("_transaction_exists"),
                            "transaction_risk", "risk score outside 0..100 or orphan TransactionID")
    risk = risk.drop("_transaction_exists")

    merchants = latest(raw_merchants, ["MerchantID"], "SourceBatch").select(
        "MerchantID", "MerchantName", "MerchantCategory", "City", "State", "Country", "MerchantRiskCategory", "SourceBatch")
    merchants, _ = split_quality(merchants, F.col("MerchantID").isNotNull() & F.col("MerchantName").isNotNull(),
                                 "merchants", "missing merchant business key or name")

    session_json = json_text(raw_sessions, "device")
    auth_json = json_text(raw_sessions, "authentication")
    geo_json = json_text(raw_sessions, "geo")
    activities_json = json_text(raw_sessions, "activities")
    sessions = latest(raw_sessions, ["sessionId"], "loginTimestamp").select(
        F.col("sessionId").alias("SessionID"), F.col("customerId").alias("CustomerID"),
        F.get_json_object(session_json, "$.deviceId").alias("DeviceID"),
        F.get_json_object(session_json, "$.deviceType").alias("DeviceType"),
        F.get_json_object(session_json, "$.operatingSystem.name").alias("OperatingSystem"),
        F.to_timestamp("loginTimestamp").alias("LoginTimestamp"), F.to_timestamp("logoutTimestamp").alias("LogoutTimestamp"),
        F.get_json_object(auth_json, "$.method").alias("AuthenticationMethod"),
        F.get_json_object(auth_json, "$.mfaUsed").cast("boolean").alias("MfaUsed"),
        F.get_json_object(auth_json, "$.failedAttempts").cast("int").alias("FailedAttempts"),
        F.get_json_object(geo_json, "$.country").alias("Country"), F.get_json_object(geo_json, "$.state").alias("State"),
        F.get_json_object(geo_json, "$.city").alias("City"), F.col("sessionRiskScore").cast("double").alias("SessionRiskScore"),
        activities_json.alias("ActivitiesJSON"))
    sessions, _ = split_quality(sessions, F.col("SessionID").isNotNull() & F.col("CustomerID").isNotNull() &
                                F.col("DeviceID").isNotNull() & F.col("LoginTimestamp").isNotNull(),
                                "sessions", "missing key, device, customer, or valid login timestamp")

    os_json = json_text(raw_devices, "operatingSystem")
    signals_json = json_text(raw_devices, "riskSignals")
    geo_history_json = json_text(raw_devices, "geoHistory")
    devices = latest(raw_devices, ["deviceId"], "lastSeen").select(
        F.col("deviceId").alias("DeviceID"), F.col("customerId").alias("CustomerID"),
        F.to_timestamp("firstSeen").alias("FirstSeen"), F.to_timestamp("lastSeen").alias("LastSeen"),
        F.col("trusted").cast("boolean").alias("Trusted"), "deviceFingerprint",
        F.get_json_object(os_json, "$.name").alias("OperatingSystem"),
        F.get_json_object(os_json, "$.version").alias("OperatingSystemVersion"), "appVersion",
        signals_json.alias("RiskSignalsJSON"), geo_history_json.alias("GeoHistoryJSON"))
    devices, _ = split_quality(devices, F.col("DeviceID").isNotNull() & F.col("CustomerID").isNotNull(),
                               "devices", "missing device or customer business key")

    alerts = latest(raw_alerts, ["alertId"], "createdTimestamp").select(
        F.col("alertId").alias("AlertID"), F.col("customerId").alias("CustomerID"),
        F.col("transactionId").alias("TransactionID"), F.to_timestamp("createdTimestamp").alias("CreatedTimestamp"),
        "alertType", F.lower("severity").alias("Severity"), F.lower("status").alias("Status"),
        json_text(raw_alerts, "signals").alias("SignalsJSON"),
        json_text(raw_alerts, "investigatorNotes").alias("InvestigatorNotesJSON"))
    alerts, _ = split_quality(alerts, F.col("AlertID").isNotNull() & F.col("CustomerID").isNotNull() &
                              F.col("CreatedTimestamp").isNotNull() & F.col("Severity").isin("low", "medium", "high", "critical"),
                              "fraud_alerts", "missing key/timestamp or invalid severity")

    outputs = {"transactions": transactions, "transaction_risk": risk, "merchants": merchants,
               "sessions": sessions, "devices": devices, "fraud_alerts": alerts}
    for name, df in outputs.items():
        enriched = with_lineage(df, "databricks" if name in {"transactions", "transaction_risk", "merchants"} else "cosmos")
        replace_table(enriched, name)
        rows_written += enriched.count()
    write_audit("Succeeded", rows_read, rows_written)
except Exception as exc:
    write_audit("Failed", rows_read, rows_written, str(exc)[:2000])
    raise

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
