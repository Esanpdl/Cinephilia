"""Inference mathematics shared with offline evaluation; no training dependencies."""
import numpy as np


def fold_profile(item_factors, item_bias, mean, rows, ratings, factor_regularization, bias_regularization):
    """Infer one user's bias/taste vector from fixed movie factors and 0.5–5 ratings."""
    factors = item_factors[rows].astype(np.float64)
    design = np.column_stack((np.ones(len(rows)), factors))
    residual = np.asarray(ratings, dtype=np.float64) - mean - item_bias[rows]
    penalty = np.full(design.shape[1], factor_regularization, dtype=np.float64)
    penalty[0] = bias_regularization
    normal = design.T @ design
    normal.flat[::normal.shape[0] + 1] += penalty
    coefficients = np.linalg.solve(normal, design.T @ residual)
    return float(coefficients[0]), coefficients[1:]


def predict_items(item_factors, item_bias, mean, bias, factors, rows):
    return np.clip(mean + bias + item_bias[rows] + item_factors[rows] @ factors, .5, 5)
