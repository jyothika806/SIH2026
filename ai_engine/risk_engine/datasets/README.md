# Risk Engine Datasets

This directory contains datasets for training and testing the OptimalRide Risk Engine.

## Dataset Structure

### Training Data Format

Training data should be in CSV or JSON format with the following columns:

```csv
timestamp,road_segment_crime_index,lighting_density_score,route_isolation_factor,distance_from_arterial,driver_30day_rating,driver_7day_rating,completion_rate,harsh_braking_frequency,speeding_frequency,total_rides_last_30days,passenger_verification_level,passenger_trust_score,co_passenger_count,co_passenger_verification_levels,risk_label
```

### Column Descriptions

- **timestamp**: ISO format datetime string of ride request
- **road_segment_crime_index**: Normalized crime index (0.0 - 1.0)
- **lighting_density_score**: Lighting infrastructure score (0.0 - 1.0)
- **route_isolation_factor**: Distance from arterial roads normalized (0.0 - 1.0)
- **distance_from_arterial**: Actual distance in meters
- **driver_30day_rating**: Driver average rating over last 30 days (0.0 - 5.0)
- **driver_7day_rating**: Driver average rating over last 7 days (0.0 - 5.0)
- **completion_rate**: Driver ride completion rate (0.0 - 1.0)
- **harsh_braking_frequency**: Harsh braking events per 100km
- **speeding_frequency**: Speeding events per 100km
- **total_rides_last_30days**: Total rides completed in last 30 days
- **passenger_verification_level**: One of 'none', 'basic', 'standard', 'enhanced'
- **passenger_trust_score**: Passenger trust score (0.0 - 1.0)
- **co_passenger_count**: Number of co-passengers (0 - 6)
- **co_passenger_verification_levels**: JSON array of verification levels for co-passengers
- **risk_label**: Target label (0=Green, 1=Yellow, 2=Red)

## Sample Data Generation

Use the `create_sample_data()` function in `feature_engineering.py` to generate synthetic data for testing:

```python
from feature_engineering import create_sample_data
import pandas as pd

# Generate 1000 samples
sample_data = create_sample_data(n_samples=1000)
sample_data.to_csv('datasets/sample_training_data.csv', index=False)
```

## Data Sources

For production deployment, integrate with:
- Municipal crime databases
- Street lighting infrastructure APIs
- GPS and mapping services for isolation metrics
- Driver telemetry systems
- Passenger verification databases
