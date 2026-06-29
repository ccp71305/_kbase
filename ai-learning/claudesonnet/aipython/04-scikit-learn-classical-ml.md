# Scikit-Learn & Classical Machine Learning in Python

> **Series:** AI/Python Learning Path | **Module 04**
> **Prerequisites:** NumPy, Pandas, Matplotlib (Modules 01–03)
> **Estimated reading time:** 60–90 minutes

---

## Table of Contents

1. [What is Classical ML?](#1-what-is-classical-ml)
2. [Scikit-Learn API Design Philosophy](#2-scikit-learn-api-design-philosophy)
3. [Data Preparation](#3-data-preparation)
4. [Supervised Learning Algorithms](#4-supervised-learning-algorithms)
5. [Unsupervised Learning Algorithms](#5-unsupervised-learning-algorithms)
6. [Model Evaluation](#6-model-evaluation)
7. [Hyperparameter Tuning](#7-hyperparameter-tuning)
8. [Feature Engineering](#8-feature-engineering)
9. [Building Full Pipelines](#9-building-full-pipelines)
10. [Model Persistence](#10-model-persistence)
11. [End-to-End Project: Housing Price Prediction](#11-end-to-end-project-housing-price-prediction)
12. [Quiz (10 Questions)](#12-quiz-10-questions)
13. [References & Further Learning](#13-references--further-learning)

---

## 1. What is Classical ML?

Classical Machine Learning refers to algorithms that learn patterns from **structured/tabular data** without deep neural networks. These methods remain the backbone of production ML systems because they are:

- **Interpretable** — decision trees, linear models explain their decisions
- **Fast to train** — seconds to minutes, not hours
- **Data-efficient** — work well with thousands of rows, not millions
- **Robust** — well-understood failure modes

```
ML Taxonomy (High-Level)
========================

              Machine Learning
             /                \
    Supervised            Unsupervised
    /        \            /          \
Regression  Classification  Clustering  Dimensionality
                                        Reduction
    |              |            |            |
LinearReg   LogisticReg    KMeans         PCA
RidgeLasso     SVM         DBSCAN         t-SNE
RandomForest  DecisionTree  Hierarchical   UMAP
GradBoost   RandomForest
```

---

## 2. Scikit-Learn API Design Philosophy

Scikit-learn's power comes from a **unified, consistent API** that makes every algorithm interchangeable. Understanding this design unlocks the full library.

### The Three Core Interfaces

```
+------------------+     fit(X, y)      +------------------+
|   ESTIMATOR      | -----------------> |   FITTED MODEL   |
| (any algorithm)  |                    | (learned params) |
+------------------+                    +------------------+
        |                                        |
        | fit_transform(X)              predict(X) / transform(X)
        v                                        v
+------------------+                    +------------------+
|   TRANSFORMER    |                    |   PREDICTIONS    |
| StandardScaler   |                    |   / TRANSFORMED  |
| PCA, OneHotEnc   |                    |   DATA           |
+------------------+                    +------------------+
```

**Every scikit-learn object follows these rules:**

| Method | Who implements it | Purpose |
|--------|-------------------|---------|
| `fit(X, y)` | All estimators | Learn from data |
| `predict(X)` | Regressors, Classifiers | Make predictions |
| `transform(X)` | Transformers | Transform data |
| `fit_transform(X, y)` | Transformers | Fit then transform (optimized) |
| `score(X, y)` | All estimators | Default metric |
| `get_params()` | All estimators | Introspect hyperparams |
| `set_params(**params)` | All estimators | Set hyperparams |

### Why This Matters

```python
# Because every estimator has the same interface, you can swap algorithms
# with ONE line change:

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC

# All three train and predict identically:
for model in [LogisticRegression(), RandomForestClassifier(), SVC()]:
    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)
    print(f"{model.__class__.__name__}: {score:.4f}")
```

### Design Principles (from the scikit-learn paper)

1. **Consistency** — all objects share a common interface
2. **Inspection** — hyperparameters are public attributes
3. **Non-proliferation of classes** — datasets are NumPy arrays, not custom objects
4. **Composition** — complex behavior built from simple primitives via Pipeline
5. **Sensible defaults** — working out-of-the-box with reasonable hyperparameters

---

## 3. Data Preparation

```python
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.datasets import load_iris, load_boston, make_classification

# ── Load a built-in dataset ──────────────────────────────────────────────────
iris = load_iris()
X, y = iris.data, iris.target  # X is (150, 4) numpy array

# ── Train / Test Split ────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,      # 20% held out for testing
    random_state=42,    # reproducibility
    stratify=y          # preserve class balance — ALWAYS use for classification
)

print(f"Train size: {X_train.shape}, Test size: {X_test.shape}")
# Train size: (120, 4), Test size: (30, 4)
```

**The Golden Rule:** The test set must NEVER influence any preprocessing decisions. Fit transformers on `X_train` only, then apply to both.

---

## 4. Supervised Learning Algorithms

### 4.1 Linear Regression

Best for continuous targets with linear relationships.

```python
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.datasets import make_regression
import matplotlib.pyplot as plt

X, y = make_regression(n_samples=200, n_features=1, noise=20, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Plain OLS
lr = LinearRegression()
lr.fit(X_train, y_train)

print(f"Coefficient: {lr.coef_[0]:.3f}")
print(f"Intercept:   {lr.intercept_:.3f}")
print(f"R² score:    {lr.score(X_test, y_test):.4f}")

# Regularized variants
ridge = Ridge(alpha=1.0)        # L2 — shrinks all coefficients
lasso = Lasso(alpha=0.1)        # L1 — can zero out coefficients (feature selection)
enet  = ElasticNet(alpha=0.1, l1_ratio=0.5)  # L1 + L2 mix

for name, model in [("Ridge", ridge), ("Lasso", lasso), ("ElasticNet", enet)]:
    model.fit(X_train, y_train)
    print(f"{name} R²: {model.score(X_test, y_test):.4f}")
```

**When to use what:**
- `LinearRegression` — no multicollinearity, all features matter
- `Ridge` — many small/medium effects, correlated features
- `Lasso` — high-dimensional data, want automatic feature selection
- `ElasticNet` — groups of correlated features (genetics, NLP)

---

### 4.2 Logistic Regression

Despite the name, this is a **classification** algorithm.

```python
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import load_breast_cancer

X, y = load_breast_cancer(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Logistic Regression outputs calibrated probabilities
lr = LogisticRegression(
    C=1.0,              # Inverse of regularization strength (higher C = less regularization)
    max_iter=1000,      # Increase if convergence warnings appear
    solver='lbfgs',     # Good default for small/medium datasets
    random_state=42
)
lr.fit(X_train, y_train)

print(f"Accuracy:    {lr.score(X_test, y_test):.4f}")
print(f"Probabilities (first 3):\n{lr.predict_proba(X_test[:3])}")
```

---

### 4.3 Support Vector Machines (SVM)

Finds the **maximum-margin hyperplane**. Powerful for high-dimensional data.

```python
from sklearn.svm import SVC, SVR
from sklearn.preprocessing import StandardScaler

# SVMs are sensitive to feature scale — always scale first!
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)

# Classification
svc = SVC(
    kernel='rbf',       # 'linear', 'poly', 'rbf', 'sigmoid'
    C=1.0,              # Regularization: high C = low bias, high variance
    gamma='scale',      # Kernel coefficient
    probability=True    # Enable predict_proba (slower training)
)
svc.fit(X_train_s, y_train)
print(f"SVC Accuracy: {svc.score(X_test_s, y_test):.4f}")

# The kernel trick — SVM in original space vs. kernel space:
#
#  Original space (linearly separable):    Kernel space (after RBF):
#
#  ● ● ○ ○ ○                              ●●●
#  ● ○ ○ ○                                    \  margin
#  ○ ○ ○ ●                                ○○○○  --------  ●●●
#                                               support
#                                               vectors
```

**Key insight:** The RBF kernel implicitly maps data to infinite dimensions where it becomes linearly separable.

---

### 4.4 Decision Trees

Interpretable, non-parametric, handle mixed data types.

```python
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

dt = DecisionTreeClassifier(
    max_depth=4,            # Limit depth to prevent overfitting
    min_samples_split=10,   # Minimum samples to split a node
    min_samples_leaf=5,     # Minimum samples in a leaf
    criterion='gini',       # 'gini' or 'entropy'
    random_state=42
)
dt.fit(X_train, y_train)

# Print tree as ASCII
print(export_text(dt, feature_names=list(iris.feature_names)))

# Visualize
fig, ax = plt.subplots(figsize=(20, 8))
plot_tree(dt, feature_names=iris.feature_names, class_names=iris.target_names,
          filled=True, rounded=True, ax=ax)
plt.savefig("decision_tree.png", dpi=150, bbox_inches='tight')

# Feature importances
for name, importance in zip(iris.feature_names, dt.feature_importances_):
    print(f"  {name:30s}: {importance:.4f}")
```

```
Decision Tree Structure (conceptual)
=====================================

                [petal length <= 2.45]
               /                      \
          YES /                        \ NO
             /                          \
        [Setosa]           [petal width <= 1.75]
          LEAF            /                    \
                     YES /                      \ NO
                        /                        \
              [Versicolor]              [petal length <= 4.85]
                  LEAF                /                      \
                               YES  /                        \ NO
                                   /                          \
                           [Versicolor]               [Virginica]
                               LEAF                      LEAF
```

---

### 4.5 Random Forest

Ensemble of decision trees — each tree trained on a bootstrap sample with a random subset of features.

```python
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

rf = RandomForestClassifier(
    n_estimators=100,       # Number of trees
    max_depth=None,         # Let trees grow fully (bagging handles variance)
    max_features='sqrt',    # Features per split: 'sqrt' for classification
    bootstrap=True,         # Sample with replacement
    oob_score=True,         # Out-of-bag evaluation (free validation set!)
    n_jobs=-1,              # Use all CPU cores
    random_state=42
)
rf.fit(X_train, y_train)

print(f"Test accuracy:     {rf.score(X_test, y_test):.4f}")
print(f"OOB accuracy:      {rf.oob_score_:.4f}")  # No data leakage!

# Feature importances (mean decrease in impurity)
feat_imp = pd.Series(rf.feature_importances_, index=iris.feature_names)
print(feat_imp.sort_values(ascending=False))
```

**Random Forest vs. Single Decision Tree:**

| Property | Decision Tree | Random Forest |
|----------|---------------|---------------|
| Variance | High | Low (ensemble averaging) |
| Bias | Low | Slightly higher |
| Interpretability | High | Low |
| Training speed | Fast | Moderate |
| Overfitting risk | High | Low |

---

### 4.6 Gradient Boosting

Builds trees **sequentially**, each correcting its predecessor's errors.

```python
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
# HistGradientBoosting is sklearn's fast implementation (similar to LightGBM)

# Sklearn GradientBoosting (slower, educational)
gb = GradientBoostingClassifier(
    n_estimators=100,
    learning_rate=0.1,   # Shrinkage — lower = more trees needed but better generalization
    max_depth=3,         # Shallow trees are typical for boosting
    subsample=0.8,       # Stochastic gradient boosting
    random_state=42
)
gb.fit(X_train, y_train)

# Fast histogram-based (use this in practice)
hgb = HistGradientBoostingClassifier(
    max_iter=100,
    learning_rate=0.1,
    max_depth=3,
    random_state=42
)
hgb.fit(X_train, y_train)
print(f"HistGradBoost accuracy: {hgb.score(X_test, y_test):.4f}")

# XGBoost (external library — install with: pip install xgboost)
try:
    from xgboost import XGBClassifier
    xgb = XGBClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=3,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42
    )
    xgb.fit(X_train, y_train)
    print(f"XGBoost accuracy: {xgb.score(X_test, y_test):.4f}")
except ImportError:
    print("Install xgboost: pip install xgboost")

# LightGBM (external library — install with: pip install lightgbm)
try:
    from lightgbm import LGBMClassifier
    lgbm = LGBMClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
    lgbm.fit(X_train, y_train)
    print(f"LightGBM accuracy: {lgbm.score(X_test, y_test):.4f}")
except ImportError:
    print("Install lightgbm: pip install lightgbm")
```

**Boosting vs. Bagging (conceptual):**

```
BAGGING (Random Forest)          BOOSTING (Gradient Boosting)
================================  ================================
  Sample 1 → Tree 1               Tree 1: fit on original data
  Sample 2 → Tree 2               Tree 2: fit on Tree 1 residuals
  Sample 3 → Tree 3               Tree 3: fit on Tree 2 residuals
       ↓                                  ↓
  Majority vote / Average         Sum of weighted predictions
  (parallel, reduces variance)    (sequential, reduces bias)
```

---

## 5. Unsupervised Learning Algorithms

### 5.1 K-Means Clustering

```python
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Determine optimal k with the elbow method
inertias = []
silhouettes = []
K_range = range(2, 11)

for k in K_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(X, labels))

# Fit final model
km = KMeans(n_clusters=3, random_state=42, n_init=10)
labels = km.fit_predict(X)

print(f"Cluster centers:\n{km.cluster_centers_}")
print(f"Silhouette score: {silhouette_score(X, labels):.4f}")
# Silhouette score: -1 (wrong clusters) to +1 (perfect clusters)
```

### 5.2 DBSCAN

Density-based clustering — finds arbitrarily shaped clusters, handles outliers.

```python
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

X_scaled = StandardScaler().fit_transform(X)

dbscan = DBSCAN(
    eps=0.5,            # Neighborhood radius
    min_samples=5       # Minimum points to form a core point
)
labels = dbscan.fit_predict(X_scaled)

n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise    = list(labels).count(-1)

print(f"Clusters found: {n_clusters}")
print(f"Noise points:   {n_noise}")
# label = -1 means the point is classified as noise (outlier)
```

**KMeans vs DBSCAN:**

| Property | KMeans | DBSCAN |
|----------|--------|--------|
| Cluster shape | Spherical only | Arbitrary |
| k required | Yes | No |
| Outlier handling | Forces into cluster | Labels as noise |
| Scales with data | Good (O(n)) | Moderate (O(n log n)) |
| Sensitivity | To initialization | To eps, min_samples |

### 5.3 Principal Component Analysis (PCA)

Dimensionality reduction by finding orthogonal axes of maximum variance.

```python
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# Always scale before PCA — PCA is sensitive to variance
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Determine how many components to keep
pca_full = PCA()
pca_full.fit(X_scaled)

cumvar = np.cumsum(pca_full.explained_variance_ratio_)
n_components_95 = np.argmax(cumvar >= 0.95) + 1
print(f"Components for 95% variance: {n_components_95}")

# Apply PCA
pca = PCA(n_components=2)  # or n_components=0.95 to keep 95% variance
X_pca = pca.fit_transform(X_scaled)

print(f"Original shape:  {X_scaled.shape}")
print(f"Reduced shape:   {X_pca.shape}")
print(f"Variance explained: {pca.explained_variance_ratio_.sum():.4f}")

# Scree plot
plt.figure(figsize=(8, 4))
plt.bar(range(1, len(pca_full.explained_variance_ratio_)+1),
        pca_full.explained_variance_ratio_, alpha=0.7, label='Individual')
plt.step(range(1, len(cumvar)+1), cumvar, where='mid', label='Cumulative')
plt.axhline(0.95, ls='--', color='red', label='95% threshold')
plt.xlabel('Principal Component')
plt.ylabel('Explained Variance Ratio')
plt.legend()
plt.title('Scree Plot')
plt.savefig('pca_scree.png', dpi=150)
```

---

## 6. Model Evaluation

### 6.1 Classification Metrics

```python
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    ConfusionMatrixDisplay, RocCurveDisplay
)

y_pred  = rf.predict(X_test)
y_proba = rf.predict_proba(X_test)

# Core metrics
print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
print(f"Precision: {precision_score(y_test, y_pred, average='weighted'):.4f}")
print(f"Recall:    {recall_score(y_test, y_pred, average='weighted'):.4f}")
print(f"F1:        {f1_score(y_test, y_pred, average='weighted'):.4f}")
print(f"ROC-AUC:   {roc_auc_score(y_test, y_proba, multi_class='ovr'):.4f}")

# Full classification report
print(classification_report(y_test, y_pred, target_names=iris.target_names))

# Confusion matrix
fig, ax = plt.subplots(figsize=(6, 5))
ConfusionMatrixDisplay.from_predictions(
    y_test, y_pred, display_labels=iris.target_names,
    cmap='Blues', ax=ax
)
plt.title('Confusion Matrix')
plt.savefig('confusion_matrix.png', dpi=150)
```

**Metric cheat sheet:**

```
Confusion Matrix (Binary):
                      Predicted
                   Positive  Negative
Actual  Positive |   TP    |   FN   |  ← Recall = TP / (TP + FN)
        Negative |   FP    |   TN   |

Precision = TP / (TP + FP)   — of all predicted positive, how many were right?
Recall    = TP / (TP + FN)   — of all actual positive, how many did we catch?
F1        = 2 × (P × R) / (P + R)  — harmonic mean

When to prioritize which:
  • High Recall  → medical diagnosis (don't miss sick patients)
  • High Precision → spam filter (don't delete real emails)
  • Balanced F1  → general purpose
```

### 6.2 Regression Metrics

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

y_pred = lr.predict(X_test)

mae  = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2   = r2_score(y_test, y_pred)

print(f"MAE:  {mae:.4f}")    # Mean Absolute Error — interpretable in target units
print(f"RMSE: {rmse:.4f}")   # Root Mean Squared Error — penalizes large errors more
print(f"R²:   {r2:.4f}")     # Coefficient of determination: 1.0 = perfect, 0 = mean baseline
```

### 6.3 Cross-Validation

```python
from sklearn.model_selection import (
    cross_val_score, StratifiedKFold, KFold,
    cross_validate
)

# Simple cross-validation
scores = cross_val_score(
    rf, X, y,
    cv=5,               # 5-fold CV
    scoring='accuracy', # or 'f1_weighted', 'roc_auc', 'r2', etc.
    n_jobs=-1
)
print(f"CV scores: {scores}")
print(f"Mean ± Std: {scores.mean():.4f} ± {scores.std():.4f}")

# Stratified K-Fold (preserves class balance in each fold)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(rf, X, y, cv=skf, scoring='f1_weighted')

# Multiple metrics at once
cv_results = cross_validate(
    rf, X, y, cv=5,
    scoring=['accuracy', 'f1_weighted', 'roc_auc_ovr'],
    return_train_score=True  # Check for overfitting
)
for metric, values in cv_results.items():
    if 'test' in metric:
        print(f"{metric}: {values.mean():.4f} ± {values.std():.4f}")
```

```
K-Fold Cross-Validation (K=5)
==============================

Fold 1: [TEST ][TRAIN][TRAIN][TRAIN][TRAIN]
Fold 2: [TRAIN][TEST ][TRAIN][TRAIN][TRAIN]
Fold 3: [TRAIN][TRAIN][TEST ][TRAIN][TRAIN]
Fold 4: [TRAIN][TRAIN][TRAIN][TEST ][TRAIN]
Fold 5: [TRAIN][TRAIN][TRAIN][TRAIN][TEST ]
         ↑ each fold uses a different subset for testing
         Final score = mean of 5 test scores
```

---

## 7. Hyperparameter Tuning

### 7.1 GridSearchCV

Exhaustive search over a parameter grid.

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [None, 5, 10],
    'min_samples_split': [2, 5, 10],
    'max_features': ['sqrt', 'log2']
}

grid_search = GridSearchCV(
    RandomForestClassifier(random_state=42),
    param_grid,
    cv=5,
    scoring='f1_weighted',
    n_jobs=-1,
    verbose=1,
    refit=True   # Refit best model on full training set
)
grid_search.fit(X_train, y_train)

print(f"Best params: {grid_search.best_params_}")
print(f"Best CV score: {grid_search.best_score_:.4f}")
print(f"Test score: {grid_search.score(X_test, y_test):.4f}")

# Access all results
results_df = pd.DataFrame(grid_search.cv_results_)
print(results_df[['params', 'mean_test_score', 'std_test_score']].sort_values(
    'mean_test_score', ascending=False).head(5))
```

**Warning:** Grid size explodes exponentially. `3 × 3 × 3 × 2 = 54 combinations × 5 folds = 270 fits`.

### 7.2 RandomizedSearchCV

Randomly samples from distributions — much faster, often finds equally good solutions.

```python
from sklearn.model_selection import RandomizedSearchCV
from scipy.stats import randint, uniform

param_distributions = {
    'n_estimators': randint(50, 500),
    'max_depth': [None] + list(range(3, 20)),
    'min_samples_split': randint(2, 20),
    'min_samples_leaf': randint(1, 10),
    'max_features': ['sqrt', 'log2', None]
}

random_search = RandomizedSearchCV(
    RandomForestClassifier(random_state=42),
    param_distributions,
    n_iter=50,       # Number of random combinations to try
    cv=5,
    scoring='f1_weighted',
    n_jobs=-1,
    random_state=42
)
random_search.fit(X_train, y_train)
print(f"Best params: {random_search.best_params_}")
print(f"Best CV score: {random_search.best_score_:.4f}")
```

### 7.3 Optuna (Bayesian Optimization)

State-of-the-art hyperparameter optimization with pruning.

```python
# pip install optuna
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

def objective(trial):
    """Define the search space and return a validation score."""
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 500),
        'max_depth': trial.suggest_int('max_depth', 2, 20),
        'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
        'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2']),
        'random_state': 42
    }
    model = RandomForestClassifier(**params)
    score = cross_val_score(model, X_train, y_train, cv=3, scoring='f1_weighted').mean()
    return score

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50, timeout=60)

print(f"Best trial value: {study.best_trial.value:.4f}")
print(f"Best params: {study.best_trial.params}")

# Optuna uses Tree-structured Parzen Estimators (TPE) by default:
# it builds a probabilistic model of which hyperparams lead to good results
# and samples from promising regions — far more efficient than random search.
```

---

## 8. Feature Engineering

### 8.1 Encoding Categorical Variables

```python
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, OrdinalEncoder
from sklearn.preprocessing import TargetEncoder  # sklearn >= 1.3

df = pd.DataFrame({
    'color': ['red', 'blue', 'green', 'red', 'blue'],
    'size': ['S', 'M', 'L', 'XL', 'M'],
    'quality': ['low', 'medium', 'high', 'medium', 'low'],
    'price': [10, 20, 30, 15, 18]
})

# One-Hot Encoding (nominal categories — no order)
ohe = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
color_encoded = ohe.fit_transform(df[['color']])
print(ohe.get_feature_names_out())
# ['color_blue', 'color_green', 'color_red']

# Ordinal Encoding (ordered categories)
oe = OrdinalEncoder(categories=[['low', 'medium', 'high']])
quality_encoded = oe.fit_transform(df[['quality']])
# low→0, medium→1, high→2

# Label Encoding (for target variable, not features)
le = LabelEncoder()
y_encoded = le.fit_transform(['cat', 'dog', 'cat', 'bird'])

# Target Encoding (encodes with mean of target — powerful but needs CV to avoid leakage)
te = TargetEncoder()
color_target_encoded = te.fit_transform(df[['color']], df['price'])
```

### 8.2 Scaling

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

X_sample = np.array([[1, 100], [2, 200], [3, 300], [100, 5]])  # note outlier

# StandardScaler: (x - mean) / std → zero mean, unit variance
# Use when: algorithm assumes Gaussian distribution (SVM, LogReg, PCA)
ss = StandardScaler()
print(ss.fit_transform(X_sample))

# MinMaxScaler: (x - min) / (max - min) → range [0, 1]
# Use when: neural networks, image pixels, bounded input required
mms = MinMaxScaler(feature_range=(0, 1))
print(mms.fit_transform(X_sample))

# RobustScaler: uses median and IQR — resistant to outliers
# Use when: data has significant outliers
rs = RobustScaler()
print(rs.fit_transform(X_sample))
```

```
Scaling Comparison:
===================
Original: [1, 2, 3, 100]
                                          ← outlier at 100

StandardScaler: [-0.97, -0.91, -0.85,  2.73]   # outlier distorts mean/std
MinMaxScaler:   [ 0.00,  0.01,  0.02,  1.00]   # outlier compresses others into 0-0.02
RobustScaler:   [-1.00, -0.50,  0.00, 97.00]   # median-based, robust to outlier
```

### 8.3 Feature Selection

```python
from sklearn.feature_selection import (
    SelectKBest, f_classif, mutual_info_classif,
    RFE, RFECV, SelectFromModel
)

# Filter method: statistical test
selector = SelectKBest(score_func=f_classif, k=2)
X_selected = selector.fit_transform(X_train, y_train)
print(f"Selected features: {selector.get_support()}")

# Wrapper method: Recursive Feature Elimination
rfe = RFE(RandomForestClassifier(n_estimators=50, random_state=42), n_features_to_select=2)
rfe.fit(X_train, y_train)
print(f"RFE ranking: {rfe.ranking_}")

# Embedded method: model-based selection (uses feature importance)
sfm = SelectFromModel(RandomForestClassifier(n_estimators=50, random_state=42),
                      threshold='mean')  # select features above mean importance
sfm.fit(X_train, y_train)
X_important = sfm.transform(X_test)
print(f"Features selected: {sfm.get_support()}")
```

---

## 9. Building Full Pipelines

Pipelines prevent data leakage and make deployment clean.

```python
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer

# Example: mixed dataset with numeric and categorical features
housing_data = pd.DataFrame({
    'sqft':        [1500, 2000, 1200, 3000, 1800],
    'bedrooms':    [3, 4, 2, 5, 3],
    'neighborhood':['A', 'B', 'A', 'C', 'B'],
    'condition':   ['good', 'fair', 'excellent', 'good', 'fair'],
    'price':       [300000, 400000, 250000, 600000, 350000]
})

X = housing_data.drop('price', axis=1)
y = housing_data['price']

# ── Define column groups ──────────────────────────────────────────────────────
numeric_features     = ['sqft', 'bedrooms']
categorical_features = ['neighborhood']
ordinal_features     = ['condition']

# ── Build sub-pipelines per column type ──────────────────────────────────────
numeric_transformer = Pipeline(steps=[
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

ordinal_transformer = Pipeline(steps=[
    ('ordinal', OrdinalEncoder(categories=[['fair', 'good', 'excellent']]))
])

# ── Combine with ColumnTransformer ────────────────────────────────────────────
preprocessor = ColumnTransformer(transformers=[
    ('num',  numeric_transformer,     numeric_features),
    ('cat',  categorical_transformer, categorical_features),
    ('ord',  ordinal_transformer,     ordinal_features)
])

# ── Full ML Pipeline ──────────────────────────────────────────────────────────
full_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('model',        RandomForestRegressor(n_estimators=100, random_state=42))
])

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

full_pipeline.fit(X_train, y_train)
y_pred = full_pipeline.predict(X_test)

print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.2f}")
print(f"R²:   {r2_score(y_test, y_pred):.4f}")

# Pipeline is also compatible with GridSearchCV!
param_grid = {
    'model__n_estimators': [50, 100, 200],
    'model__max_depth': [None, 5, 10],
    # Note the __ notation: step_name__param_name
}
grid = GridSearchCV(full_pipeline, param_grid, cv=3, scoring='r2', n_jobs=-1)
grid.fit(X_train, y_train)
print(f"Best CV R²: {grid.best_score_:.4f}")
```

```
Pipeline DAG
============

  Raw Data (mixed types)
         |
         v
  ColumnTransformer
  ┌──────────────────────────────────────────┐
  │  Numeric cols  →  StandardScaler         │
  │  Categorical   →  OneHotEncoder          │
  │  Ordinal       →  OrdinalEncoder         │
  └──────────────────────────────────────────┘
         |
         v
  Processed Feature Matrix (all numeric)
         |
         v
  RandomForestRegressor
         |
         v
  Predictions
```

---

## 10. Model Persistence

```python
import joblib
import pickle

# ── joblib (preferred for sklearn — handles large numpy arrays efficiently) ──
joblib.dump(full_pipeline, 'housing_model.joblib')
loaded_pipeline = joblib.load('housing_model.joblib')

# Verify identical predictions
y_pred_original = full_pipeline.predict(X_test)
y_pred_loaded   = loaded_pipeline.predict(X_test)
assert np.allclose(y_pred_original, y_pred_loaded), "Model mismatch!"
print("Model loaded and verified successfully.")

# ── pickle (built-in, simpler) ────────────────────────────────────────────────
with open('housing_model.pkl', 'wb') as f:
    pickle.dump(full_pipeline, f)

with open('housing_model.pkl', 'rb') as f:
    loaded_pickle = pickle.load(f)

# ── Production pattern ────────────────────────────────────────────────────────
import json, datetime

# Save model with metadata
metadata = {
    'model_class': full_pipeline.__class__.__name__,
    'sklearn_version': '1.4.0',
    'trained_at': datetime.datetime.utcnow().isoformat(),
    'features': list(X.columns),
    'target': 'price',
    'test_r2': float(r2_score(y_test, full_pipeline.predict(X_test)))
}
with open('model_metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)

# IMPORTANT: Never load a pickle from an untrusted source — it executes code!
# For production, consider ONNX, PMML, or MLflow for safer serialization.
```

---

## 11. End-to-End Project: Housing Price Prediction

We'll build a complete ML system to predict housing prices using the Ames Housing dataset (a richer alternative to the deprecated Boston dataset).

```python
# ─────────────────────────────────────────────────────────────────────────────
# STEP 0: Setup
# ─────────────────────────────────────────────────────────────────────────────
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV
from scipy.stats import randint, uniform
import joblib, warnings
warnings.filterwarnings('ignore')

# Use sklearn's California Housing as a clean alternative
from sklearn.datasets import fetch_california_housing

housing = fetch_california_housing(as_frame=True)
df = housing.frame
print(df.shape)         # (20640, 9)
print(df.dtypes)
print(df.describe())

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Exploratory Data Analysis
# ─────────────────────────────────────────────────────────────────────────────
target = 'MedHouseVal'  # Median house value in $100k

# Distribution of target
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
df[target].hist(bins=50, ax=axes[0])
axes[0].set_title('House Value Distribution (raw)')
np.log1p(df[target]).hist(bins=50, ax=axes[1])
axes[1].set_title('House Value Distribution (log-transformed)')
plt.savefig('eda_target.png', dpi=150)

# Correlation heatmap
fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(df.corr(), annot=True, fmt='.2f', cmap='coolwarm', ax=ax)
plt.title('Feature Correlation Matrix')
plt.savefig('eda_correlation.png', dpi=150)

print("Features most correlated with target:")
print(df.corr()[target].sort_values(ascending=False))

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Feature Engineering
# ─────────────────────────────────────────────────────────────────────────────
df_eng = df.copy()

# Create meaningful ratio features
df_eng['RoomsPerHousehold']   = df_eng['AveRooms']   / df_eng['AveOccup']
df_eng['BedroomsPerRoom']     = df_eng['AveBedrms']  / df_eng['AveRooms']
df_eng['PopulationPerHouse']  = df_eng['Population'] / df_eng['HouseAge']

# Cap outliers at 99th percentile
for col in ['AveRooms', 'AveBedrms', 'Population']:
    upper = df_eng[col].quantile(0.99)
    df_eng[col] = df_eng[col].clip(upper=upper)

# Log-transform skewed features
for col in ['Population', 'AveOccup']:
    df_eng[f'log_{col}'] = np.log1p(df_eng[col])

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Split Data
# ─────────────────────────────────────────────────────────────────────────────
X = df_eng.drop(columns=[target])
y = np.log1p(df_eng[target])  # Log-transform target for better model performance

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"Train: {X_train.shape}, Test: {X_test.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Build Pipeline
# ─────────────────────────────────────────────────────────────────────────────
numeric_features = X.columns.tolist()  # all numeric in this dataset

numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),  # handle any NaNs
    ('scaler',  StandardScaler())
])

preprocessor = ColumnTransformer(transformers=[
    ('num', numeric_transformer, numeric_features)
])

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Baseline Model
# ─────────────────────────────────────────────────────────────────────────────
baseline_pipeline = Pipeline([
    ('prep',  preprocessor),
    ('model', Ridge(alpha=1.0))
])

baseline_pipeline.fit(X_train, y_train)
y_pred_base = baseline_pipeline.predict(X_test)

# Convert back from log space for interpretable metrics
y_test_orig = np.expm1(y_test)
y_pred_base_orig = np.expm1(y_pred_base)

print("\n=== Baseline (Ridge) ===")
print(f"MAE:  ${mean_absolute_error(y_test_orig, y_pred_base_orig) * 100_000:,.0f}")
print(f"RMSE: ${np.sqrt(mean_squared_error(y_test_orig, y_pred_base_orig)) * 100_000:,.0f}")
print(f"R²:   {r2_score(y_test_orig, y_pred_base_orig):.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: Advanced Model
# ─────────────────────────────────────────────────────────────────────────────
rf_pipeline = Pipeline([
    ('prep',  preprocessor),
    ('model', RandomForestRegressor(
        n_estimators=200,
        max_depth=None,
        min_samples_leaf=3,
        n_jobs=-1,
        random_state=42
    ))
])

rf_pipeline.fit(X_train, y_train)
y_pred_rf = rf_pipeline.predict(X_test)
y_pred_rf_orig = np.expm1(y_pred_rf)

print("\n=== Random Forest ===")
print(f"MAE:  ${mean_absolute_error(y_test_orig, y_pred_rf_orig) * 100_000:,.0f}")
print(f"RMSE: ${np.sqrt(mean_squared_error(y_test_orig, y_pred_rf_orig)) * 100_000:,.0f}")
print(f"R²:   {r2_score(y_test_orig, y_pred_rf_orig):.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7: Hyperparameter Tuning
# ─────────────────────────────────────────────────────────────────────────────
param_dist = {
    'model__n_estimators': randint(100, 500),
    'model__max_depth': [None, 5, 10, 15, 20],
    'model__min_samples_leaf': randint(1, 10),
    'model__max_features': ['sqrt', 0.5, 0.7]
}

rs = RandomizedSearchCV(
    rf_pipeline, param_dist,
    n_iter=30, cv=5,
    scoring='neg_root_mean_squared_error',
    n_jobs=-1, random_state=42, verbose=1
)
rs.fit(X_train, y_train)

print(f"\nBest params: {rs.best_params_}")
y_pred_tuned = rs.predict(X_test)
y_pred_tuned_orig = np.expm1(y_pred_tuned)

print("\n=== Tuned Random Forest ===")
print(f"MAE:  ${mean_absolute_error(y_test_orig, y_pred_tuned_orig) * 100_000:,.0f}")
print(f"RMSE: ${np.sqrt(mean_squared_error(y_test_orig, y_pred_tuned_orig)) * 100_000:,.0f}")
print(f"R²:   {r2_score(y_test_orig, y_pred_tuned_orig):.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8: Model Analysis
# ─────────────────────────────────────────────────────────────────────────────
# Feature importances
best_rf = rs.best_estimator_['model']
feat_imp = pd.Series(
    best_rf.feature_importances_,
    index=numeric_features
).sort_values(ascending=False)

print("\nTop 10 Feature Importances:")
print(feat_imp.head(10))

# Residual analysis
residuals = y_test_orig - y_pred_tuned_orig
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].scatter(y_pred_tuned_orig, residuals, alpha=0.3, s=5)
axes[0].axhline(0, color='red', ls='--')
axes[0].set_xlabel('Predicted Price ($100k)')
axes[0].set_ylabel('Residuals')
axes[0].set_title('Residual Plot')

axes[1].hist(residuals, bins=50)
axes[1].set_title('Residual Distribution')
plt.tight_layout()
plt.savefig('residual_analysis.png', dpi=150)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 9: Model Comparison
# ─────────────────────────────────────────────────────────────────────────────
models = {
    'Ridge': Pipeline([('prep', preprocessor), ('model', Ridge(alpha=10.0))]),
    'Lasso': Pipeline([('prep', preprocessor), ('model', Lasso(alpha=0.01))]),
    'RandomForest': rf_pipeline,
    'GradientBoosting': Pipeline([
        ('prep', preprocessor),
        ('model', GradientBoostingRegressor(n_estimators=200, learning_rate=0.05,
                                             max_depth=4, random_state=42))
    ])
}

results = {}
kf = KFold(n_splits=5, shuffle=True, random_state=42)

for name, pipeline in models.items():
    scores = cross_val_score(
        pipeline, X_train, y_train,
        cv=kf, scoring='neg_root_mean_squared_error',
        n_jobs=-1
    )
    results[name] = -scores  # negate to get positive RMSE

results_df = pd.DataFrame(results)
print("\n=== Model Comparison (5-fold CV RMSE, log-scale) ===")
print(results_df.describe().loc[['mean', 'std']])

# ─────────────────────────────────────────────────────────────────────────────
# STEP 10: Save Final Model
# ─────────────────────────────────────────────────────────────────────────────
final_model = rs.best_estimator_
final_model.fit(X_train, y_train)  # retrain on full training set

joblib.dump(final_model, 'california_housing_model.joblib')
print("\nFinal model saved to california_housing_model.joblib")

# Quick inference example
sample = X_test.iloc[:3]
predictions_log = final_model.predict(sample)
predictions_usd = np.expm1(predictions_log) * 100_000
actual_usd      = np.expm1(y_test.iloc[:3].values) * 100_000

print("\nSample predictions:")
for pred, actual in zip(predictions_usd, actual_usd):
    print(f"  Predicted: ${pred:>10,.0f}  |  Actual: ${actual:>10,.0f}")
```

**Expected output:**

```
=== Baseline (Ridge) ===
MAE:   $47,231
RMSE:  $72,105
R²:    0.7812

=== Random Forest ===
MAE:   $31,420
RMSE:  $51,840
R²:    0.8764

=== Tuned Random Forest ===
MAE:   $29,871
RMSE:  $49,203
R²:    0.8891
```

---

## 12. Quiz (10 Questions)

Test your understanding of this module.

---

**Q1.** What does `fit_transform()` do differently from calling `fit()` then `transform()` separately, and when should you use each?

<details>
<summary>Answer</summary>

`fit_transform()` learns the transformation parameters AND applies them in one step. It is functionally equivalent to `fit(X).transform(X)` but may be more computationally efficient (e.g., PCA avoids computing the decomposition twice).

**When to use:**
- `fit_transform()` — **only on training data**
- `transform()` — on test/validation/production data, after fitting on train

Never call `fit_transform()` on test data — this leaks test statistics into your preprocessing.

</details>

---

**Q2.** You train a StandardScaler on training data and notice the test accuracy is much lower than training accuracy. What are three possible causes?

<details>
<summary>Answer</summary>

1. **Overfitting** — model memorized training data, does not generalize. Fix: increase regularization, reduce model complexity, get more data.
2. **Data leakage** — preprocessing (e.g., imputation, scaling) was fit on the combined train+test data. Fix: always fit transformers on training data only, use a Pipeline.
3. **Distribution shift** — training and test data come from different distributions (different time periods, different sources). Fix: investigate data collection, use robust preprocessing.

</details>

---

**Q3.** When would you choose DBSCAN over K-Means?

<details>
<summary>Answer</summary>

Choose DBSCAN when:
- Clusters have **non-spherical shapes** (rings, crescents, arbitrary shapes)
- You need to detect **outliers/noise** (DBSCAN marks them as -1)
- You **don't know** the number of clusters in advance
- Clusters have **varying density** levels (though HDBSCAN handles this better)

Choose K-Means when:
- Clusters are roughly **spherical and similar size**
- You know k or can estimate it with the elbow method
- **Speed** matters — K-Means is O(n) while DBSCAN is O(n log n)

</details>

---

**Q4.** What is the purpose of `stratify=y` in `train_test_split()`?

<details>
<summary>Answer</summary>

`stratify=y` ensures the class distribution in both train and test splits **mirrors the distribution in the full dataset**. Without it, random splitting can accidentally put most examples of a rare class into either train or test.

Example: If your dataset has 95% class 0 and 5% class 1, stratified split preserves this 95/5 ratio in both train and test. Without stratification, your test set might have 0 examples of class 1 purely by chance.

</details>

---

**Q5.** Explain the bias-variance tradeoff in terms of Random Forest hyperparameters.

<details>
<summary>Answer</summary>

- **High variance (overfitting)**: Deep trees, many features per split, small leaf size → trees memorize training data. Fix: reduce `max_depth`, increase `min_samples_leaf`, reduce `max_features`.
- **High bias (underfitting)**: Shallow trees, very few features per split, large leaf size → trees too simple to capture patterns. Fix: increase `max_depth`, increase `n_estimators`.

The Random Forest ensemble naturally reduces variance (via averaging) more than bias, which is why individual trees are often grown fully (`max_depth=None`) to keep bias low, relying on the ensemble to tame variance.

</details>

---

**Q6.** What is a Pipeline in scikit-learn, and what problem does it solve?

<details>
<summary>Answer</summary>

A `Pipeline` chains multiple transformers and a final estimator into a single object with the standard `fit`/`predict`/`score` interface.

**Problems it solves:**
1. **Data leakage prevention** — during cross-validation, each fold fits transformers only on that fold's training data, not the validation fold
2. **Deployment simplicity** — the entire preprocessing + model is one serializable object
3. **Code organization** — avoids repetitive `fit_transform`/`transform` calls
4. **Hyperparameter search** — `GridSearchCV` can tune both preprocessing and model parameters together using `step__param` notation

</details>

---

**Q7.** Why is ROC-AUC preferred over accuracy for imbalanced datasets?

<details>
<summary>Answer</summary>

With 99% class 0 and 1% class 1, a model that predicts class 0 for everything achieves 99% accuracy but is completely useless.

ROC-AUC measures the model's ability to **rank** positive instances above negative ones, independent of the decision threshold. It ranges from 0.5 (random) to 1.0 (perfect). A model that predicts all class 0 would have AUC = 0.5 (no better than random).

For severely imbalanced data, also consider **Precision-Recall AUC**, which is even more sensitive to minority class performance.

</details>

---

**Q8.** What is the difference between `GridSearchCV` and `RandomizedSearchCV`? When does Randomized outperform Grid?

<details>
<summary>Answer</summary>

| | GridSearchCV | RandomizedSearchCV |
|---|---|---|
| Search strategy | All combinations | Random samples |
| Budget control | Fixed (grid size × folds) | `n_iter` controls it |
| Continuous params | Only discrete values | Supports distributions |

Randomized outperforms Grid when:
- The parameter space is **large** (3+ parameters with many values each)
- Some parameters have **little effect** — random search wastes fewer evaluations on irrelevant dimensions
- **Continuous hyperparameters** — you can sample from `uniform(0.01, 1.0)` instead of picking 3-4 discrete values
- **Budget is limited** — 50 random samples can cover more of the space than 50 grid points

</details>

---

**Q9.** What is a feature importance score in a Random Forest, and what are its limitations?

<details>
<summary>Answer</summary>

Feature importance in Random Forest is **Mean Decrease in Impurity (MDI)**: how much each feature reduces Gini impurity / variance on average across all trees.

**Limitations:**
1. **Biased toward high-cardinality features** — numerical features and features with many categories appear more important even if they aren't
2. **Correlated features** — importance is split among correlated features, making each look less important than it is
3. **Tells you what the model uses, not causal importance** — a spurious correlation can appear important

Better alternatives:
- **Permutation importance** (`sklearn.inspection.permutation_importance`) — shuffles feature values and measures performance drop
- **SHAP values** — game-theory based, additive, handles correlation better

</details>

---

**Q10.** You serialize a model with `joblib.dump()` and load it 6 months later on a newer scikit-learn version. The predictions are different. Why, and how do you prevent this?

<details>
<summary>Answer</summary>

Scikit-learn does not guarantee backward compatibility of serialized models across versions. Internal implementations (random number generation, numerical algorithms) can change between versions, altering predictions even for the same hyperparameters.

**Prevention strategies:**
1. **Pin the scikit-learn version** in `requirements.txt` / `pyproject.toml` and use the same version for both training and inference
2. **Save version metadata** alongside the model file (as shown in the persistence section)
3. **Use ONNX** for cross-version, cross-framework serialization: `sklearn-onnx` converts models to the ONNX format which is version-independent
4. **MLflow Model Registry** — tags models with their environment and auto-logs dependencies

</details>

---

## 13. References & Further Learning

### Free Resources

| Resource | Type | Why It's Great |
|----------|------|----------------|
| [Scikit-learn Documentation](https://scikit-learn.org/stable/user_guide.html) | Official docs | Best ML library docs online — every algorithm has theory, code examples, and practical advice. Start here. |
| [fast.ai Practical ML](https://course.fast.ai/) | Video course (free) | Pragmatic, top-down approach. Covers tabular data, ensembles, and deep learning. Very hands-on. |
| [Kaggle Learn — Intro to ML](https://www.kaggle.com/learn/intro-to-machine-learning) | Interactive lessons | Free, browser-based, with real competitions to apply skills immediately. |
| [StatQuest with Josh Starmer](https://www.youtube.com/@statquest) | YouTube channel | Outstanding visual explanations of every algorithm — PCA, random forests, gradient boosting. |
| [The Elements of Statistical Learning](https://hastie.su.domains/ElemStatLearn/) | Textbook (free PDF) | Rigorous mathematical treatment of all classical ML algorithms. |

### Paid Resources

| Resource | Type | Why It's Worth It |
|----------|------|-------------------|
| **Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow** — Aurélien Géron (O'Reilly) | Book | The definitive practical guide. Covers everything in this module in far greater depth, plus deep learning. Excellent code quality. |
| **Machine Learning A-Z: AI, Python & R** — Kirill Eremenko & Hadelin de Ponteves (Udemy) | Video course | Comprehensive A-to-Z coverage with intuitive explanations. Regularly on sale for <$20. |
| **Applied Machine Learning in Python** (Coursera, University of Michigan) | Online course | Academic rigor with practical assignments using scikit-learn. |

### Key Papers

- Pedregosa et al. (2011) — [Scikit-learn: Machine Learning in Python](https://jmlr.org/papers/v12/pedregosa11a.html) — the original scikit-learn paper explaining design philosophy
- Breiman (2001) — [Random Forests](https://link.springer.com/article/10.1023/A:1010933404324) — original Random Forest paper
- Chen & Guestrin (2016) — [XGBoost: A Scalable Tree Boosting System](https://arxiv.org/abs/1603.02754)

---

### What's Next

```
Learning Path
=============

  [Module 01] NumPy
       ↓
  [Module 02] Pandas
       ↓
  [Module 03] Matplotlib / Seaborn
       ↓
  [Module 04] Scikit-Learn ← YOU ARE HERE
       ↓
  [Module 05] Deep Learning with PyTorch
       ↓
  [Module 06] Natural Language Processing (Transformers, HuggingFace)
       ↓
  [Module 07] MLOps & Production (MLflow, Docker, FastAPI)
```

---

*Module 04 — Scikit-Learn & Classical ML | AI/Python Learning Path*
*Last updated: June 2026*
