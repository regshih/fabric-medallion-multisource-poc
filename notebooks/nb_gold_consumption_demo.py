# Fabric notebook source

# PARAMETERS CELL ********************
pipeline_run_id = "manual"
run_date = ""
workspace_id = ""
gold_lakehouse_id = ""

# CELL ********************
from pyspark.sql import functions as F

if not workspace_id or not gold_lakehouse_id:
    raise ValueError("workspace_id and gold_lakehouse_id are required deployment parameters")


def gold(name):
    location = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{gold_lakehouse_id}/Tables/{name}"
    return spark.read.format("delta").load(location)


# Cross-source customer risk leaderboard. This is the primary Direct Lake / Power BI-ready output.
risk_profile = gold("AggCustomerRiskProfile")
customer_risk_leaderboard = (risk_profile.orderBy(F.desc("CustomerRiskScore"), F.desc("FraudAlertCount"))
    .select("CustomerID", "CustomerRiskBand", "CustomerRiskScore", "TransactionCount30D",
            "TotalTransactionAmount30D", "AverageTransactionRiskScore", "HighRiskTransactionCount",
            "FraudAlertCount", "FailedLoginCount", "DistinctDeviceCount", "UntrustedDeviceCount",
            "GeographicAnomalyCount"))
customer_risk_leaderboard.show(25, truncate=False)

# Executive distribution for a compact semantic-model visual.
risk_band_summary = risk_profile.groupBy("CustomerRiskBand").agg(
    F.count("CustomerID").alias("CustomerCount"),
    F.round(F.avg("CustomerRiskScore"), 2).alias("AverageCustomerRiskScore"),
    F.sum("TotalTransactionAmount30D").alias("TotalTransactionAmount30D"),
    F.sum("FraudAlertCount").alias("FraudAlertCount"))
risk_band_summary.show(truncate=False)

# Drill-through from Cosmos fraud alert to the Databricks transaction and merchant.
alert_drillthrough = (gold("FactFraudAlerts").alias("a")
    .join(gold("FactTransactions").alias("t"), "TransactionID", "left")
    .join(gold("DimMerchant").select("MerchantSK", "MerchantName", "MerchantRiskCategory").alias("m"), "MerchantSK", "left")
    .select("AlertID", "TransactionID", "Severity", "Status", "CreatedTimestamp", "Amount", "RiskScore",
            "RiskBand", "MerchantName", "MerchantRiskCategory")
    .orderBy(F.desc("CreatedTimestamp")))
alert_drillthrough.show(25, truncate=False)

