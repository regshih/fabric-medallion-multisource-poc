# Databricks notebook source
"""Apply a deterministic, safely repeatable second Delta batch."""

# COMMAND ----------
import re
from delta.tables import DeltaTable
from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "fabric_multisource_poc", "Unity Catalog catalog")
dbutils.widgets.text("schema", "banking_source", "Schema")
dbutils.widgets.text("base_row_count", "500000", "Initial rows")
dbutils.widgets.text("customer_count", "50000", "Customers used by seed")
dbutils.widgets.text("merchant_count", "5000", "Merchants used by seed")
dbutils.widgets.text("new_transaction_count", "10000", "New transactions")
dbutils.widgets.text("risk_updates", "1000", "Existing risk rows to update")
dbutils.widgets.text("batch_id", "incremental_001", "Stable batch id")

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")


def ident(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe identifier: {value!r}")
    return f"`{value}`"


catalog_raw, schema_raw = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
catalog, schema = ident(catalog_raw), ident(schema_raw)
base_count = int(dbutils.widgets.get("base_row_count"))
customer_count = int(dbutils.widgets.get("customer_count"))
merchant_count = int(dbutils.widgets.get("merchant_count"))
new_count = int(dbutils.widgets.get("new_transaction_count"))
risk_updates = int(dbutils.widgets.get("risk_updates"))
batch_id = dbutils.widgets.get("batch_id")
if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", batch_id):
    raise ValueError("batch_id must contain only letters, numbers, underscore, or hyphen")
if min(base_count, customer_count, merchant_count, new_count, risk_updates) < 1 or risk_updates > base_count:
    raise ValueError("counts must be positive and risk_updates cannot exceed base_row_count")


def table(name: str) -> str:
    return f"{catalog}.{schema}.{ident(name)}"


required = ("transactions", "transaction_risk", "merchants")
missing = [name for name in required if not spark.catalog.tableExists(f"{catalog_raw}.{schema_raw}.{name}")]
if missing:
    raise RuntimeError(f"Seed tables first; missing: {missing}")

ordinal = spark.range(base_count, base_count + new_count).withColumnRenamed("id", "Ordinal")
customer_num = F.pmod(F.xxhash64(F.lit("customer"), "Ordinal"), F.lit(customer_count)) + 1
merchant_num = F.pmod(F.xxhash64(F.lit("merchant"), "Ordinal"), F.lit(merchant_count + 1)) + 1
account_num = customer_num * 2 - F.pmod(F.xxhash64(F.lit("account"), "Ordinal"), F.lit(2))
device_num = customer_num * 3 - F.pmod(F.xxhash64(F.lit("device"), "Ordinal"), F.lit(3))
seconds = F.pmod(F.xxhash64(F.lit("timestamp"), "Ordinal"), F.lit(86_400)).cast("int")
risk_score = (F.pmod(F.xxhash64(F.lit("risk"), "Ordinal"), F.lit(10_001)) / 100).cast("decimal(5,2)")

new_transactions = ordinal.select(
    F.format_string("TXN-%09d", F.col("Ordinal") + 1).alias("TransactionID"),
    F.format_string("ACCT%09d", account_num).alias("AccountID"),
    F.format_string("CUST-%06d", customer_num).alias("CustomerID"),
    F.format_string("MER%06d", merchant_num).alias("MerchantID"),
    (F.to_timestamp(F.lit("2026-02-01T00:00:00Z")) + F.expr("INTERVAL 1 SECOND") * seconds).alias("TransactionTimestamp"),
    ((F.pmod(F.xxhash64(F.lit("amount"), "Ordinal"), F.lit(249_900)) + 100) / 100).cast("decimal(18,2)").alias("Amount"),
    F.lit("USD").alias("Currency"), F.lit("Purchase").alias("TransactionType"),
    F.lit("Digital").alias("MerchantCategory"), F.lit("Mobile").alias("Channel"),
    F.lit("US").alias("Country"), F.format_string("DEVICE-%06d", device_num).alias("DeviceID"),
    F.lit(False).alias("CardPresent"), F.lit("Approved").alias("TransactionStatus"),
    F.lit(batch_id).alias("SourceBatch"),
)

new_risks = ordinal.select(
    F.format_string("TXN-%09d", F.col("Ordinal") + 1).alias("TransactionID"), risk_score.alias("RiskScore"),
    F.when(risk_score >= 80, "High").when(risk_score >= 45, "Medium").otherwise("Low").alias("RiskBand"),
    F.lit("synthetic-risk-v2").alias("ModelVersion"),
    (F.to_timestamp(F.lit("2026-02-01T00:00:30Z")) + F.expr("INTERVAL 1 SECOND") * seconds).alias("ScoredTimestamp"),
    F.array(F.lit("incremental_scoring")).alias("RiskFactors"), F.lit(batch_id).alias("SourceBatch"),
)

DeltaTable.forName(spark, table("transactions")).alias("t").merge(
    new_transactions.alias("s"), "t.TransactionID = s.TransactionID"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
DeltaTable.forName(spark, table("transaction_risk")).alias("t").merge(
    new_risks.alias("s"), "t.TransactionID = s.TransactionID"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

# Update a stable set of existing scores; repeated execution produces the same state.
updates = spark.range(risk_updates).select(
    F.format_string("TXN-%09d", F.col("id") + 1).alias("TransactionID"),
    F.lit(95.00).cast("decimal(5,2)").alias("RiskScore"), F.lit("High").alias("RiskBand"),
    F.lit("synthetic-risk-v2").alias("ModelVersion"), F.to_timestamp(F.lit("2026-02-01T12:00:00Z")).alias("ScoredTimestamp"),
    F.array(F.lit("controlled_score_change")).alias("RiskFactors"), F.lit(batch_id).alias("SourceBatch"),
)
DeltaTable.forName(spark, table("transaction_risk")).alias("t").merge(
    updates.alias("s"), "t.TransactionID = s.TransactionID"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

new_merchant_id = f"MER{merchant_count + 1:06d}"
new_merchant = spark.createDataFrame([(
    new_merchant_id, f"Synthetic Merchant {merchant_count + 1:06d}", "Digital", "Synthetic City 101", "S51", "US", "High", batch_id
)], spark.table(table("merchants")).schema)
DeltaTable.forName(spark, table("merchants")).alias("t").merge(
    new_merchant.alias("s"), "t.MerchantID = s.MerchantID"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

display(spark.sql(f"""
SELECT 'transactions' object, count(*) rows FROM {table('transactions')}
UNION ALL SELECT 'transaction_risk', count(*) FROM {table('transaction_risk')}
UNION ALL SELECT 'merchants', count(*) FROM {table('merchants')}
"""))
