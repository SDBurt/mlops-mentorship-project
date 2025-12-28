"""
ML Model Training Assets

This module provides Dagster assets for training ML models using:
- Trino: Query DBT feature tables for training data
- MLflow: Experiment tracking and model registry

Training Flow:
    1. Query feature tables from Trino (DBT-created tables)
    2. Generate/fetch labels (synthetic for demo, real in production)
    3. Train model with sklearn
    4. Log metrics/params/model to MLflow
    5. Champion/challenger: Only promote to Production if F1 beats current champion
    6. Model ready for serving via inference service

Note: For inference, features are retrieved from Feast online store (Redis).
      For training, we query directly from Trino for full historical data.
"""

import os
from datetime import datetime
from typing import Any

import mlflow
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException
import pandas as pd
from dagster import asset, AssetExecutionContext, Config, MaterializeResult, MetadataValue, AssetKey
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)
import numpy as np


class MLTrainingConfig(Config):
    """Configuration for ML training."""
    mlflow_tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
    test_size: float = 0.2
    random_state: int = 42
    # Minimum F1 improvement required to promote challenger to champion
    min_f1_improvement: float = 0.0


def get_champion_f1(client: MlflowClient, model_name: str, context: AssetExecutionContext) -> float | None:
    """
    Get the F1 score of the current Production model (champion).

    Returns None if no Production model exists.
    """
    try:
        # Get the latest version with "Production" alias
        versions = client.get_latest_versions(model_name, stages=["Production"])
        if not versions:
            context.log.info(f"No Production model found for {model_name}")
            return None

        production_version = versions[0]
        run_id = production_version.run_id

        # Get the F1 metric from that run
        run = client.get_run(run_id)
        champion_f1 = run.data.metrics.get("f1")

        if champion_f1 is not None:
            context.log.info(f"Current champion F1: {champion_f1:.4f} (version {production_version.version})")
        return champion_f1

    except MlflowException as e:
        # Model not registered yet
        context.log.info(f"Model {model_name} not yet registered: {e}")
        return None


def promote_if_better(
    client: MlflowClient,
    model_name: str,
    run_id: str,
    challenger_f1: float,
    champion_f1: float | None,
    min_improvement: float,
    context: AssetExecutionContext,
) -> tuple[bool, str | None]:
    """
    Register the model and promote to Production if it beats the champion.

    Returns (promoted: bool, version: str | None)
    """
    # Register the model
    model_uri = f"runs:/{run_id}/model"

    try:
        # Register model (creates if doesn't exist)
        result = mlflow.register_model(model_uri, model_name)
        new_version = result.version
        context.log.info(f"Registered model {model_name} version {new_version}")
    except MlflowException as e:
        context.log.error(f"Failed to register model: {e}")
        return False, None

    # Determine if we should promote
    should_promote = False
    if champion_f1 is None:
        # No current champion - first model becomes Production
        should_promote = True
        context.log.info("No existing champion - promoting first model to Production")
    elif challenger_f1 > champion_f1 + min_improvement:
        should_promote = True
        improvement = challenger_f1 - champion_f1
        context.log.info(
            f"Challenger beats champion: {challenger_f1:.4f} > {champion_f1:.4f} "
            f"(+{improvement:.4f})"
        )
    else:
        context.log.info(
            f"Challenger does not beat champion: {challenger_f1:.4f} <= {champion_f1:.4f} "
            f"(need +{min_improvement:.4f} improvement)"
        )

    if should_promote:
        # Transition new version to Production
        client.transition_model_version_stage(
            name=model_name,
            version=new_version,
            stage="Production",
            archive_existing_versions=True,  # Move old Production to Archived
        )
        context.log.info(f"Promoted {model_name} version {new_version} to Production")
        return True, new_version

    return False, new_version


def query_training_features(context: AssetExecutionContext, query: str) -> pd.DataFrame:
    """Query training features from Trino."""
    from trino.dbapi import connect

    trino_host = os.getenv("TRINO_HOST", "trino")

    with connect(
        host=trino_host,
        port=8080,
        catalog="iceberg",
        schema="data",
        user="dagster",
    ) as conn:
        context.log.info(f"Querying training data from Trino...")
        df = pd.read_sql(query, conn)

    return df


@asset(
    key_prefix=["ml", "training"],
    group_name="ml_training",
    description="Train fraud detection model using DBT features and MLflow tracking",
    compute_kind="python",
    deps=[
        AssetKey("feat_customer_features"),
        AssetKey("feat_merchant_features"),
        AssetKey(["ml", "data_quality", "validate_customer_features"]),
        AssetKey(["ml", "data_quality", "validate_merchant_features"]),
    ],
)
def fraud_detection_model(
    context: AssetExecutionContext,
    config: MLTrainingConfig,
) -> MaterializeResult:
    """
    Train a fraud detection model.

    Queries customer and merchant features from DBT tables,
    trains a RandomForest classifier, and logs to MLflow.
    """
    # Setup MLflow
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    mlflow.set_experiment("fraud-detection")

    # Query training features from DBT tables
    # Use customer features with aggregated merchant stats (avoid CROSS JOIN explosion)
    query = """
    WITH merchant_stats AS (
        SELECT
            AVG(fraud_rate_30d) AS avg_merchant_fraud_rate,
            AVG(high_risk_transaction_pct) AS avg_high_risk_pct,
            AVG(merchant_health_score) AS avg_merchant_health
        FROM iceberg.data.feat_merchant_features
    )
    SELECT
        c.customer_id,
        c.fraud_score_avg,
        c.failure_rate_30d,
        c.total_payments_30d,
        c.high_risk_payment_count,
        m.avg_merchant_fraud_rate AS merchant_fraud_rate,
        m.avg_high_risk_pct AS high_risk_transaction_pct,
        m.avg_merchant_health AS merchant_health_score
    FROM iceberg.data.feat_customer_features c
    CROSS JOIN merchant_stats m
    """

    context.log.info("Fetching training features from Trino...")
    training_data = query_training_features(context, query)

    if training_data.empty:
        context.log.warning("No training data found. Ensure DBT feature tables exist.")
        return MaterializeResult(
            metadata={"status": "skipped", "reason": "no_training_data"}
        )

    context.log.info(f"Retrieved {len(training_data)} training samples")

    # Generate synthetic labels for demo
    # In production, labels come from: fraud reviews, chargebacks, manual labels
    np.random.seed(config.random_state)
    fraud_probability = (
        training_data["fraud_score_avg"].fillna(0) * 0.5 +
        training_data["merchant_fraud_rate"].fillna(0) * 0.3 +
        training_data["high_risk_transaction_pct"].fillna(0) * 0.2
    ).clip(0, 1)
    training_data["is_fraud"] = (np.random.random(len(training_data)) < fraud_probability).astype(int)

    # Ensure we have enough samples for training (minimum 20)
    if len(training_data) < 20:
        context.log.warning(f"Insufficient training data ({len(training_data)} samples). Need at least 20.")
        return MaterializeResult(
            metadata={"status": "skipped", "reason": "insufficient_data", "samples": len(training_data)}
        )

    # Ensure both classes are present
    if training_data["is_fraud"].nunique() < 2:
        context.log.warning("Only one class in labels. Adding synthetic minority class samples.")
        minority_count = max(1, int(len(training_data) * 0.2))
        flip_indices = training_data.sample(minority_count, random_state=config.random_state).index
        training_data.loc[flip_indices, "is_fraud"] = 1 - training_data.loc[flip_indices, "is_fraud"]

    # Prepare features
    feature_cols = [
        "fraud_score_avg",
        "failure_rate_30d",
        "total_payments_30d",
        "high_risk_payment_count",
        "merchant_fraud_rate",
        "high_risk_transaction_pct",
        "merchant_health_score",
    ]

    X = training_data[feature_cols].fillna(0)
    y = training_data["is_fraud"]

    # Split data - use stratify only if we have enough samples per class
    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.test_size, random_state=config.random_state, stratify=stratify
    )

    context.log.info(f"Training set: {len(X_train)}, Test set: {len(X_test)}")
    context.log.info(f"Fraud rate: {y.mean()*100:.1f}%")

    # Model registry name
    model_name = "fraud-detection"

    # Get current champion's F1 score for comparison
    client = MlflowClient(tracking_uri=config.mlflow_tracking_uri)
    champion_f1 = get_champion_f1(client, model_name, context)

    # Train model with MLflow tracking
    with mlflow.start_run(run_name=f"fraud-rf-{datetime.now().strftime('%Y%m%d-%H%M')}"):
        # Log parameters
        params = {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 5,
            "random_state": config.random_state,
            "class_weight": "balanced",
        }
        mlflow.log_params(params)
        mlflow.log_param("features", ",".join(feature_cols))

        # Train
        context.log.info("Training RandomForest model...")
        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1] if len(np.unique(y)) > 1 else y_pred

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "fraud_rate": float(y.mean()),
        }

        # Add AUC if we have both classes
        if len(np.unique(y_test)) > 1 and len(np.unique(y_pred)) > 1:
            metrics["auc_roc"] = roc_auc_score(y_test, y_prob)

        mlflow.log_metrics(metrics)

        # Log feature importance
        importance_df = pd.DataFrame({
            "feature": feature_cols,
            "importance": model.feature_importances_
        }).sort_values("importance", ascending=False)

        context.log.info(f"Feature importances:\n{importance_df.to_string()}")

        # Log model
        mlflow.sklearn.log_model(model, "model")

        run_id = mlflow.active_run().info.run_id
        context.log.info(f"Model logged to MLflow. Run ID: {run_id}")

    # Champion/Challenger: Register and promote if better
    challenger_f1 = metrics["f1"]
    promoted, version = promote_if_better(
        client=client,
        model_name=model_name,
        run_id=run_id,
        challenger_f1=challenger_f1,
        champion_f1=champion_f1,
        min_improvement=config.min_f1_improvement,
        context=context,
    )

    return MaterializeResult(
        metadata={
            "run_id": MetadataValue.text(run_id),
            "model_version": MetadataValue.text(version) if version else MetadataValue.text("N/A"),
            "promoted_to_production": MetadataValue.bool(promoted),
            "challenger_f1": MetadataValue.float(challenger_f1),
            "champion_f1": MetadataValue.float(champion_f1) if champion_f1 else MetadataValue.text("N/A (first model)"),
            "accuracy": MetadataValue.float(metrics["accuracy"]),
            "precision": MetadataValue.float(metrics["precision"]),
            "recall": MetadataValue.float(metrics["recall"]),
            "f1_score": MetadataValue.float(metrics["f1"]),
            "training_samples": MetadataValue.int(int(metrics["training_samples"])),
            "fraud_rate": MetadataValue.float(metrics["fraud_rate"]),
            "mlflow_url": MetadataValue.url(f"{config.mlflow_tracking_uri}/#/experiments/1/runs/{run_id}"),
        }
    )


@asset(
    key_prefix=["ml", "training"],
    group_name="ml_training",
    description="Train churn prediction model using DBT features and MLflow tracking",
    compute_kind="python",
    deps=[
        AssetKey("feat_customer_features"),
        AssetKey(["ml", "data_quality", "validate_customer_features"]),
    ],
)
def churn_prediction_model(
    context: AssetExecutionContext,
    config: MLTrainingConfig,
) -> MaterializeResult:
    """
    Train a customer churn prediction model.

    Predicts likelihood of customer stopping payments based on
    payment behavior features.
    """
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    mlflow.set_experiment("churn-prediction")

    # Query customer features for churn prediction
    query = """
    SELECT
        customer_id,
        total_payments_30d,
        total_payments_90d,
        failure_rate_30d,
        consecutive_failures,
        recovery_rate_30d,
        days_since_last_payment,
        payment_method_count,
        customer_tier
    FROM iceberg.data.feat_customer_features
    """

    context.log.info("Fetching training features from Trino...")
    training_data = query_training_features(context, query)

    if training_data.empty:
        context.log.warning("No training data found")
        return MaterializeResult(metadata={"status": "skipped", "reason": "no_data"})

    context.log.info(f"Retrieved {len(training_data)} training samples")

    # Generate synthetic churn labels
    np.random.seed(config.random_state)
    churn_probability = (
        training_data["failure_rate_30d"].fillna(0) * 0.4 +
        (training_data["days_since_last_payment"].fillna(0) / 30).clip(0, 1) * 0.3 +
        (1 - training_data["recovery_rate_30d"].fillna(1)) * 0.3
    ).clip(0, 1)
    training_data["churned"] = (np.random.random(len(training_data)) < churn_probability).astype(int)

    # Ensure we have both classes for training (minimum 10 samples of each)
    if len(training_data) < 20:
        context.log.warning(f"Insufficient training data ({len(training_data)} samples). Need at least 20.")
        return MaterializeResult(
            metadata={"status": "skipped", "reason": "insufficient_data", "samples": len(training_data)}
        )

    # Ensure both classes are present
    if training_data["churned"].nunique() < 2:
        context.log.warning("Only one class in labels. Adding synthetic minority class samples.")
        # Force at least 20% minority class
        minority_count = max(1, int(len(training_data) * 0.2))
        flip_indices = training_data.sample(minority_count, random_state=config.random_state).index
        training_data.loc[flip_indices, "churned"] = 1 - training_data.loc[flip_indices, "churned"]

    feature_cols = [
        "total_payments_30d",
        "total_payments_90d",
        "failure_rate_30d",
        "consecutive_failures",
        "recovery_rate_30d",
        "days_since_last_payment",
        "payment_method_count",
    ]

    X = training_data[feature_cols].fillna(0)
    y = training_data["churned"]

    # Use stratify only if we have enough samples per class
    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.test_size, random_state=config.random_state, stratify=stratify
    )

    context.log.info(f"Training set: {len(X_train)}, Test set: {len(X_test)}")
    context.log.info(f"Churn rate: {y.mean()*100:.1f}%")

    # Model registry name
    model_name = "churn-prediction"

    # Get current champion's F1 score for comparison
    client = MlflowClient(tracking_uri=config.mlflow_tracking_uri)
    champion_f1 = get_champion_f1(client, model_name, context)

    with mlflow.start_run(run_name=f"churn-gb-{datetime.now().strftime('%Y%m%d-%H%M')}"):
        params = {
            "n_estimators": 100,
            "max_depth": 5,
            "learning_rate": 0.1,
            "random_state": config.random_state,
        }
        mlflow.log_params(params)
        mlflow.log_param("features", ",".join(feature_cols))

        context.log.info("Training GradientBoosting model...")
        model = GradientBoostingClassifier(**params)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "churn_rate": float(y.mean()),
        }
        mlflow.log_metrics(metrics)

        # Log model
        mlflow.sklearn.log_model(model, "model")
        run_id = mlflow.active_run().info.run_id

        context.log.info(f"Model logged to MLflow. Run ID: {run_id}")

    # Champion/Challenger: Register and promote if better
    challenger_f1 = metrics["f1"]
    promoted, version = promote_if_better(
        client=client,
        model_name=model_name,
        run_id=run_id,
        challenger_f1=challenger_f1,
        champion_f1=champion_f1,
        min_improvement=config.min_f1_improvement,
        context=context,
    )

    return MaterializeResult(
        metadata={
            "run_id": MetadataValue.text(run_id),
            "model_version": MetadataValue.text(version) if version else MetadataValue.text("N/A"),
            "promoted_to_production": MetadataValue.bool(promoted),
            "challenger_f1": MetadataValue.float(challenger_f1),
            "champion_f1": MetadataValue.float(champion_f1) if champion_f1 else MetadataValue.text("N/A (first model)"),
            "accuracy": MetadataValue.float(metrics["accuracy"]),
            "precision": MetadataValue.float(metrics["precision"]),
            "recall": MetadataValue.float(metrics["recall"]),
            "f1_score": MetadataValue.float(metrics["f1"]),
            "churn_rate": MetadataValue.float(metrics["churn_rate"]),
        }
    )
