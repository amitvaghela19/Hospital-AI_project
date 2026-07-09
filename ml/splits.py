from __future__ import annotations

from sklearn.model_selection import train_test_split


def make_split(data, y, split_name: str, splits: dict, random_state: int = 42):
    train_frac, val_frac = splits[split_name]
    if val_frac is None:
        X_train, X_test, y_train, y_test = train_test_split(
            data, y, train_size=train_frac, stratify=y, random_state=random_state,
        )
        return X_train, None, X_test, y_train, None, y_test
    X_train, X_temp, y_train, y_temp = train_test_split(
        data, y, train_size=train_frac, stratify=y, random_state=random_state,
    )
    relative_val = val_frac / (1 - train_frac)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, train_size=relative_val, stratify=y_temp, random_state=random_state,
    )
    return X_train, X_val, X_test, y_train, y_val, y_test
