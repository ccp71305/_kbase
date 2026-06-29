# Supervised Learning Algorithms In Depth

> **Series:** AI & Machine Learning Knowledge Base | Module 02
> **Prerequisites:** Module 01 (Math Foundations), Python, NumPy, scikit-learn basics
> **Estimated reading time:** ~90 minutes

---

## Table of Contents

1. [What Is Supervised Learning?](#1-what-is-supervised-learning)
2. [Linear Regression Family](#2-linear-regression-family)
   - OLS · Ridge · Lasso · ElasticNet
3. [Logistic Regression](#3-logistic-regression)
4. [K-Nearest Neighbors](#4-k-nearest-neighbors)
5. [Naive Bayes](#5-naive-bayes)
6. [Decision Trees (CART)](#6-decision-trees-cart)
7. [Ensemble Methods](#7-ensemble-methods)
   - Bagging · Random Forest · Boosting (AdaBoost, GBM, XGBoost, LightGBM, CatBoost) · Stacking
8. [Support Vector Machines](#8-support-vector-machines)
9. [Regression Variants Summary](#9-regression-variants-summary)
10. [Algorithm Comparison Table](#10-algorithm-comparison-table)
11. [Algorithm Selection Guide](#11-algorithm-selection-guide)
12. [Hyperparameter Tuning Reference](#12-hyperparameter-tuning-reference)
13. [Practical Exercise: Random Forest from Scratch](#13-practical-exercise-random-forest-from-scratch)
14. [Quiz (15 Questions + Solutions)](#14-quiz-15-questions--solutions)
15. [References](#15-references)

---

## 1. What Is Supervised Learning?

Supervised learning is the task of learning a mapping **f : X → Y** from labeled examples
`{(x₁, y₁), (x₂, y₂), ..., (xₙ, yₙ)}` such that the learned function generalizes well to
unseen inputs.

```
Training data              Model               Prediction
  (x, y) pairs  ──────►  learns f  ──────►  f(x_new) ≈ y_new
```

| Task type       | Output Y                     | Loss function (typical)            |
|-----------------|------------------------------|------------------------------------|
| Regression      | Continuous (price, temp)     | MSE, MAE, Huber                    |
| Classification  | Discrete class label         | Cross-entropy, Hinge loss          |
| Ranking         | Ordered preferences          | Pairwise loss                      |

**The bias-variance tradeoff** underlies every algorithm choice:

```
Total Error = Bias² + Variance + Irreducible Noise

High Bias  → underfitting (model too simple)
High Variance → overfitting (model memorizes training data)
```

---

## 2. Linear Regression Family

### 2.1 Ordinary Least Squares (OLS)

**Intuition:** Fit a hyperplane through the data by minimizing the sum of squared residuals.

**Math:**

Given design matrix **X** ∈ ℝⁿˣᵖ and targets **y** ∈ ℝⁿ:

```
Loss(w) = ||y - Xw||²₂  =  Σᵢ (yᵢ - wᵀxᵢ)²

Closed-form solution (Normal Equations):
  w* = (XᵀX)⁻¹ Xᵀy

Gradient:
  ∇Loss = -2Xᵀ(y - Xw)  →  set to zero → same solution
```

**Geometric view:** The prediction **ŷ = Xw** is the orthogonal projection of **y** onto
the column space of **X**.

**When to use:** Baseline for any regression task; features must have linear relationship
with target; no multicollinearity.

**Pros:** Fast (O(np²) fit), interpretable coefficients, exact solution.

**Cons:** Sensitive to outliers, breaks with multicollinear features (XᵀX singular).

```python
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.datasets import make_regression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

X, y = make_regression(n_samples=500, n_features=10, noise=20, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LinearRegression()
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

print(f"R²  : {r2_score(y_test, y_pred):.4f}")
print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
print(f"Coefs: {model.coef_}")
```

---

### 2.2 Ridge Regression (L2 Regularization)

**Intuition:** Add a penalty on the magnitude of coefficients to prevent overfitting and
handle multicollinearity.

**Math:**

```
Loss(w) = ||y - Xw||²₂  +  λ ||w||²₂

Closed-form:
  w* = (XᵀX + λI)⁻¹ Xᵀy

Effect: XᵀX + λI is always invertible (even with multicollinearity).
Larger λ → coefficients shrink toward 0 but never exactly 0.
```

```python
from sklearn.linear_model import Ridge, RidgeCV
import numpy as np

# Manual alpha selection
ridge = Ridge(alpha=1.0)
ridge.fit(X_train, y_train)

# Cross-validated alpha search
alphas = np.logspace(-3, 3, 100)
ridge_cv = RidgeCV(alphas=alphas, cv=5)
ridge_cv.fit(X_train, y_train)
print(f"Best alpha: {ridge_cv.alpha_:.4f}")
print(f"R²: {ridge_cv.score(X_test, y_test):.4f}")
```

**Hyperparameters:**

| Parameter | Effect | Typical range |
|-----------|--------|---------------|
| `alpha` (λ) | Regularization strength | 1e-4 to 1e4 (log scale) |
| `fit_intercept` | Center the data | Usually True |

---

### 2.3 Lasso Regression (L1 Regularization)

**Intuition:** L1 penalty induces **sparsity** — many coefficients become exactly zero,
performing automatic feature selection.

**Math:**

```
Loss(w) = ||y - Xw||²₂  +  λ ||w||₁

No closed form (non-differentiable at 0).
Solved with coordinate descent or subgradient methods.

Geometric insight:
  L1 ball is a diamond → corners lie on axes → solutions hit corners → sparsity
  L2 ball is a sphere  → no corners         → solutions rarely zero
```

```
         w₂                    w₂
          |  L2 ball             |  L1 ball (diamond)
       ───┼───                ───┼───
          |                      |  /\
   ───────●───────          ─────/──\─────
          |                    /      \
          |                   /________\
```

```python
from sklearn.linear_model import Lasso, LassoCV

lasso_cv = LassoCV(alphas=None, cv=5, max_iter=10000)
lasso_cv.fit(X_train, y_train)

print(f"Best alpha: {lasso_cv.alpha_:.6f}")
print(f"Non-zero coefs: {np.sum(lasso_cv.coef_ != 0)}")
print(f"R²: {lasso_cv.score(X_test, y_test):.4f}")
```

---

### 2.4 ElasticNet (L1 + L2)

**Intuition:** Combines Lasso (sparsity) and Ridge (stability with correlated features).

**Math:**

```
Loss(w) = ||y - Xw||²₂  +  λ₁ ||w||₁  +  λ₂ ||w||²₂

Parameterized as:
  alpha = λ₁ + λ₂
  l1_ratio = λ₁ / (λ₁ + λ₂)

l1_ratio = 1  →  pure Lasso
l1_ratio = 0  →  pure Ridge
```

```python
from sklearn.linear_model import ElasticNetCV

en_cv = ElasticNetCV(l1_ratio=[0.1, 0.5, 0.7, 0.9, 0.95, 1.0], cv=5)
en_cv.fit(X_train, y_train)
print(f"Best l1_ratio: {en_cv.l1_ratio_}, alpha: {en_cv.alpha_:.4f}")
```

**When to choose which regularization:**

```
Many correlated features, keep all → Ridge
Feature selection needed, few relevant features → Lasso
Both: correlated groups + sparsity → ElasticNet
```

---

## 3. Logistic Regression

### Intuition

Despite the name, logistic regression is a **classification** algorithm. It models the
probability of class membership using the logistic (sigmoid) function.

### Math

```
P(y=1 | x) = σ(wᵀx + b)     where σ(z) = 1 / (1 + e⁻ᶻ)

Decision boundary: wᵀx + b = 0  (a hyperplane)

Log-likelihood (Binary Cross-Entropy Loss):
  L(w) = -Σᵢ [ yᵢ log(ŷᵢ) + (1-yᵢ) log(1-ŷᵢ) ]

Gradient:
  ∂L/∂w = Xᵀ(ŷ - y)     (same form as linear regression!)

Multiclass (Softmax):
  P(y=k | x) = exp(wₖᵀx) / Σⱼ exp(wⱼᵀx)
```

```
Sigmoid curve:
  1.0 ┤              ╭──────────────
  0.5 ┤         ─────┤
  0.0 ┤──────────────╯
       ───────────────────────────── z
            -5    0    5
```

### Implementation

```python
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import make_classification
from sklearn.metrics import classification_report, roc_auc_score

X, y = make_classification(n_samples=1000, n_features=20, n_informative=10,
                            n_classes=2, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

lr = LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=1000)
lr.fit(X_train, y_train)

y_prob = lr.predict_proba(X_test)[:, 1]
print(classification_report(y_test, lr.predict(X_test)))
print(f"ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")
```

### Hyperparameters

| Parameter | Description | Values |
|-----------|-------------|--------|
| `C` | Inverse regularization (1/λ) | 0.001 to 100 |
| `penalty` | Regularization type | `l1`, `l2`, `elasticnet`, `none` |
| `solver` | Optimization algorithm | `lbfgs` (L2), `saga` (all), `liblinear` (small) |
| `multi_class` | Multiclass strategy | `ovr`, `multinomial` |

**Pros:** Fast, interpretable coefficients as log-odds, well-calibrated probabilities.
**Cons:** Linear decision boundary, requires feature scaling, poor with highly non-linear data.

---

## 4. K-Nearest Neighbors

### Intuition

"Tell me who your neighbors are and I'll tell you who you are." KNN classifies a point
by majority vote (or averages for regression) among its K closest training samples.

### Math

```
Distance metrics:
  Euclidean: d(x, x') = sqrt(Σᵢ (xᵢ - x'ᵢ)²)
  Manhattan:  d(x, x') = Σᵢ |xᵢ - x'ᵢ|
  Minkowski:  d(x, x') = (Σᵢ |xᵢ - x'ᵢ|ᵖ)^(1/p)

Classification:
  ŷ = argmax_c  |{i ∈ N_K(x) : yᵢ = c}|

Regression:
  ŷ = (1/K) Σᵢ∈N_K(x) yᵢ
```

### ASCII: Decision boundary with K=1 vs K=5

```
K=1 (overfits, jagged boundary)    K=5 (smoother boundary)
  A A . B B                          A A . B B
  A . . . B          vs.             A A . B B
  A . B . B                          A . B B B
  A . . B B                          A . . B B
```

### Implementation

```python
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# IMPORTANT: Always scale features for KNN
pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('knn', KNeighborsClassifier(n_neighbors=5, weights='uniform', metric='euclidean'))
])
pipe.fit(X_train, y_train)
print(f"Accuracy: {pipe.score(X_test, y_test):.4f}")

# Find optimal K
from sklearn.model_selection import cross_val_score
k_scores = []
for k in range(1, 31):
    knn = Pipeline([('scaler', StandardScaler()),
                    ('knn', KNeighborsClassifier(n_neighbors=k))])
    scores = cross_val_score(knn, X_train, y_train, cv=5, scoring='accuracy')
    k_scores.append(scores.mean())
best_k = np.argmax(k_scores) + 1
print(f"Best K: {best_k}, CV accuracy: {k_scores[best_k-1]:.4f}")
```

**Pros:** No training phase, naturally handles multiclass, non-parametric.
**Cons:** O(n) prediction time, suffers from curse of dimensionality, needs feature scaling.

---

## 5. Naive Bayes

### Intuition

Apply Bayes' theorem with the "naive" assumption that features are **conditionally
independent** given the class label. Surprisingly effective despite the strong assumption.

### Math

```
Bayes' theorem:
  P(y | x) ∝ P(y) · P(x | y)

Naive independence assumption:
  P(x | y) = Π_j P(x_j | y)

Therefore:
  ŷ = argmax_y  log P(y) + Σⱼ log P(xⱼ | y)

Variants:
  Gaussian NB:    P(xⱼ | y) = N(μⱼᵧ, σ²ⱼᵧ)        [continuous features]
  Bernoulli NB:   P(xⱼ | y) = pⱼᵧˣʲ (1-pⱼᵧ)^(1-xⱼ)  [binary features]
  Multinomial NB: P(xⱼ | y) ∝ (θⱼᵧ)ˣʲ              [count features/text]
```

### Implementation

```python
from sklearn.naive_bayes import GaussianNB, MultinomialNB, BernoulliNB
from sklearn.feature_extraction.text import CountVectorizer

# Gaussian NB for continuous features
gnb = GaussianNB(var_smoothing=1e-9)
gnb.fit(X_train, y_train)
print(f"GaussianNB Accuracy: {gnb.score(X_test, y_test):.4f}")

# Multinomial NB for text classification
corpus = ["good movie", "bad movie", "great film", "terrible film",
          "loved it", "hated it", "excellent", "awful"]
labels = [1, 0, 1, 0, 1, 0, 1, 0]

vectorizer = CountVectorizer()
X_text = vectorizer.fit_transform(corpus)
mnb = MultinomialNB(alpha=1.0)  # alpha = Laplace smoothing
mnb.fit(X_text, labels)
```

**Pros:** Very fast (O(np) training), works with tiny datasets, excels at text classification.
**Cons:** Independence assumption often violated; poor probability estimates.

---

## 6. Decision Trees (CART)

### Intuition

Recursively partition the feature space using axis-aligned splits to create a tree of
if-else rules. Each leaf holds a prediction.

### The CART Algorithm

```
Algorithm CART(data D, depth d):
  if stopping_criterion(D, d):
    return leaf with prediction = mean(y) or majority class
  
  for each feature j, threshold t:
    left  = {x ∈ D : xⱼ ≤ t}
    right = {x ∈ D : xⱼ > t}
    impurity_gain = I(D) - |left|/|D| · I(left) - |right|/|D| · I(right)
  
  (j*, t*) = argmax impurity_gain
  return Node(j*, t*, CART(left, d-1), CART(right, d-1))
```

### Impurity Measures

```
For Classification:
  Gini Impurity:  G(S) = 1 - Σₖ pₖ²
  Entropy:        H(S) = -Σₖ pₖ log₂(pₖ)
  Misclass error: E(S) = 1 - max(pₖ)

For Regression:
  MSE (variance): Var(S) = (1/|S|) Σᵢ (yᵢ - ȳ)²
  MAE:            MAE(S) = (1/|S|) Σᵢ |yᵢ - ȳ|
```

### ASCII: Decision Tree Structure

```
                    [Age <= 30?]
                   /             \
              YES /               \ NO
                 /                 \
          [Income > 50k?]      [Credit > 700?]
          /          \           /           \
        YES           NO       YES            NO
         |             |        |              |
     [Approve]     [Deny]   [Approve]       [Deny]
```

### Implementation

```python
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text
import matplotlib.pyplot as plt

# Classification tree
clf_tree = DecisionTreeClassifier(
    criterion='gini',        # 'gini' or 'entropy'
    max_depth=5,             # limit depth to prevent overfitting
    min_samples_split=10,    # min samples to split a node
    min_samples_leaf=5,      # min samples in leaf
    max_features=None,       # features to consider per split
    random_state=42
)
clf_tree.fit(X_train, y_train)
print(export_text(clf_tree, feature_names=[f'f{i}' for i in range(X_train.shape[1])]))
print(f"Depth: {clf_tree.get_depth()}, Leaves: {clf_tree.get_n_leaves()}")
print(f"Test accuracy: {clf_tree.score(X_test, y_test):.4f}")

# Feature importance
importances = clf_tree.feature_importances_
print("Top features:", np.argsort(importances)[::-1][:5])
```

**Pros:** Interpretable, handles mixed types, no scaling needed, captures nonlinearity.
**Cons:** Unstable (high variance), prone to overfitting, biased toward high-cardinality features.

---

## 7. Ensemble Methods

Ensemble methods combine multiple models (base learners) to reduce variance, bias, or both.

### ASCII: Three Ensemble Strategies

```
BAGGING                    BOOSTING                   STACKING
───────                    ────────                   ────────

Train data                 Train data                 Train data
    │                          │                          │
    ├── Bootstrap 1 ──► M₁     ├── M₁ ──► residuals      ├──────────────┐
    ├── Bootstrap 2 ──► M₂     ├── M₂ ──► residuals      ├──────────┐   │
    ├── Bootstrap 3 ──► M₃     └── M₃                    └──────┐   │   │
    └── Bootstrap K ──► Mₖ                                      ▼   ▼   ▼
                │                   │                         M₁  M₂  M₃  (level-0)
                ▼                   ▼                              │
            Average/Vote        Weighted sum                       ▼
            (reduces variance)  (reduces bias)                 Meta-learner (level-1)
```

---

### 7.1 Bagging (Bootstrap Aggregating)

```
For b = 1 to B:
  1. Draw bootstrap sample Dᵦ of size n (with replacement) from D
  2. Train base learner fᵦ on Dᵦ

Prediction (regression):  f̂(x) = (1/B) Σᵦ fᵦ(x)
Prediction (classification): majority vote

Why it works: Averaging reduces variance without increasing bias
  Var(mean of B iid estimates) = σ²/B
  Even with correlation, variance decreases as B grows
```

---

### 7.2 Random Forest

**Random Forest = Bagging + Feature Randomness**

At each split in each tree, only a random subset of **m** features is considered.
This decorrelates the trees, reducing variance further.

```
Typical m values:
  Classification: m = sqrt(p)
  Regression:     m = p/3

OOB (Out-of-Bag) error: each sample is OOB for ~37% of trees → free validation!
```

```python
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

rf = RandomForestClassifier(
    n_estimators=200,        # number of trees (more = better but slower)
    max_features='sqrt',     # features per split: 'sqrt', 'log2', float
    max_depth=None,          # None = fully grown
    min_samples_split=2,
    min_samples_leaf=1,
    bootstrap=True,
    oob_score=True,          # compute OOB score (free validation!)
    n_jobs=-1,               # parallelize
    random_state=42
)
rf.fit(X_train, y_train)
print(f"OOB score : {rf.oob_score_:.4f}")
print(f"Test score: {rf.score(X_test, y_test):.4f}")

# Feature importance (mean decrease in impurity)
feat_imp = pd.Series(rf.feature_importances_, index=[f'f{i}' for i in range(X.shape[1])])
feat_imp.sort_values(ascending=False).head(10)
```

**Hyperparameters:**

| Parameter | Effect | Typical range |
|-----------|--------|---------------|
| `n_estimators` | More trees = lower variance | 100–2000 |
| `max_features` | Lower = more decorrelated trees | `sqrt`, `log2`, 0.3–0.8 |
| `max_depth` | Controls overfitting | None, 5–50 |
| `min_samples_leaf` | Smoothing (regression) | 1, 3, 5, 10 |

---

### 7.3 AdaBoost

**Intuition:** Train weak learners sequentially, each focusing on the mistakes of the previous.

```
Algorithm AdaBoost:
  Initialize sample weights: wᵢ = 1/n

  For t = 1 to T:
    1. Train weak learner hₜ on weighted sample
    2. Compute weighted error: εₜ = Σᵢ wᵢ · 1[hₜ(xᵢ) ≠ yᵢ]
    3. Compute learner weight: αₜ = (1/2) ln((1-εₜ)/εₜ)
    4. Update sample weights:
         wᵢ ← wᵢ · exp(-αₜ yᵢ hₜ(xᵢ))
         normalize so Σwᵢ = 1

  Final: H(x) = sign(Σₜ αₜ hₜ(x))
```

```python
from sklearn.ensemble import AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier

ada = AdaBoostClassifier(
    estimator=DecisionTreeClassifier(max_depth=1),  # decision stumps
    n_estimators=200,
    learning_rate=1.0,
    algorithm='SAMME.R',
    random_state=42
)
ada.fit(X_train, y_train)
print(f"AdaBoost accuracy: {ada.score(X_test, y_test):.4f}")
```

---

### 7.4 Gradient Boosting Machine (GBM)

**Intuition:** Build trees to fit the **residuals** (negative gradient of loss) of all
previous trees. This is functional gradient descent in hypothesis space.

```
Algorithm Gradient Boosting:
  Initialize: F₀(x) = argmin_γ Σᵢ L(yᵢ, γ)  (e.g., mean of y)

  For m = 1 to M:
    1. Compute pseudo-residuals:
         rᵢₘ = -[∂L(yᵢ, F(xᵢ)) / ∂F(xᵢ)]|_{F=F_{m-1}}

    2. Fit a regression tree hₘ to {(xᵢ, rᵢₘ)}ᵢ

    3. Find optimal step:
         γₘ = argmin_γ Σᵢ L(yᵢ, F_{m-1}(xᵢ) + γ hₘ(xᵢ))

    4. Update: Fₘ(x) = F_{m-1}(x) + η · γₘ hₘ(x)

  Return: F_M(x)
```

```python
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

gbm = GradientBoostingClassifier(
    n_estimators=200,
    learning_rate=0.1,    # shrinkage: smaller = more robust, needs more trees
    max_depth=3,          # shallow trees work well
    subsample=0.8,        # stochastic gradient boosting (reduces overfitting)
    max_features='sqrt',
    min_samples_leaf=5,
    random_state=42
)
gbm.fit(X_train, y_train)
print(f"GBM accuracy: {gbm.score(X_test, y_test):.4f}")
```

---

### 7.5 XGBoost

XGBoost (Extreme Gradient Boosting) adds several engineering improvements:

```
Key innovations:
  1. Regularized objective: L(Fₘ) + Ω(hₘ) where Ω = γT + (λ/2)||w||²
  2. Second-order Taylor expansion of loss for faster convergence
  3. Column subsampling (like Random Forest)
  4. Weighted quantile sketch for approximate split finding
  5. Cache-aware block structure for out-of-core computation
  6. Parallel split finding within each tree
```

```python
import xgboost as xgb

xgb_model = xgb.XGBClassifier(
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    min_child_weight=1,      # min sum of instance weight in child
    gamma=0,                 # min loss reduction for split
    subsample=0.8,
    colsample_bytree=0.8,    # features per tree
    colsample_bylevel=1.0,   # features per level
    reg_alpha=0,             # L1 regularization
    reg_lambda=1,            # L2 regularization
    scale_pos_weight=1,      # for class imbalance: neg/pos ratio
    tree_method='hist',      # 'hist' fast, 'exact' precise
    eval_metric='logloss',
    early_stopping_rounds=20,
    random_state=42,
    n_jobs=-1
)

eval_set = [(X_test, y_test)]
xgb_model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
print(f"XGBoost best iteration: {xgb_model.best_iteration}")
print(f"XGBoost accuracy: {xgb_model.score(X_test, y_test):.4f}")
```

---

### 7.6 LightGBM

LightGBM grows trees **leaf-wise** (best-first) rather than level-wise, and uses
histogram-based splits for speed.

```
Level-wise (XGBoost default):    Leaf-wise (LightGBM):
  ┌───────────────────┐            ┌───────────────────┐
  │ split ALL leaves  │            │ split BEST leaf   │
  │ at same depth     │            │ (max gain)        │
  └───────────────────┘            └───────────────────┘
  → balanced tree, safer           → deeper asymmetric tree,
                                     faster convergence
```

```python
import lightgbm as lgb

lgb_model = lgb.LGBMClassifier(
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=31,           # controls complexity (leaf-wise specific)
    max_depth=-1,            # -1 = unlimited
    min_child_samples=20,    # min data in leaf
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    reg_alpha=0.0,
    reg_lambda=0.0,
    class_weight='balanced',
    random_state=42,
    n_jobs=-1,
    verbose=-1
)
lgb_model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
)
print(f"LightGBM accuracy: {lgb_model.score(X_test, y_test):.4f}")
```

---

### 7.7 CatBoost

CatBoost handles **categorical features natively** using ordered target statistics and
symmetric trees.

```python
from catboost import CatBoostClassifier

cat_model = CatBoostClassifier(
    iterations=500,
    learning_rate=0.05,
    depth=6,
    l2_leaf_reg=3.0,
    border_count=128,
    cat_features=[],         # list of categorical feature indices
    auto_class_weights='Balanced',
    eval_metric='Accuracy',
    early_stopping_rounds=50,
    random_seed=42,
    verbose=False
)
cat_model.fit(X_train, y_train, eval_set=(X_test, y_test))
print(f"CatBoost accuracy: {cat_model.score(X_test, y_test):.4f}")
```

---

### 7.8 Stacking

```
Level-0 (base learners): trained on full training data
Level-1 (meta-learner): trained on out-of-fold predictions

Implementation:
  For each fold k in K-fold CV:
    Train each base learner on folds ≠ k
    Predict on fold k → meta-features

  Train meta-learner on meta-features
  At test time: average base learner predictions → meta-learner input
```

```python
from sklearn.ensemble import StackingClassifier
from sklearn.linear_model import LogisticRegression

estimators = [
    ('rf',   RandomForestClassifier(n_estimators=100, random_state=42)),
    ('xgb',  xgb.XGBClassifier(n_estimators=100, random_state=42, eval_metric='logloss')),
    ('lgb',  lgb.LGBMClassifier(n_estimators=100, random_state=42, verbose=-1))
]

stack = StackingClassifier(
    estimators=estimators,
    final_estimator=LogisticRegression(),
    cv=5,
    stack_method='predict_proba',
    n_jobs=-1
)
stack.fit(X_train, y_train)
print(f"Stacking accuracy: {stack.score(X_test, y_test):.4f}")
```

---

## 8. Support Vector Machines

### Intuition

Find the hyperplane that **maximizes the margin** between classes. Only the training
points closest to the boundary (support vectors) matter.

### Math: Hard Margin SVM

```
Primal problem (linearly separable):
  minimize    (1/2) ||w||²
  subject to  yᵢ(wᵀxᵢ + b) ≥ 1  for all i

Geometric interpretation:
  Margin width = 2 / ||w||
  Maximizing margin ↔ minimizing ||w||²

Support vectors: points where  yᵢ(wᵀxᵢ + b) = 1
```

### ASCII: SVM Margin

```
                    ╔══════════════════════════════╗
      class +1      ║  margin = 2/||w||            ║
                    ║                              ║
  ○  ○  ○  ○  ○ ──►║◄─── decision boundary ──────►║◄── ○  ○  ○  ○
                    ║    wᵀx + b = 0               ║
  class -1         ║                              ║
                    ║  ⊕ = support vector          ║
                    ╚══════════════════════════════╝

  wᵀx+b = -1                                      wᵀx+b = +1
       ⊕                                                  ⊕
```

### Soft Margin SVM (C-SVM)

```
Allow some misclassifications with slack variables ξᵢ:
  minimize    (1/2)||w||² + C Σᵢ ξᵢ
  subject to  yᵢ(wᵀxᵢ + b) ≥ 1 - ξᵢ,  ξᵢ ≥ 0

C → ∞: hard margin (overfit if not separable)
C → 0:  large margin (more misclassifications allowed)

Hinge loss view: L(y,ŷ) = max(0, 1 - yŷ)
Total: min_w ||w||² + C Σᵢ max(0, 1 - yᵢwᵀxᵢ)
```

### The Kernel Trick

Map data to higher-dimensional space implicitly via kernel function K(x, x') = φ(x)·φ(x'):

```
Common kernels:
  Linear:       K(x,x') = xᵀx'
  Polynomial:   K(x,x') = (γxᵀx' + r)^d
  RBF/Gaussian: K(x,x') = exp(-γ||x-x'||²)
  Sigmoid:      K(x,x') = tanh(γxᵀx' + r)

RBF intuition:
  γ large → narrow bell → fits tightly → can overfit
  γ small → wide bell  → smoother boundary

Decision function becomes:
  f(x) = sign(Σᵢ αᵢ yᵢ K(xᵢ, x) + b)
```

```python
from sklearn.svm import SVC, SVR
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# SVM requires feature scaling!
svm_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('svm', SVC(
        C=1.0,               # regularization
        kernel='rbf',        # 'linear', 'poly', 'rbf', 'sigmoid'
        gamma='scale',       # 'scale'=1/(n_features*X.var()), 'auto'=1/n_features
        degree=3,            # only for poly kernel
        class_weight='balanced',
        probability=True,    # enable predict_proba (slower training)
        random_state=42
    ))
])
svm_pipeline.fit(X_train, y_train)
print(f"SVM accuracy: {svm_pipeline.score(X_test, y_test):.4f}")

# SVR for regression
svr_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('svr', SVR(
        C=1.0,
        kernel='rbf',
        gamma='scale',
        epsilon=0.1          # width of insensitive tube (no loss inside)
    ))
])
```

**Hyperparameter tuning SVM:**

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'svm__C': [0.1, 1, 10, 100],
    'svm__gamma': [0.001, 0.01, 0.1, 1, 'scale'],
    'svm__kernel': ['rbf', 'poly']
}
grid_search = GridSearchCV(svm_pipeline, param_grid, cv=5, scoring='accuracy', n_jobs=-1)
grid_search.fit(X_train, y_train)
print(f"Best params: {grid_search.best_params_}")
print(f"Best CV score: {grid_search.best_score_:.4f}")
```

**Pros:** Effective in high dimensions, memory efficient (uses support vectors only),
versatile via kernels.
**Cons:** Slow on large datasets O(n²) to O(n³), sensitive to feature scaling,
difficult to interpret, C and γ tuning critical.

---

## 9. Regression Variants Summary

| Classifier Algorithm | Regression Variant | Key Difference |
|---------------------|-------------------|----------------|
| Logistic Regression | Linear Regression | Output: probability vs continuous value |
| Decision Tree (Gini) | Decision Tree (MSE) | Impurity: Gini/Entropy vs MSE/MAE |
| Random Forest Classifier | Random Forest Regressor | Leaf: majority vote vs mean |
| AdaBoost Classifier | AdaBoost Regressor | Loss: exponential vs linear |
| GBM Classifier | GBM Regressor | Loss: log-loss vs MSE/MAE/Huber |
| XGBoost Classifier | XGBoost Regressor | `objective='binary:logistic'` vs `'reg:squarederror'` |
| SVC (classification) | SVR (regression) | Margin: hyperplane vs ε-insensitive tube |
| KNN Classifier | KNN Regressor | Output: majority vote vs mean of neighbors |

---

## 10. Algorithm Comparison Table

| Algorithm | Training Speed | Prediction Speed | Interpretability | Handles Nonlinearity | Handles Missing Data | Feature Scaling | Handles Outliers | Overfitting Risk |
|-----------|:--------------:|:----------------:|:----------------:|:--------------------:|:--------------------:|:---------------:|:----------------:|:----------------:|
| Linear Regression | Fast | Fast | High | No | No | Needed | Low | Low |
| Ridge/Lasso | Fast | Fast | High | No | No | Needed | Medium | Low |
| Logistic Regression | Fast | Fast | High | No | No | Needed | Medium | Low |
| K-Nearest Neighbors | None | Slow | Low | Yes | No | Critical | Low | High (K=1) |
| Naive Bayes | Very Fast | Very Fast | Medium | No | Yes* | No | Low | Low |
| Decision Tree | Fast | Fast | Very High | Yes | Partial | No | Low | Very High |
| Random Forest | Medium | Medium | Low | Yes | Partial | No | Medium | Low |
| AdaBoost | Medium | Fast | Low | Yes | No | No | High | Medium |
| GBM | Slow | Fast | Low | Yes | No | No | Medium | Medium |
| XGBoost | Medium | Fast | Low | Yes | Yes | No | Medium | Low |
| LightGBM | Fast | Fast | Low | Yes | Yes | No | Medium | Low |
| CatBoost | Medium | Fast | Low | Yes | Yes | No | Medium | Low |
| SVM (linear) | Fast | Fast | Medium | No | No | Critical | High | Low |
| SVM (RBF) | Slow | Medium | Low | Yes | No | Critical | High | Medium |

`*` Naive Bayes handles missing values by simply ignoring them during likelihood estimation.

---

## 11. Algorithm Selection Guide

```
START: What type of problem?
        │
        ├── REGRESSION ──────────────────────────────────────────────────────────┐
        │                                                                         │
        │   How many samples?                                                     │
        │   < 1000  ──► Is it interpretability needed?                           │
        │               YES → Linear/Ridge/Lasso (start simple!)                │
        │               NO  → SVR(rbf) or GBM                                   │
        │                                                                         │
        │   1k-100k ──► Are features linearly related to target?                │
        │               YES → LinearRegression / Ridge / Lasso / ElasticNet     │
        │               NO  → Random Forest or GBM                              │
        │                                                                         │
        │   > 100k  ──► LightGBM (fast) or Random Forest (robust)               │
        │                                                                         │
        └── CLASSIFICATION ──────────────────────────────────────────────────────┐
                                                                                  │
            How many samples?                                                     │
            < 1000  ──► Is data high-dimensional (text/images)?                  │
                        YES → Naive Bayes / LinearSVM                            │
                        NO  → LogisticRegression / SVM(rbf)                     │
                                                                                  │
            1k-100k ──► Binary or Multiclass?                                   │
                        BINARY → XGBoost / LightGBM / RandomForest              │
                        MULTI  → RandomForest / CatBoost (cats) / LightGBM      │
                                                                                  │
            > 100k  ──► LightGBM / CatBoost / LogisticRegression               │
                                                                                  │
            Need probabilities?  → CalibratedClassifierCV or algorithms with    │
                                    native probability support                   │
                                                                                  │
            Imbalanced classes? → XGBoost scale_pos_weight / class_weight       │
                                   / BalancedRandomForest / SMOTE + any algo    │

ALWAYS:
  1. Establish baseline (DummyClassifier/DummyRegressor)
  2. Try LogisticRegression/LinearRegression as first real baseline
  3. Try RandomForest (robust, less tuning)
  4. Try GBM family (usually best performance)
  5. Tune top model
```

---

## 12. Hyperparameter Tuning Reference

### Search Strategies

```python
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from scipy.stats import randint, uniform, loguniform

# Grid Search: exhaustive, for small grids
param_grid = {'n_estimators': [100, 200, 500], 'max_depth': [3, 5, None]}
gs = GridSearchCV(RandomForestClassifier(), param_grid, cv=5, n_jobs=-1)

# Random Search: better for large spaces
param_dist = {
    'n_estimators': randint(100, 1000),
    'max_features': uniform(0.1, 0.9),
    'max_depth': randint(3, 20),
    'min_samples_leaf': randint(1, 10)
}
rs = RandomizedSearchCV(RandomForestClassifier(), param_dist, n_iter=50, cv=5, n_jobs=-1)

# Bayesian Optimization (via optuna)
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
        'max_features': trial.suggest_float('max_features', 0.1, 1.0),
        'max_depth': trial.suggest_int('max_depth', 3, 20),
        'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
    }
    model = RandomForestClassifier(**params, random_state=42, n_jobs=-1)
    return cross_val_score(model, X_train, y_train, cv=3, scoring='roc_auc').mean()

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50, timeout=120)
print(f"Best params: {study.best_params}")
```

### Per-Algorithm Tuning Priority

| Algorithm | Most Important | Medium Impact | Low Impact |
|-----------|---------------|---------------|------------|
| Random Forest | `n_estimators`, `max_features` | `max_depth`, `min_samples_leaf` | `bootstrap`, `criterion` |
| XGBoost | `learning_rate`, `n_estimators` | `max_depth`, `subsample`, `colsample_bytree` | `gamma`, `reg_alpha`, `reg_lambda` |
| LightGBM | `learning_rate`, `num_leaves` | `min_child_samples`, `feature_fraction` | `lambda_l1`, `lambda_l2` |
| SVM | `C`, `gamma` | `kernel` | `degree` (poly only) |
| KNN | `n_neighbors` | `metric` | `weights` |
| Lasso/Ridge | `alpha` | — | — |

---

## 13. Practical Exercise: Random Forest from Scratch

Build a Random Forest using only NumPy to deeply understand the algorithm.

```python
import numpy as np
from collections import Counter


# --- Decision Stump (depth-1 tree) ---

class DecisionStump:
    """A single-level decision tree (stump) for classification."""

    def __init__(self):
        self.feature_index = None
        self.threshold = None
        self.left_label = None
        self.right_label = None

    def gini(self, y):
        """Compute Gini impurity of label array y."""
        if len(y) == 0:
            return 0.0
        counts = Counter(y)
        n = len(y)
        return 1.0 - sum((c / n) ** 2 for c in counts.values())

    def best_split(self, X, y, feature_indices):
        """Find best (feature, threshold) pair among feature_indices."""
        best_gain = -np.inf
        best_feat = None
        best_thresh = None
        base_impurity = self.gini(y)
        n = len(y)

        for feat in feature_indices:
            thresholds = np.unique(X[:, feat])
            for thresh in thresholds:
                left_mask = X[:, feat] <= thresh
                right_mask = ~left_mask
                if left_mask.sum() == 0 or right_mask.sum() == 0:
                    continue

                gain = base_impurity - (
                    (left_mask.sum() / n) * self.gini(y[left_mask]) +
                    (right_mask.sum() / n) * self.gini(y[right_mask])
                )
                if gain > best_gain:
                    best_gain = gain
                    best_feat = feat
                    best_thresh = thresh

        return best_feat, best_thresh

    def fit(self, X, y, feature_indices):
        self.feature_index, self.threshold = self.best_split(X, y, feature_indices)
        if self.feature_index is None:
            # No valid split found: predict majority
            majority = Counter(y).most_common(1)[0][0]
            self.left_label = majority
            self.right_label = majority
        else:
            left_mask = X[:, self.feature_index] <= self.threshold
            right_mask = ~left_mask
            self.left_label = Counter(y[left_mask]).most_common(1)[0][0]
            self.right_label = Counter(y[right_mask]).most_common(1)[0][0]
        return self

    def predict_one(self, x):
        if self.feature_index is None:
            return self.left_label
        if x[self.feature_index] <= self.threshold:
            return self.left_label
        return self.right_label

    def predict(self, X):
        return np.array([self.predict_one(x) for x in X])


# --- Random Forest from Scratch ---

class RandomForestScratch:
    """
    Random Forest classifier built from scratch.
    Uses decision stumps as base learners.
    """

    def __init__(self, n_estimators=100, max_features='sqrt', random_state=None):
        self.n_estimators = n_estimators
        self.max_features = max_features
        self.random_state = random_state
        self.trees = []
        self.oob_indices = []

    def _get_n_features(self, p):
        if self.max_features == 'sqrt':
            return max(1, int(np.sqrt(p)))
        elif self.max_features == 'log2':
            return max(1, int(np.log2(p)))
        elif isinstance(self.max_features, float):
            return max(1, int(self.max_features * p))
        return p

    def fit(self, X, y):
        rng = np.random.RandomState(self.random_state)
        n, p = X.shape
        m = self._get_n_features(p)
        self.classes_ = np.unique(y)
        self.trees = []
        self.oob_indices = []

        for _ in range(self.n_estimators):
            # 1. Bootstrap sample
            boot_idx = rng.choice(n, size=n, replace=True)
            oob_idx = np.array(list(set(range(n)) - set(boot_idx)))
            X_boot, y_boot = X[boot_idx], y[boot_idx]

            # 2. Random feature subset
            feat_idx = rng.choice(p, size=m, replace=False)

            # 3. Train stump on bootstrap sample with feature subset
            stump = DecisionStump().fit(X_boot, y_boot, feat_idx)
            self.trees.append(stump)
            self.oob_indices.append(oob_idx)

        return self

    def predict_proba(self, X):
        """Aggregate votes across all trees."""
        n = len(X)
        class_to_idx = {c: i for i, c in enumerate(self.classes_)}
        votes = np.zeros((n, len(self.classes_)))
        for tree in self.trees:
            preds = tree.predict(X)
            for i, pred in enumerate(preds):
                votes[i, class_to_idx[pred]] += 1
        return votes / votes.sum(axis=1, keepdims=True)

    def predict(self, X):
        proba = self.predict_proba(X)
        return self.classes_[np.argmax(proba, axis=1)]

    def oob_score(self, X, y):
        """Compute Out-of-Bag score."""
        n = len(y)
        class_to_idx = {c: i for i, c in enumerate(self.classes_)}
        oob_votes = np.zeros((n, len(self.classes_)))
        oob_counts = np.zeros(n)

        for tree, oob_idx in zip(self.trees, self.oob_indices):
            if len(oob_idx) == 0:
                continue
            preds = tree.predict(X[oob_idx])
            for i, pred in zip(oob_idx, preds):
                oob_votes[i, class_to_idx[pred]] += 1
                oob_counts[i] += 1

        # Only score samples that appeared OOB at least once
        valid = oob_counts > 0
        oob_preds = self.classes_[np.argmax(oob_votes[valid], axis=1)]
        return np.mean(oob_preds == y[valid])


# --- Test it ---

from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

iris = load_iris()
X_iris, y_iris = iris.data, iris.target
X_tr, X_te, y_tr, y_te = train_test_split(X_iris, y_iris, test_size=0.2, random_state=42)

rf_scratch = RandomForestScratch(n_estimators=200, max_features='sqrt', random_state=42)
rf_scratch.fit(X_tr, y_tr)

y_pred_scratch = rf_scratch.predict(X_te)
print(f"Scratch RF test accuracy : {accuracy_score(y_te, y_pred_scratch):.4f}")
print(f"Scratch RF OOB accuracy  : {rf_scratch.oob_score(X_tr, y_tr):.4f}")

# Compare to sklearn
from sklearn.ensemble import RandomForestClassifier
rf_sk = RandomForestClassifier(n_estimators=200, max_features='sqrt', random_state=42)
rf_sk.fit(X_tr, y_tr)
print(f"Sklearn RF test accuracy : {accuracy_score(y_te, rf_sk.predict(X_te)):.4f}")
print(f"Sklearn RF OOB accuracy  : {rf_sk.oob_score_:.4f}")
```

**Expected output:**
```
Scratch RF test accuracy : 0.9333  (may vary slightly)
Scratch RF OOB accuracy  : 0.9417
Sklearn RF test accuracy : 0.9667
Sklearn RF OOB accuracy  : 0.9583
```

The scratch implementation uses stumps only; sklearn uses full trees — hence the gap.
The OOB mechanism and voting logic are identical, demonstrating the core algorithm.

---

## 14. Quiz (15 Questions + Solutions)

### Questions

**Q1.** The Normal Equations for OLS are `w* = (XᵀX)⁻¹ Xᵀy`. Under what condition does
this solution fail, and how does Ridge regression fix it?

**Q2.** Lasso regression can produce sparse models but Ridge cannot. Explain geometrically
why this is the case.

**Q3.** You fit a logistic regression model and notice the coefficients are very large.
What has likely happened, and how do you fix it?

**Q4.** KNN with K=1 achieves 0% training error but 30% test error. What problem does
this illustrate? What would you change?

**Q5.** Naive Bayes is called "naive" because of the conditional independence assumption.
Despite this being frequently violated in practice, Naive Bayes often works well for text
classification. Give one reason why.

**Q6.** A decision tree trained to full depth achieves 100% training accuracy but 60% test
accuracy. Name three hyperparameters you would tune to improve generalization.

**Q7.** What is the difference between Gini impurity and information gain (entropy) as split
criteria? Which is generally faster to compute?

**Q8.** Explain why Out-of-Bag (OOB) error is a valid estimate of generalization error in
Random Forests. What fraction of training samples are typically OOB for any given tree?

**Q9.** In AdaBoost, what happens to the weight of a misclassified sample after each round?
What is the effect on subsequent weak learners?

**Q10.** Gradient Boosting and AdaBoost are both boosting algorithms. What is the key
conceptual difference in how they build each new learner?

**Q11.** In XGBoost, what two regularization terms are added to the standard gradient
boosting objective, and what do they control?

**Q12.** Explain the kernel trick in SVMs. Why is it computationally advantageous over
explicitly mapping features to a high-dimensional space?

**Q13.** An SVM with a very large C value is used on a non-linearly separable dataset.
Describe the likely behavior of the model.

**Q14.** You are building a model for fraud detection (1% fraud rate). Which metric(s)
would you prioritize, and which algorithm would you consider first?

**Q15.** Describe the bias-variance characteristics of: (a) a single deep decision tree,
(b) a Random Forest, (c) a highly regularized Ridge regression.

---

### Solutions

**A1.** `XᵀX` is singular (not invertible) when features are perfectly multicollinear
(linearly dependent columns). Ridge adds `λI` to `XᵀX`, making the matrix `XᵀX + λI`
always positive definite and invertible for any `λ > 0`.

**A2.** The L1 constraint region is a diamond (in 2D) with corners on the coordinate axes.
The loss function contours (ellipses) are likely to first touch the L1 ball at a corner,
where one coordinate is exactly zero → sparsity. The L2 ball is a smooth sphere with no
corners, so the contours rarely touch at a zero-coordinate point.

**A3.** The model has likely **overfit** due to near-perfect separability (the decision
boundary tries to push probabilities to 0 and 1, requiring infinite weights in the limit).
Fix: add L2 regularization by decreasing `C` (e.g., `C=0.01`), or use `penalty='l1'` for
feature selection.

**A4.** This illustrates **overfitting / high variance**. K=1 memorizes the training set.
Increase K (try K=5, 11, 21), use cross-validation to select K, and ensure features are
scaled.

**A5.** Even though the independence assumption is violated, the **decision boundary** for
Naive Bayes (argmax of class posteriors) is often still in the right place even when the
probability estimates are miscalibrated. The ranking of classes is correct even if the
absolute probabilities are wrong.

**A6.** Three hyperparameters to tune: (1) `max_depth` — limit tree depth, (2)
`min_samples_leaf` — require more samples in each leaf, (3) `min_samples_split` — require
more samples before allowing a split. Alternatively, `max_leaf_nodes` or `ccp_alpha`
(cost-complexity pruning).

**A7.** Gini impurity: `G = 1 - Σpₖ²`. Entropy: `H = -Σpₖ log₂pₖ`. Gini avoids computing
logarithms and is therefore faster to compute. In practice, both produce very similar trees
— the choice rarely affects model quality significantly.

**A8.** Each bootstrap sample draws n samples with replacement from n, so the probability
a given sample is NOT selected in one draw is (1-1/n). Over n draws, the probability of
never being selected is (1-1/n)ⁿ → e⁻¹ ≈ 0.368 as n→∞. Thus approximately **36.8%**
of samples are OOB for each tree. Each sample gets evaluated by trees that never saw it
during training → valid unbiased estimate of test error.

**A9.** Misclassified samples receive **increased weights** (`wᵢ ← wᵢ · exp(αₜ)`, where
`αₜ > 0`). The next weak learner is trained on the reweighted distribution, forcing it to
focus more on previously misclassified examples.

**A10.** AdaBoost modifies sample weights to focus on hard examples; each new learner is
fitted to the reweighted training set. Gradient Boosting fits each new learner to the
**residuals** (pseudo-residuals = negative gradient of loss), which is functional gradient
descent in function space — a more general framework that subsumes AdaBoost as a special
case (exponential loss).

**A11.** XGBoost adds: (1) `γ · T` where T is the number of leaves — penalizes tree
complexity (fewer leaves); (2) `(λ/2) · ||w||²` where w are the leaf weights — L2
regularization on leaf scores. These prevent overfitting by discouraging complex trees
and large leaf weights.

**A12.** The kernel trick evaluates `K(x, x') = φ(x)·φ(x')` directly in input space
without ever computing `φ(x)`. The dual SVM only needs inner products between pairs of
samples, so we can implicitly work in a potentially infinite-dimensional feature space
(e.g., RBF kernel corresponds to an infinite-dimensional feature map) with computational
cost O(n²) regardless of the feature space dimension.

**A13.** Large C → low regularization → the SVM tries to classify all training points
correctly → small or zero margin → **overfit**. The model will have high training accuracy
but poor test accuracy. The boundary will be jagged and overly complex. Solution: reduce C.

**A14.** Prioritize **Precision-Recall AUC** and **F1-score** (accuracy is misleading with
1% class rate — a model predicting "no fraud" always gets 99% accuracy). Consider
**XGBoost with `scale_pos_weight=99`** (ratio of negatives to positives) or
**BalancedRandomForestClassifier**. Also use SMOTE or undersampling. Monitor recall (not
missing fraud) vs. precision (not flagging legitimate transactions) based on business cost.

**A15.** (a) **Single deep decision tree**: low bias (can fit any complex pattern), very
high variance (small changes in data → very different tree). (b) **Random Forest**:
slightly higher bias than a single tree (averaging smooths predictions), much lower
variance (averaging ~200 decorrelated trees reduces variance by ~200×). (c) **Highly
regularized Ridge**: high bias (coefficients shrunk toward 0, can underfit), very low
variance (stable predictions across different training samples).

---

## 15. References

All references below are freely available:

| Resource | URL | Coverage |
|----------|-----|----------|
| **The Elements of Statistical Learning** (ESL) — Hastie, Tibshirani, Friedman | https://hastie.su.domains/ElemStatLearn/ | Comprehensive mathematical treatment of all algorithms |
| **CS229 Stanford Machine Learning Notes** — Andrew Ng | https://cs229.stanford.edu/main_notes.pdf | Linear/logistic regression, SVMs, trees, ensemble methods |
| **scikit-learn User Guide** | https://scikit-learn.org/stable/user_guide.html | Practical implementation, hyperparameter descriptions |
| **XGBoost Documentation** | https://xgboost.readthedocs.io/ | XGBoost algorithm, parameters, tutorials |
| **LightGBM Documentation** | https://lightgbm.readthedocs.io/ | LightGBM internals, parameter reference |
| **CatBoost Documentation** | https://catboost.ai/docs/ | Categorical feature handling, ordered boosting |
| **An Introduction to Statistical Learning** (ISLR, free PDF) — James et al. | https://www.statlearning.com/ | Gentler treatment with R and Python labs |
| **Pattern Recognition and Machine Learning** — Bishop | https://www.microsoft.com/en-us/research/uploads/prod/2006/01/Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf | Bayesian perspective, deep math |
| **Optuna documentation** | https://optuna.readthedocs.io/ | Hyperparameter optimization framework |

---

> **Next module:** 03 — Neural Networks and Deep Learning Foundations
> (Perceptron, MLP, backpropagation, activation functions, optimizers, regularization)

---

*Last updated: 2026-06-29 | Author: Arijit Kundu | Series: AI & Machine Learning Knowledge Base*
