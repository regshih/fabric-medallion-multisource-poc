# Databricks notebook source
"""Create deterministic synthetic source tables in Unity Catalog.

Attach this notebook to a Unity Catalog-enabled cluster or serverless compute.
It uses only managed tables and contains no credentials or storage locations.
"""

# COMMAND ----------
import re
from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "fabric_multisource_poc", "Unity Catalog catalog")
dbutils.widgets.text("schema", "banking_source", "Schema")
dbutils.widgets.text("row_count", "500000", "Transaction rows")
dbutils.widgets.text("customer_count", "50000", "Customers")
dbutils.widgets.text("merchant_count", "5000", "Merchants")
dbutils.widgets.dropdown("create_catalog", "false", ["false", "true"], "Create catalog")

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")


def identifier(name: str) -> str:
    if not IDENTIFIER.fullmatch(name):
        raise ValueError(f"Unsafe Unity Catalog identifier: {name!r}")
    return f"`{name}`"


catalog_raw = dbutils.widgets.get("catalog")
schema_raw = dbutils.widgets.get("schema")
catalog = identifier(catalog_raw)
schema = identifier(schema_raw)
row_count = int(dbutils.widgets.get("row_count"))
customer_count = int(dbutils.widgets.get("customer_count"))
merchant_count = int(dbutils.widgets.get("merchant_count"))
if not (1 <= row_count <= 100_000_000):
    raise ValueError("row_count must be between 1 and 100,000,000")
if min(customer_count, merchant_count) < 1:
    raise ValueError("customer_count and merchant_count must be positive")

if dbutils.widgets.get("create_catalog") == "true":
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema} COMMENT 'Synthetic banking source data for Fabric POC'")


def target(table: str) -> str:
    return f"{catalog}.{schema}.{identifier(table)}"


def save_initial(df, table: str) -> None:
    """Atomically replace only the deterministic initial partition."""
    name = target(table)
    if not spark.catalog.tableExists(f"{catalog_raw}.{schema_raw}.{table}"):
        (df.write.format("delta").partitionBy("SourceBatch").saveAsTable(name))
    else:
        (df.write.format("delta").mode("overwrite")
         .option("replaceWhere", "SourceBatch = 'initial'").saveAsTable(name))
    spark.sql(f"ALTER TABLE {name} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")


base = spark.range(row_count).withColumnRenamed("id", "Ordinal")
customer_num = F.pmod(F.xxhash64(F.lit("customer"), "Ordinal"), F.lit(customer_count)) + 1
merchant_num = F.pmod(F.xxhash64(F.lit("merchant"), "Ordinal"), F.lit(merchant_count)) + 1
account_num = customer_num * 2 - F.pmod(F.xxhash64(F.lit("account"), "Ordinal"), F.lit(2))
device_num = customer_num * 3 - F.pmod(F.xxhash64(F.lit("device"), "Ordinal"), F.lit(3))
seconds = F.pmod(F.xxhash64(F.lit("timestamp"), "Ordinal"), F.lit(2_592_000)).cast("int")

transactions = base.select(
    F.format_string("TXN-%09d", F.col("Ordinal") + 1).alias("TransactionID"),
    F.format_string("ACCT%09d", account_num).alias("AccountID"),
    F.format_string("CUST-%06d", customer_num).alias("CustomerID"),
    F.format_string("MER%06d", merchant_num).alias("MerchantID"),
    (F.to_timestamp(F.lit("2026-01-01T00:00:00Z")) + F.expr("INTERVAL 1 SECOND") * seconds).alias("TransactionTimestamp"),
    ((F.pmod(F.xxhash64(F.lit("amount"), "Ordinal"), F.lit(249_900)) + 100) / 100).cast("decimal(18,2)").alias("Amount"),
    F.element_at(F.array(*map(F.lit, ["USD", "USD", "USD", "CAD", "EUR"])), (F.pmod(F.xxhash64(F.lit("currency"), "Ordinal"), F.lit(5)) + 1).cast("int")).alias("Currency"),
    F.element_at(F.array(*map(F.lit, ["Purchase", "Purchase", "Refund", "Transfer", "ATM"])), (F.pmod(F.xxhash64(F.lit("type"), "Ordinal"), F.lit(5)) + 1).cast("int")).alias("TransactionType"),
    F.element_at(F.array(*map(F.lit, ["Grocery", "Dining", "Travel", "Fuel", "Retail", "Healthcare", "Digital"])), (F.pmod(F.xxhash64(F.lit("category"), "Ordinal"), F.lit(7)) + 1).cast("int")).alias("MerchantCategory"),
    F.element_at(F.array(*map(F.lit, ["Mobile", "Web", "POS", "ATM"])), (F.pmod(F.xxhash64(F.lit("channel"), "Ordinal"), F.lit(4)) + 1).cast("int")).alias("Channel"),
    F.element_at(F.array(*map(F.lit, ["US", "US", "US", "CA", "GB"])), (F.pmod(F.xxhash64(F.lit("country"), "Ordinal"), F.lit(5)) + 1).cast("int")).alias("Country"),
    F.format_string("DEVICE-%06d", device_num).alias("DeviceID"),
    (F.pmod(F.xxhash64(F.lit("card_present"), "Ordinal"), F.lit(2)) == 1).alias("CardPresent"),
    F.element_at(F.array(*map(F.lit, ["Approved", "Approved", "Approved", "Declined", "Pending"])), (F.pmod(F.xxhash64(F.lit("status"), "Ordinal"), F.lit(5)) + 1).cast("int")).alias("TransactionStatus"),
    F.lit("initial").alias("SourceBatch"),
)

risk_score = (F.pmod(F.xxhash64(F.lit("risk"), "Ordinal"), F.lit(10_001)) / 100).cast("decimal(5,2)")
risks = base.select(
    F.format_string("TXN-%09d", F.col("Ordinal") + 1).alias("TransactionID"),
    risk_score.alias("RiskScore"),
    F.when(risk_score >= 80, "High").when(risk_score >= 45, "Medium").otherwise("Low").alias("RiskBand"),
    F.lit("synthetic-risk-v1").alias("ModelVersion"),
    (F.to_timestamp(F.lit("2026-01-01T00:00:30Z")) + F.expr("INTERVAL 1 SECOND") * seconds).alias("ScoredTimestamp"),
    F.when(risk_score >= 80, F.array(F.lit("velocity"), F.lit("merchant_risk")))
     .when(risk_score >= 45, F.array(F.lit("device_novelty"))).otherwise(F.array().cast("array<string>"))
     .alias("RiskFactors"),
    F.lit("initial").alias("SourceBatch"),
)

merchant_base = spark.range(merchant_count).withColumnRenamed("id", "Ordinal")
merchant_risk = F.pmod(F.xxhash64(F.lit("merchant_risk"), "Ordinal"), F.lit(10))
merchants = merchant_base.select(
    F.format_string("MER%06d", F.col("Ordinal") + 1).alias("MerchantID"),
    F.format_string("Synthetic Merchant %06d", F.col("Ordinal") + 1).alias("MerchantName"),
    F.element_at(F.array(*map(F.lit, ["Grocery", "Dining", "Travel", "Fuel", "Retail", "Healthcare", "Digital"])), (F.pmod(F.xxhash64(F.lit("merchant_category"), "Ordinal"), F.lit(7)) + 1).cast("int")).alias("MerchantCategory"),
    F.format_string("Synthetic City %03d", F.pmod(F.xxhash64(F.lit("city"), "Ordinal"), F.lit(100)) + 1).alias("City"),
    F.format_string("S%02d", F.pmod(F.xxhash64(F.lit("state"), "Ordinal"), F.lit(50)) + 1).alias("State"),
    F.element_at(F.array(*map(F.lit, ["US", "US", "US", "CA", "GB"])), (F.pmod(F.xxhash64(F.lit("merchant_country"), "Ordinal"), F.lit(5)) + 1).cast("int")).alias("Country"),
    F.when(merchant_risk == 9, "High").when(merchant_risk >= 6, "Medium").otherwise("Low").alias("MerchantRiskCategory"),
    F.lit("initial").alias("SourceBatch"),
)

save_initial(transactions, "transactions")
save_initial(risks, "transaction_risk")
save_initial(merchants, "merchants")

display(spark.createDataFrame([
    ("transactions", spark.table(target("transactions")).count()),
    ("transaction_risk", spark.table(target("transaction_risk")).count()),
    ("merchants", spark.table(target("merchants")).count()),
], ["object", "row_count"]))
