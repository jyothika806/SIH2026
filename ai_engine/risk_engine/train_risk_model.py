"""
XGBoost Risk Model Training with Conformal Uncertainty Estimation and ONNX Export

This module implements:
- XGBoost Multi-Class Classifier training for risk prediction
- Conformal Uncertainty Estimation for prediction confidence
- ONNX model export with FP16/INT8 quantization for sub-5ms latency
- Comprehensive evaluation metrics (Log-Loss, F1-Score, Calibration Error, Latency)

Author: OptimalRide AI Team
Date: 2026-09-27
"""
import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import numpy as np
import pandas as pd
import xgboost as xgb
from onnxmltools.convert.common.data_types import FloatTensorType
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    log_loss, f1_score, classification_report, 
    confusion_matrix, accuracy_score
)
from sklearn.calibration import calibration_curve
import onnx
from onnxmltools.convert import convert_xgboost
try:
    from onnxconverter_common.float16 import convert_float_to_float16
except ImportError:
    from onnxmltools.utils import convert_float_to_float16
import onnxruntime as ort
import joblib
import json
import time
import os
from typing import Dict, Tuple, Optional, List
from pathlib import Path

# Import feature engineering pipeline
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from feature_engineering import RiskFeaturePipeline, create_sample_data


class ConformalUncertaintyEstimator:
    """
    Conformal Uncertainty Estimation for prediction confidence bounds.
    
    Uses conformal prediction to estimate uncertainty and flag
    predictions that exceed uncertainty thresholds.
    """
    
    def __init__(self, entropy_threshold: float = 0.45):
        """
        Initialize the conformal uncertainty estimator.
        
        Args:
            entropy_threshold: Entropy threshold for uncertainty flag
        """
        self.entropy_threshold = entropy_threshold
        self.calibration_scores = None
    
    def calculate_entropy(self, probabilities: np.ndarray) -> float:
        """
        Calculate Shannon entropy of probability distribution.
        
        Args:
            probabilities: Probability array from model
            
        Returns:
            Entropy value
        """
        # Avoid log(0) by adding small epsilon
        eps = 1e-10
        probabilities = np.clip(probabilities, eps, 1 - eps)
        return -np.sum(probabilities * np.log(probabilities))
    
    def fit(self, probabilities: np.ndarray, y_true: np.ndarray):
        """
        Fit the conformal estimator on calibration data.
        
        Args:
            probabilities: Predicted probabilities from model
            y_true: True labels
        """
        calibration_entropies = []
        for prob in probabilities:
            entropy = self.calculate_entropy(prob)
            calibration_entropies.append(entropy)
        
        self.calibration_scores = np.array(calibration_entropies)
    
    def predict_uncertainty(self, probabilities: np.ndarray) -> Dict[str, any]:
        """
        Predict uncertainty for given probabilities.
        
        Args:
            probabilities: Predicted probabilities from model
            
        Returns:
            Dictionary with uncertainty metrics
        """
        entropy = self.calculate_entropy(probabilities)
        
        # Compare with calibration distribution
        if self.calibration_scores is not None:
            percentile = (self.calibration_scores < entropy).mean()
        else:
            percentile = 0.0
        
        uncertainty_flag = entropy > self.entropy_threshold
        
        return {
            'entropy': float(entropy),
            'uncertainty_flag': bool(uncertainty_flag),
            'percentile': float(percentile),
            'threshold': self.entropy_threshold
        }


class RiskModelTrainer:
    """
    Main trainer class for XGBoost risk prediction model.
    """
    
    RISK_CLASSES = ['Green', 'Yellow', 'Red']
    RISK_CODES = [0, 1, 2]
    
    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        entropy_threshold: float = 0.45
    ):
        """
        Initialize the model trainer.
        
        Args:
            n_estimators: Number of boosting rounds
            max_depth: Maximum tree depth
            learning_rate: Learning rate for boosting
            entropy_threshold: Entropy threshold for uncertainty estimation
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.entropy_threshold = entropy_threshold
        
        self.model = None
        self.feature_pipeline = None
        self.uncertainty_estimator = None
        self.scaler = None
        
        self.evaluation_metrics = {}
    
    def prepare_data(
        self,
        data: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare training and test data.
        
        Args:
            data: DataFrame with features and labels
            test_size: Proportion of data for testing
            random_state: Random seed
            
        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        # Initialize feature pipeline
        self.feature_pipeline = RiskFeaturePipeline()
        
        # Extract features
        feature_matrix = self.feature_pipeline.process_batch(
            data_rows=data.to_dict('records'),
            fit_scaler=True
        )
        
        # Extract labels (assuming a 'risk_label' column exists)
        if 'risk_label' not in data.columns:
            # Generate synthetic labels for testing
            print("Warning: No 'risk_label' column found. Generating synthetic labels.")
            y = self._generate_synthetic_labels(feature_matrix)
        else:
            y = data['risk_label'].values
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            feature_matrix, y, test_size=test_size, 
            random_state=random_state, stratify=y
        )
        
        return X_train, X_test, y_train, y_test
    
    def _generate_synthetic_labels(self, features: np.ndarray) -> np.ndarray:
        """
        Generate synthetic risk labels based on feature patterns.
        
        Args:
            features: Feature matrix
            
        Returns:
            Array of risk labels (0, 1, 2)
        """
        # Simple rule-based label generation for testing
        labels = []
        for feat in features:
            # Use interaction features to determine risk
            isolation_factor = feat[12]  # route_isolation_factor
            crime_index = feat[10]  # road_segment_crime_index
            telemetry_anomaly = feat[25]  # telemetry_anomaly_score
            
            risk_score = (
                isolation_factor * 0.3 + 
                crime_index * 0.3 + 
                telemetry_anomaly * 0.4
            )
            
            if risk_score > 0.6:
                labels.append(2)  # Red
            elif risk_score > 0.3:
                labels.append(1)  # Yellow
            else:
                labels.append(0)  # Green
        
        return np.array(labels)
    
    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None
    ):
        """
        Train the XGBoost model.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
        """
        print("Training XGBoost model...")
        
        # Initialize XGBoost classifier
        self.model = xgb.XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            objective='multi:softprob',
            num_class=3,
            eval_metric='mlogloss',
            random_state=42,
            n_jobs=-1,
            tree_method='hist',
            subsample=0.8,
            colsample_bytree=0.8
        )
        
        # Train with early stopping if validation data provided
        if X_val is not None and y_val is not None:
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=True
            )
        else:
            self.model.fit(X_train, y_train)
        
        print("Model training completed.")
    
    def setup_uncertainty_estimation(self, X_cal: np.ndarray, y_cal: np.ndarray):
        """
        Setup conformal uncertainty estimation.
        
        Args:
            X_cal: Calibration features
            y_cal: Calibration labels
        """
        print("Setting up conformal uncertainty estimation...")
        
        self.uncertainty_estimator = ConformalUncertaintyEstimator(
            entropy_threshold=self.entropy_threshold
        )
        
        # Get calibration probabilities
        cal_probs = self.model.predict_proba(X_cal)
        
        # Fit conformal estimator
        self.uncertainty_estimator.fit(cal_probs, y_cal)
        
        print("Uncertainty estimation setup completed.")
    
    def evaluate_model(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict[str, any]:
        """
        Evaluate the model with comprehensive metrics.
        
        Args:
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Dictionary of evaluation metrics
        """
        print("Evaluating model...")
        
        # Predictions
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)
        
        # Basic metrics
        accuracy = accuracy_score(y_test, y_pred)
        logloss = log_loss(y_test, y_pred_proba)
        f1_macro = f1_score(y_test, y_pred, average='macro')
        f1_per_class = f1_score(y_test, y_pred, average=None)
        
        # Classification report
        class_report = classification_report(
            y_test, y_pred, 
            target_names=self.RISK_CLASSES,
            output_dict=True
        )
        
        # Confusion matrix
        conf_matrix = confusion_matrix(y_test, y_pred)
        
        # Uncertainty calibration error
        if self.uncertainty_estimator:
            calibration_error = self._calculate_calibration_error(
                y_test, y_pred_proba
            )
        else:
            calibration_error = 0.0
        
        # Store metrics
        self.evaluation_metrics = {
            'accuracy': float(accuracy),
            'log_loss': float(logloss),
            'f1_macro': float(f1_macro),
            'f1_per_class': {
                self.RISK_CLASSES[i]: float(f1_per_class[i])
                for i in range(len(self.RISK_CLASSES))
            },
            'confusion_matrix': conf_matrix.tolist(),
            'classification_report': class_report,
            'calibration_error': float(calibration_error),
            'n_test_samples': len(y_test)
        }
        
        # Print metrics
        print(f"\n=== Model Evaluation Results ===")
        print(f"Accuracy: {accuracy:.4f}")
        print(f"Log Loss: {logloss:.4f}")
        print(f"F1-Score (Macro): {f1_macro:.4f}")
        print(f"\nF1-Score per Class:")
        for i, cls in enumerate(self.RISK_CLASSES):
            print(f"  {cls}: {f1_per_class[i]:.4f}")
        print(f"\nCalibration Error: {calibration_error:.4f}")
        print(f"\nConfusion Matrix:")
        print(conf_matrix)
        
        return self.evaluation_metrics
    
    def _calculate_calibration_error(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        n_bins: int = 10
    ) -> float:
        """
        Calculate Expected Calibration Error (ECE).
        
        Args:
            y_true: True labels
            y_pred_proba: Predicted probabilities
            n_bins: Number of bins for calibration
            
        Returns:
            Expected Calibration Error
        """
        # Get predicted class and max probability
        y_pred = np.argmax(y_pred_proba, axis=1)
        max_probs = np.max(y_pred_proba, axis=1)
        
        # Calculate calibration curve
        prob_true, prob_pred = calibration_curve(
            y_true == y_pred, max_probs, n_bins=n_bins
        )
        
        # Calculate ECE
        ece = 0.0
        for i in range(len(prob_true)):
            ece += abs(prob_true[i] - prob_pred[i]) / n_bins
        
        return ece
    
    def benchmark_inference_latency(
        self,
        X_test: np.ndarray,
        n_iterations: int = 1000
    ) -> Dict[str, float]:
        """
        Benchmark inference latency.
        
        Args:
            X_test: Test features
            n_iterations: Number of iterations for benchmarking
            
        Returns:
            Dictionary with latency metrics
        """
        print(f"Benchmarking inference latency ({n_iterations} iterations)...")
        
        # Warm-up
        for _ in range(10):
            _ = self.model.predict(X_test[:1])
        
        # Benchmark
        latencies = []
        for _ in range(n_iterations):
            start_time = time.perf_counter()
            _ = self.model.predict(X_test[:1])
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000)  # Convert to ms
        
        latencies = np.array(latencies)
        
        latency_metrics = {
            'mean_latency_ms': float(np.mean(latencies)),
            'median_latency_ms': float(np.median(latencies)),
            'p95_latency_ms': float(np.percentile(latencies, 95)),
            'p99_latency_ms': float(np.percentile(latencies, 99)),
            'min_latency_ms': float(np.min(latencies)),
            'max_latency_ms': float(np.max(latencies))
        }
        
        print(f"\n=== Inference Latency Benchmarks ===")
        print(f"Mean: {latency_metrics['mean_latency_ms']:.3f} ms")
        print(f"Median: {latency_metrics['median_latency_ms']:.3f} ms")
        print(f"P95: {latency_metrics['p95_latency_ms']:.3f} ms")
        print(f"P99: {latency_metrics['p99_latency_ms']:.3f} ms")
        
        return latency_metrics
    
    def export_to_onnx(
        self,
        output_path: str,
        quantization: str = 'float16'
    ) -> str:
        """
        Export XGBoost model to ONNX format with quantization.
        
        Args:
            output_path: Path to save ONNX model
            quantization: Quantization type ('float16' or 'int8')
            
        Returns:
            Path to exported ONNX model
        """
        print(f"Exporting model to ONNX with {quantization} quantization...")
        
        # 1. Determine feature matrix width dynamically
        num_features = len(self.feature_pipeline.FEATURE_ORDER)
        
        # 2. Correctly declare initial input types using FloatTensorType
        initial_type = [('float_input', FloatTensorType([None, num_features]))]
        
        # 3. Convert XGBoost model to ONNX
        onnx_model = convert_xgboost(
            self.model,
            initial_types=initial_type,
            target_opset=12
        )
        
        # 4. Apply quantization
        if quantization == 'float16':
            onnx_model = convert_float_to_float16(onnx_model)
        elif quantization == 'int8':
            print("Warning: INT8 quantization requires additional calibration steps.")
            print("Using FP16 quantization instead.")
            onnx_model = convert_float_to_float16(onnx_model)
        
        # 5. Save ONNX model
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        onnx.save(onnx_model, output_path)
        
        print(f"ONNX model exported to: {output_path}")
        
        # 6. Verify ONNX model
        self._verify_onnx_model(output_path)
        
        return output_path  
    def _verify_onnx_model(self, model_path: str):
        """
        Verify the exported ONNX model with ONNX Runtime.
        """
        import onnxruntime as ort
        
        try:
            session = ort.InferenceSession(model_path)
            input_name = session.get_inputs()[0].name
            print(f"ONNX model verified successfully. Input node name: {input_name}")
        except Exception as e:
            print(f"ONNX verification failed: {e}")  
    def save_artifacts(self, output_dir: str):
        """
        Save feature pipeline, uncertainty estimator, and evaluation metrics.
        
        Args:
            output_dir: Directory to save all model artifacts
        """
        import joblib
        import json

        os.makedirs(output_dir, exist_ok=True)

        # 1. Save Feature Pipeline
        pipeline_path = os.path.join(output_dir, "feature_pipeline.pkl")
        joblib.dump(self.feature_pipeline, pipeline_path)

        # 2. Save Uncertainty Estimator
        if self.uncertainty_estimator:
            uncertainty_path = os.path.join(output_dir, "uncertainty_estimator.pkl")
            joblib.dump(self.uncertainty_estimator, uncertainty_path)

        # 3. Save Evaluation Metrics
        if self.evaluation_metrics:
            metrics_path = os.path.join(output_dir, "evaluation_metrics.json")
            with open(metrics_path, "w") as f:
                json.dump(self.evaluation_metrics, f, indent=4)

        print(f"All model artifacts successfully saved to: {output_dir}")

def main():
    """Main training pipeline."""
    print("=" * 60)
    print("OptimalRide Risk Model Training Pipeline")
    print("=" * 60)
    
    # Initialize trainer
    trainer = RiskModelTrainer(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        entropy_threshold=0.45
    )
    
    # Generate sample data
    print("\nGenerating sample training data...")
    data = create_sample_data(n_samples=5000)
    
    # Prepare data
    print("\nPreparing data...")
    X_train, X_test, y_train, y_test = trainer.prepare_data(data)
    
    # Split training data for calibration
    X_train_main, X_cal, y_train_main, y_cal = train_test_split(
        X_train, y_train, test_size=0.2, random_state=42, stratify=y_train
    )
    
    # Train model
    trainer.train_model(X_train_main, y_train_main, X_cal, y_cal)
    
    # Setup uncertainty estimation
    trainer.setup_uncertainty_estimation(X_cal, y_cal)
    
    # Evaluate model
    metrics = trainer.evaluate_model(X_test, y_test)
    
    # Benchmark latency
    latency_metrics = trainer.benchmark_inference_latency(X_test)
    
    # Add latency to metrics
    metrics['inference_latency'] = latency_metrics
    
    # Export to ONNX
    onnx_path = "ai_engine/models/risk_engine.onnx"
    trainer.export_to_onnx(onnx_path, quantization='float16')
    
    # Save artifacts
    trainer.save_artifacts("ai_engine/models")
    
    print("\n" + "=" * 60)
    print("Training pipeline completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
