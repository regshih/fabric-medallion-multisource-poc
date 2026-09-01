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
silver_lakehouse_id = ""
gold_lakehouse_id = ""
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

STAGE = "gold_build"
_started = datetime.now(timezone.utc)
for _name in ("workspace_id", "silver_lakehouse_id", "gold_lakehouse_id", "audit_lakehouse_id"):
    if not str(globals()[_name]).strip():
        raise ValueError(f"Required deployment parameter is empty: {_name}")


def path(lakehouse_id, table_name):
    return f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/{table_name}"


def silver(name):
    return spark.read.format("delta").load(path(silver_lakehouse_id, name))


def write_gold(df, name):
    (df.withColumn("pipeline_run_id", F.lit(pipeline_run_id))
       .withColumn("run_date", F.to_date(F.lit(run_date)) if run_date else F.current_date())
       .withColumn("gold_loaded_at", F.current_timestamp())
       .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .save(path(gold_lakehouse_id, name)))


def audit(status, rows_read, rows_written, error_message=None):
    ended = datetime.now(timezone.utc)
    schema = StructType([
        StructField("pipeline_run_id", StringType(), False), StructField("run_date", StringType(), True),
        StructField("stage", StringType(), False), StructField("status", StringType(), False),
        StructField("rows_read", LongType(), False), StructField("rows_written", LongType(), False),
        StructField("started_at", TimestampType(), False), StructField("ended_at", TimestampType(), False),
        StructField("duration_seconds", LongType(), False), StructField("error_message", StringType(), True)])
    incoming = spark.createDataFrame([Row(
        pipeline_run_id=pipeline_run_id, run_date=run_date or None, stage=STAGE, status=status,
        rows_read=int(rows_read), rows_written=int(rows_written), started_at=_started, ended_at=ended,
        duration_seconds=int((ended - _started).total_seconds()), error_message=error_message)], schema)
    target = path(audit_lakehouse_id, "control_pipeline_run_log")
    if DeltaTable.isDeltaTable(spark, target):
        (DeltaTable.forPath(spark, target).alias("t").merge(incoming.alias("s"),
         "t.pipeline_run_id=s.pipeline_run_id AND t.stage=s.stage")
         .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        incoming.write.format("delta").mode("overwrite").save(target)


rows_read = rows_written = 0
try:
    transactions, risks, merchants = silver("transactions"), silver("transaction_risk"), silver("merchants")
    sessions, devices, alerts = silver("sessions"), silver("devices"), silver("fraud_alerts")
    rows_read = sum(df.count() for df in [transactions, risks, merchants, sessions, devices, alerts])

    customer_ids = (transactions.select("CustomerID").union(sessions.select("CustomerID"))
                    .union(devices.select("CustomerID")).union(alerts.select("CustomerID")).distinct())
    dim_customer = customer_ids.withColumn("CustomerSK", F.xxhash64("CustomerID"))
    dim_account = transactions.select("AccountID", "CustomerID").dropDuplicates(["AccountID"]).withColumn("AccountSK", F.xxhash64("AccountID"))
    dim_merchant = merchants.withColumn("MerchantSK", F.xxhash64("MerchantID"))
    dim_device = devices.withColumn("DeviceSK", F.xxhash64("DeviceID"))
    date_bounds = transactions.select(F.to_date("TransactionTimestamp").alias("d")).union(sessions.select(F.to_date("LoginTimestamp").alias("d")))
    bounds = date_bounds.agg(F.min("d").alias("min_d"), F.max("d").alias("max_d")).first()
    dim_date = (spark.sql(f"SELECT explode(sequence(to_date('{bounds.min_d}'), to_date('{bounds.max_d}'), interval 1 day)) FullDate")
                .withColumn("DateKey", F.date_format("FullDate", "yyyyMMdd").cast("int"))
                .withColumn("Year", F.year("FullDate")).withColumn("Month", F.month("FullDate"))
                .withColumn("Day", F.dayofmonth("FullDate")).withColumn("DayName", F.date_format("FullDate", "EEEE")))

    fact_transactions = (transactions.join(risks, "TransactionID", "left")
        .join(dim_customer.select("CustomerID", "CustomerSK"), "CustomerID")
        .join(dim_account.select("AccountID", "AccountSK"), "AccountID")
        .join(dim_merchant.select("MerchantID", "MerchantSK"), "MerchantID", "left")
        .withColumn("DateKey", F.date_format("TransactionTimestamp", "yyyyMMdd").cast("int"))
        .select("TransactionID", "CustomerSK", "AccountSK", "MerchantSK", "DeviceID", "DateKey",
                "TransactionTimestamp", "Amount", "Currency", "Channel", "TransactionStatus", "RiskScore", "RiskBand"))
    fact_sessions = (sessions.join(dim_customer.select("CustomerID", "CustomerSK"), "CustomerID")
        .join(dim_device.select("DeviceID", "DeviceSK"), "DeviceID", "left")
        .withColumn("DateKey", F.date_format("LoginTimestamp", "yyyyMMdd").cast("int"))
        .select("SessionID", "CustomerSK", "DeviceSK", "DateKey", "LoginTimestamp", "LogoutTimestamp",
                "AuthenticationMethod", "MfaUsed", "FailedAttempts", "Country", "SessionRiskScore"))
    fact_alerts = (alerts.join(dim_customer.select("CustomerID", "CustomerSK"), "CustomerID")
        .withColumn("DateKey", F.date_format("CreatedTimestamp", "yyyyMMdd").cast("int"))
        .select("AlertID", "CustomerSK", "TransactionID", "DateKey", "CreatedTimestamp", "alertType", "Severity", "Status"))

    # Each independently mirrored source has its own observable watermark.
    # Source-relative windows keep the POC meaningful even when source clocks
    # are intentionally asynchronous; run_date remains lineage, not event time.
    txn_as_of = transactions.agg(F.max(F.to_date("TransactionTimestamp"))).first()[0]
    session_as_of = sessions.agg(F.max(F.to_date("LoginTimestamp"))).first()[0]
    txn_30 = (transactions.filter(F.to_date("TransactionTimestamp").between(F.date_sub(F.lit(txn_as_of), 29), F.lit(txn_as_of)))
              .join(risks, "TransactionID", "left").groupBy("CustomerID").agg(
                  F.count("TransactionID").alias("TransactionCount30D"),
                  F.sum("Amount").alias("TotalTransactionAmount30D"),
                  F.avg("RiskScore").alias("AverageTransactionRiskScore"),
                  F.sum(F.when(F.col("RiskScore") >= 80, 1).otherwise(0)).alias("HighRiskTransactionCount")))
    session_30 = sessions.filter(F.to_date("LoginTimestamp").between(
        F.date_sub(F.lit(session_as_of), 29), F.lit(session_as_of))).groupBy("CustomerID").agg(
        F.sum("FailedAttempts").alias("FailedLoginCount"), F.countDistinct("DeviceID").alias("DistinctDeviceCount"),
        F.sum(F.when(F.col("Country") != "US", 1).otherwise(0)).alias("GeographicAnomalyCount"))
    device_agg = devices.groupBy("CustomerID").agg(F.sum(F.when(~F.col("Trusted"), 1).otherwise(0)).alias("UntrustedDeviceCount"))
    alert_agg = alerts.groupBy("CustomerID").agg(F.count("AlertID").alias("FraudAlertCount"))
    profile = (dim_customer.select("CustomerID", "CustomerSK").join(txn_30, "CustomerID", "left")
               .join(session_30, "CustomerID", "left").join(device_agg, "CustomerID", "left").join(alert_agg, "CustomerID", "left")
               .fillna(0))
    profile = (profile.withColumn("CustomerRiskScore", F.round(F.least(F.lit(100.0),
                F.coalesce("AverageTransactionRiskScore", F.lit(0.0)) * .45 +
                F.least(F.col("FraudAlertCount") * 12.0, F.lit(24.0)) +
                F.least(F.col("FailedLoginCount") * 2.0, F.lit(12.0)) +
                F.least(F.col("UntrustedDeviceCount") * 5.0, F.lit(10.0)) +
                F.least(F.col("GeographicAnomalyCount") * 3.0, F.lit(9.0))), 2))
        .withColumn("CustomerRiskBand", F.when(F.col("CustomerRiskScore") >= 80, "High")
                    .when(F.col("CustomerRiskScore") >= 45, "Medium").otherwise("Low")))

    outputs = {"DimCustomer": dim_customer, "DimAccount": dim_account, "DimMerchant": dim_merchant,
               "DimDevice": dim_device, "DimDate": dim_date, "FactTransactions": fact_transactions,
               "FactDigitalSessions": fact_sessions, "FactFraudAlerts": fact_alerts,
               "AggCustomerRiskProfile": profile}
    for name, df in outputs.items():
        write_gold(df, name)
        rows_written += df.count()
    audit("Succeeded", rows_read, rows_written)
except Exception as exc:
    audit("Failed", rows_read, rows_written, str(exc)[:2000])
    raise

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
