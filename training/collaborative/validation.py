"""Configuration and chronological partition checks; never fit a model."""
import numpy as np


def validate_config(config):
    integers = ("factors", "max_epochs", "patience", "minimum_item_train_ratings", "validation_sample_size", "fold_in_users", "minimum_history", "baseline_iterations")
    for name in integers:
        if type(config.get(name)) is not int or config[name] <= 0:
            raise ValueError(f"{name} must be a positive integer.")
    for name in ("learning_rate", "regularization", "initial_stddev", "minimum_improvement", "fold_in_factors_regularization", "fold_in_bias_regularization", "baseline_user_regularization", "baseline_item_regularization"):
        if not np.isfinite(config.get(name, float("nan"))) or config[name] <= 0:
            raise ValueError(f"{name} must be finite and positive.")
    if not 0 < config["learning_rate_decay"] <= 1:
        raise ValueError("learning_rate_decay must be in (0, 1].")


def temporal_split(timestamps, train_fraction, validation_fraction):
    if not 0 < train_fraction < train_fraction + validation_fraction < 1:
        raise ValueError("Invalid chronological split fractions.")
    train_cut, test_cut = np.quantile(timestamps, [train_fraction, train_fraction + validation_fraction], method="lower").astype(np.int64)
    train = np.flatnonzero(timestamps < train_cut)
    validation = np.flatnonzero((timestamps >= train_cut) & (timestamps < test_cut))
    test = np.flatnonzero(timestamps >= test_cut)
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("Chronological splits must all be nonempty.")
    return train, validation, test, int(train_cut), int(test_cut)
