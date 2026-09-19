"""Biased matrix factorization (Funk SVD) on observed ratings only.

Prediction: mean + user_bias + item_bias + dot(user_factors, item_factors).
Numba compiles the explicit SGD loop; no missing ratings are replaced with zeros.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def epoch(users, items, ratings, order, pu, qi, bu, bi, mean, rate, regularization):
    for index in order:
        user, item = users[index], items[index]
        prediction = mean + bu[user] + bi[item]
        for factor in range(pu.shape[1]):
            prediction += pu[user, factor] * qi[item, factor]
        error = ratings[index] - prediction
        bu[user] += rate * (error - regularization * bu[user])
        bi[item] += rate * (error - regularization * bi[item])
        for factor in range(pu.shape[1]):
            old_user, old_item = pu[user, factor], qi[item, factor]
            pu[user, factor] += rate * (error * old_item - regularization * old_user)
            qi[item, factor] += rate * (error * old_user - regularization * old_item)


@njit(cache=True)
def predict(users, items, indices, pu, qi, bu, bi, mean):
    result = np.empty(len(indices), dtype=np.float32)
    for position, index in enumerate(indices):
        user, item = users[index], items[index]
        value = mean + bu[user] + bi[item]
        for factor in range(pu.shape[1]):
            value += pu[user, factor] * qi[item, factor]
        result[position] = min(5.0, max(.5, value))
    return result


def baseline(users, items, ratings, indices, user_count, item_count, config):
    u, i, r = users[indices], items[indices], ratings[indices]
    mean = float(np.mean(r, dtype=np.float64))
    user_counts = np.bincount(u, minlength=user_count)
    item_counts = np.bincount(i, minlength=item_count)
    bu, bi = np.zeros(user_count), np.zeros(item_count)
    for _ in range(config["baseline_iterations"]):
        bu = np.bincount(u, weights=r - mean - bi[i], minlength=user_count) / (user_counts + config["baseline_user_regularization"])
        bi = np.bincount(i, weights=r - mean - bu[u], minlength=item_count) / (item_counts + config["baseline_item_regularization"])
    return mean, bu.astype(np.float32), bi.astype(np.float32), user_counts, item_counts


def initialize(user_count, item_count, mean, bu, bi, user_counts, item_counts, config):
    rng = np.random.default_rng(config["seed"])
    pu = rng.normal(0, config["initial_stddev"], (user_count, config["factors"])).astype(np.float32)
    qi = rng.normal(0, config["initial_stddev"], (item_count, config["factors"])).astype(np.float32)
    pu[user_counts == 0] = 0
    qi[item_counts == 0] = 0
    return pu, qi, bu.copy(), bi.copy(), mean


def metrics(actual, predicted):
    errors = np.asarray(actual, dtype=np.float64) - np.asarray(predicted, dtype=np.float64)
    if len(errors) == 0 or not np.all(np.isfinite(errors)):
        raise ValueError("Evaluation requires finite predictions for real held-out ratings.")
    return {"rmse": float(np.sqrt(np.mean(errors ** 2))), "mae": float(np.mean(np.abs(errors))), "ratings": len(errors)}
