# appointments/kalman.py

def kalman_filter_update(measured_value, prev_estimate, prev_covariance, process_var=100.0, measurement_var=200.0):
    """
    A single-step Kalman filter update.
    Returns the updated estimate and covariance.
    """
    # Prediction step (for simplicity, assume state remains the same)
    x_pred = prev_estimate
    p_pred = prev_covariance + process_var

    # Kalman gain
    K = p_pred / (p_pred + measurement_var)
    # Update step
    x_updated = x_pred + K * (measured_value - x_pred)
    p_updated = (1 - K) * p_pred
    return x_updated, p_updated
