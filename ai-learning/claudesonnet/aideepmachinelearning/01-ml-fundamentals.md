# Machine Learning Fundamentals
### A Complete, Practitioner-Focused Reference

> **Level:** Beginner to Intermediate  
> **Prerequisites:** Basic Python, high-school statistics  
> **Time to complete:** 4–6 hours  
> **Last updated:** June 2026

---

## Table of Contents

1. [What is Machine Learning?](#1-what-is-machine-learning)
2. [The ML Taxonomy](#2-the-ml-taxonomy)
3. [The ML Workflow](#3-the-ml-workflow)
4. [Bias-Variance Tradeoff](#4-bias-variance-tradeoff)
5. [Overfitting and Underfitting](#5-overfitting-and-underfitting)
6. [Model Evaluation Deep Dive](#6-model-evaluation-deep-dive)
7. [The No Free Lunch Theorem](#7-the-no-free-lunch-theorem)
8. [Feature Engineering Fundamentals](#8-feature-engineering-fundamentals)
9. [Data Splitting and Data Leakage](#9-data-splitting-and-data-leakage)
10. [Class Imbalance](#10-class-imbalance)
11. [Case Study: End-to-End ML Problem](#11-case-study-end-to-end-ml-problem)
12. [Quiz: 15 Questions with Solutions](#12-quiz-15-questions-with-solutions)
13. [References and Learning Resources](#13-references-and-learning-resources)

---

## 1. What is Machine Learning?

Machine learning is a subfield of artificial intelligence in which a system **learns patterns from data** rather than following explicitly programmed rules. The classic definition by Tom Mitchell (1997) remains the clearest:

> *"A computer program is said to learn from experience E with respect to some class of tasks T and performance measure P, if its performance at tasks in T, as measured by P, improves with experience E."*

### Traditional Programming vs. Machine Learning

```
TRADITIONAL PROGRAMMING
┌──────────┐    ┌─────────┐    ┌──────────┐
│   Data   │───▶│  Rules  │───▶│ Answers  │
└──────────┘    └─────────┘    └──────────┘
   (input)      (human-coded)   (output)

MACHINE LEARNING
┌──────────┐    ┌──────────┐    ┌─────────┐
│   Data   │───▶│    ML    │───▶│  Rules  │
└──────────┘    │ Algorithm│    └─────────┘
┌──────────┐    └──────────┘    (learned model)
│ Answers  │───▶
└──────────┘
   (labels)
```

The shift is fundamental: instead of telling the computer *how* to solve a problem, we show it *examples* of the problem being solved and let it infer the logic.

### Why ML Now?

Three forces converged to make ML practical:
1. **Data** — the internet created massive labeled datasets
2. **Compute** — GPUs made matrix operations cheap at scale
3. **Algorithms** — decades of research matured into reliable methods

---

## 2. The ML Taxonomy

### Full Taxonomy Diagram

```
                        MACHINE LEARNING
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
   SUPERVISED           UNSUPERVISED       REINFORCEMENT
   LEARNING              LEARNING           LEARNING
          │                   │                   │
    ┌─────┴─────┐       ┌─────┴──────┐      ┌─────┴─────┐
    │           │       │            │      │           │
REGRESSION CLASSIF-  CLUSTERING   DIMEN-  POLICY    VALUE
           ICATION               SIONALITY GRADIENT  BASED
                                 REDUCTION
    │           │       │            │      │           │
 Linear    Binary    k-Means      PCA    PPO/A3C     Q-Learnin
 Ridge     Multi-    DBSCAN       t-SNE  REINFORCE   DQN
 Lasso     class     Gaussian     UMAP               TD(0)
 SVR       Multi-    Mixture      LDA
 Trees     label     Models       Autoencoders
 NNs       SVMs
           Trees
           NNs

                    SELF-SUPERVISED LEARNING
                    (bridges supervised + unsupervised)
                              │
                    ┌─────────┴──────────┐
                    │                    │
               CONTRASTIVE         GENERATIVE
               LEARNING            PRETRAINING
               SimCLR, MoCo        GPT, BERT
               CLIP                MAE
```

### 2.1 Supervised Learning

In supervised learning, every training example has a **label** — the correct answer. The model learns a mapping function `f(X) → y`.

#### Regression

Regression predicts a **continuous numeric output**.

| Algorithm | Strengths | Weaknesses |
|-----------|-----------|------------|
| Linear Regression | Interpretable, fast | Only linear relationships |
| Ridge / Lasso | Regularized, handles collinearity | Still linear |
| Decision Tree | Nonlinear, interpretable | Prone to overfit |
| Random Forest | Robust, handles missing data | Slow to predict |
| Gradient Boosting (XGBoost, LightGBM) | Best-in-class tabular | Many hyperparameters |
| Support Vector Regression | Effective in high dimensions | Slow on large data |
| Neural Networks | Universal approximators | Data-hungry, opaque |

**Key metrics:** MAE, MSE, RMSE, R², MAPE

#### Classification

Classification predicts a **discrete category**.

- **Binary:** spam / not-spam, disease / healthy
- **Multiclass:** digit recognition (0–9), sentiment (positive/neutral/negative)
- **Multilabel:** a photo tagged with multiple objects

**Key metrics:** Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC

### 2.2 Unsupervised Learning

No labels. The model finds structure in the data on its own.

#### Clustering

Groups similar data points together. Applications: customer segmentation, anomaly detection, document organization.

| Algorithm | Best For |
|-----------|----------|
| k-Means | Spherical clusters, known k |
| DBSCAN | Arbitrary shapes, noise-robust |
| Hierarchical | Unknown k, dendrogram exploration |
| Gaussian Mixture Models | Soft cluster membership |

#### Dimensionality Reduction

Compresses high-dimensional data into fewer dimensions while preserving important structure.

| Algorithm | Linear? | Best For |
|-----------|---------|----------|
| PCA | Yes | Visualization, noise removal, preprocessing |
| LDA | Yes | Supervised dim-reduction |
| t-SNE | No | 2D/3D visualization of clusters |
| UMAP | No | Faster than t-SNE, better global structure |
| Autoencoders | No | Nonlinear compression, generative use |

### 2.3 Self-Supervised Learning

The model creates its own supervision signal from raw unlabeled data. Examples:
- **BERT:** predict masked words in a sentence
- **GPT:** predict the next token
- **SimCLR:** learn representations where augmented views of the same image are similar

Self-supervised pretraining followed by fine-tuning on labeled data has become the dominant paradigm in NLP and is increasingly prevalent in vision.

### 2.4 Reinforcement Learning

An **agent** interacts with an **environment**, takes **actions**, and receives **rewards**. The goal is to learn a **policy** that maximizes cumulative reward.

```
         ┌───────────┐
         │           │◀─── Observation / State
         │   Agent   │
         │  (Policy) │───▶ Action
         │           │
         └───────────┘
               │ ▲
         Reward│ │Next State
               ▼ │
         ┌───────────┐
         │Environment│
         └───────────┘
```

Applications: game playing (AlphaGo, Atari), robotics, recommendation systems, LLM fine-tuning (RLHF).

---

## 3. The ML Workflow

### End-to-End Pipeline

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                        ML WORKFLOW                              │
  └─────────────────────────────────────────────────────────────────┘

  1. PROBLEM FRAMING
  ┌──────────────────┐
  │ Define objective │  ← What decision will this model power?
  │ Choose metric    │  ← What does "good" look like?
  │ Feasibility check│  ← Do we have enough data? Is the task learnable?
  └────────┬─────────┘
           │
           ▼
  2. DATA COLLECTION
  ┌──────────────────┐
  │ Identify sources │  ← Databases, APIs, web scraping, sensors
  │ Label data       │  ← Manual annotation, programmatic labeling
  │ Check licenses   │  ← Privacy, GDPR, terms of service
  └────────┬─────────┘
           │
           ▼
  3. EXPLORATORY DATA ANALYSIS (EDA)
  ┌──────────────────┐
  │ Distributions    │  ← Histograms, box plots
  │ Correlations     │  ← Heatmaps, scatter matrices
  │ Missing values   │  ← Counts, patterns (MCAR/MAR/MNAR)
  │ Outliers         │  ← IQR, Z-score, isolation forest
  └────────┬─────────┘
           │
           ▼
  4. FEATURE ENGINEERING
  ┌──────────────────┐
  │ Imputation       │  ← Fill missing values
  │ Encoding         │  ← Categorical → numeric
  │ Scaling          │  ← Normalize / standardize
  │ Feature creation │  ← Domain knowledge, interactions
  │ Selection        │  ← Remove redundant / irrelevant features
  └────────┬─────────┘
           │
           ▼
  5. MODEL SELECTION & TRAINING
  ┌──────────────────┐
  │ Baseline first   │  ← Dummy model, simple heuristic
  │ Shortlist models │  ← Based on data type, size, constraints
  │ Hyperparameter   │  ← Grid search, random search, Bayesian
  │ optimization     │
  └────────┬─────────┘
           │
           ▼
  6. EVALUATION
  ┌──────────────────┐
  │ Held-out test set│  ← Final, unbiased estimate
  │ Cross-validation │  ← Variance estimation
  │ Error analysis   │  ← Where does the model fail?
  └────────┬─────────┘
           │
           ▼
  7. DEPLOYMENT
  ┌──────────────────┐
  │ Serve as API     │  ← REST endpoint, batch job, edge device
  │ A/B test         │  ← Compare against current system
  │ Shadow mode      │  ← Log predictions, don't act on them yet
  └────────┬─────────┘
           │
           ▼
  8. MONITORING & MAINTENANCE
  ┌──────────────────┐
  │ Data drift       │  ← Input distribution changed?
  │ Concept drift    │  ← Relationship X→y changed?
  │ Performance drop │  ← Alert and retrain
  │ Feedback loops   │  ← Collect new labels from production
  └──────────────────┘
           │
           └──────────────────────────────────────────▶ (back to step 1)
```

### Step 1: Problem Framing — The Most Underrated Step

Before writing a line of code, answer these questions:
- **What is the actual business problem?** A churn-prediction model that correctly identifies churners but has no intervention mechanism solves nothing.
- **What is the ground truth label?** "Customer satisfaction" is vague. "Rated 1–2 stars on the post-order survey" is a label.
- **What data will be available at inference time?** Features you use in training must be available when the model is deployed.
- **What is the cost of different error types?** False positives vs. false negatives may have very different business costs.

---

## 4. Bias-Variance Tradeoff

This is the single most important theoretical concept in ML. Understanding it explains why models fail and how to fix them.

### Decomposing Prediction Error

For any ML model, the expected prediction error on new data can be decomposed:

```
Total Error = Bias² + Variance + Irreducible Noise
```

| Term | Definition | Cause |
|------|-----------|-------|
| **Bias** | Average error from wrong assumptions in the model | Model too simple, underfitting |
| **Variance** | Sensitivity to fluctuations in the training set | Model too complex, overfitting |
| **Irreducible Noise** | Inherent noise in the data | Cannot be reduced by any model |

### The Tradeoff Diagram

```
  Error
    │
    │  \                          /
    │   \                        /  ◀── Total Error
    │    \        ___           /
    │     \      /   \         /
    │      \    /     \       /
    │ Bias² \  /  Var  \     /
    │        \/         \   /
    │                    \ /
    │◀── Underfitting  ──▶X◀── Overfitting ──▶
    │                    ↑
    │              Sweet spot
    └──────────────────────────────────────────▶ Model Complexity


  HIGH BIAS (Underfitting):              HIGH VARIANCE (Overfitting):
  ┌──────────────────────┐              ┌──────────────────────┐
  │  Training: 60% acc   │              │  Training: 99% acc   │
  │  Validation: 58% acc │              │  Validation: 72% acc │
  │                      │              │                      │
  │  Decision boundary:  │              │  Decision boundary:  │
  │     ___________      │              │   ~·~·~·~·~·~·~·~    │
  │    /            \    │              │  /~~\  /~\ /~\ /~~\  │
  │   straight line  \   │              │  wriggly mess        │
  └──────────────────────┘              └──────────────────────┘
```

### Practical Intuition

Think of fitting a polynomial to data points:

- **Degree 1 (linear):** probably too simple for most real data — high bias
- **Degree 3–5:** often captures the true relationship — balanced
- **Degree 20:** memorizes every point including noise — high variance

The art of ML is finding the right model complexity for the amount and quality of data you have.

---

## 5. Overfitting and Underfitting

### Diagnosis

```python
import matplotlib.pyplot as plt

# Plot learning curves to diagnose
def plot_learning_curve(model, X, y):
    train_sizes = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
    train_scores = []
    val_scores = []
    
    for size in train_sizes:
        n = int(len(X) * size)
        model.fit(X[:n], y[:n])
        train_scores.append(model.score(X[:n], y[:n]))
        val_scores.append(model.score(X_val, y_val))
    
    plt.plot(train_sizes, train_scores, label='Training score')
    plt.plot(train_sizes, val_scores, label='Validation score')
    plt.legend()
```

**Overfitting signals:**
- Training accuracy >> validation accuracy
- Validation loss increases while training loss decreases
- Model memorizes training labels (near-perfect train accuracy with random labels)

**Underfitting signals:**
- Both training and validation accuracy are low
- Adding more training data does not help
- Increasing model complexity improves both train and val performance

### Remedies for Overfitting

#### 1. L1 Regularization (Lasso)

Adds penalty proportional to the **absolute value** of weights:

```
Loss = MSE + λ * Σ|wᵢ|
```

Effect: drives some weights exactly to **zero** — automatic feature selection. Useful when many features are irrelevant.

#### 2. L2 Regularization (Ridge)

Adds penalty proportional to the **square** of weights:

```
Loss = MSE + λ * Σwᵢ²
```

Effect: shrinks all weights toward zero but rarely to exactly zero. Better when all features are relevant.

#### 3. Elastic Net

Combines both:
```
Loss = MSE + λ₁ * Σ|wᵢ| + λ₂ * Σwᵢ²
```

#### 4. Dropout (Neural Networks)

```
During training:
┌─────┐    ┌──────┐    ┌──────┐    ┌──────┐
│Input│───▶│Layer1│───▶│Layer2│───▶│Output│
└─────┘    │ ✗  ✓ │    │ ✓  ✗ │    └──────┘
           │ ✓  ✗ │    │ ✗  ✓ │
           └──────┘    └──────┘
              ↑ randomly zeroed neurons (e.g. 50%)

During inference: all neurons active, weights scaled down
```

Dropout prevents neurons from co-adapting — each must learn independently useful features.

#### 5. Early Stopping

```
  Loss
    │
    │ Train \
    │        \
    │         \___________
    │                     \_____ ← training loss keeps falling
    │
    │ Val   \
    │        \_____
    │              \____
    │                   ↑ val loss starts rising here
    │                   STOP HERE
    └──────────────────────────────▶ Epochs
```

Save the model checkpoint at the validation loss minimum.

#### 6. Data Augmentation

Artificially expand the training set by applying label-preserving transformations:

| Domain | Augmentation Techniques |
|--------|------------------------|
| Images | Flip, rotate, crop, color jitter, cutout, mixup |
| Text | Back-translation, synonym replacement, random deletion |
| Audio | Time stretch, pitch shift, add noise |
| Tabular | SMOTE (see Section 10), Gaussian noise to features |

#### 7. Reduce Model Complexity

- Fewer layers / neurons (neural nets)
- Max depth, min samples leaf (trees)
- Fewer polynomial features (linear models)

---

## 6. Model Evaluation Deep Dive

Good evaluation is what separates production ML from notebook experiments.

### 6.1 Confusion Matrix

For binary classification (Positive = the class we care about):

```
                    PREDICTED
                 Positive   Negative
              ┌──────────┬──────────┐
A  Positive   │    TP    │    FN    │  ← Actual Positives
C             │          │          │    (TP + FN = all real positives)
T  ──────────────────────────────────
U  Negative   │    FP    │    TN    │  ← Actual Negatives
A             │          │          │
L             └──────────┴──────────┘

TP = True Positive  (correctly predicted positive)
TN = True Negative  (correctly predicted negative)
FP = False Positive (predicted positive, actually negative) — Type I Error
FN = False Negative (predicted negative, actually positive) — Type II Error
```

### 6.2 Derived Metrics

| Metric | Formula | Intuition |
|--------|---------|-----------|
| **Accuracy** | (TP+TN)/(TP+TN+FP+FN) | Overall correct rate — misleading when classes are imbalanced |
| **Precision** | TP/(TP+FP) | Of all predicted positives, how many are truly positive? |
| **Recall (Sensitivity)** | TP/(TP+FN) | Of all actual positives, how many did we catch? |
| **Specificity** | TN/(TN+FP) | Of all actual negatives, how many did we correctly reject? |
| **F1 Score** | 2*(P*R)/(P+R) | Harmonic mean of precision and recall |
| **F-beta** | (1+β²)*(P*R)/(β²*P+R) | β>1 weights recall; β<1 weights precision |

**Precision vs. Recall tradeoff:**

```
High Precision, Low Recall:     High Recall, Low Precision:
"Only flag when very sure"      "Catch everything, many false alarms"

Good for:                       Good for:
  - Spam filter (FP = user      - Cancer screening (FN = missed
    loses real email)             case is catastrophic)
  - Fraud block (FP = angry     - Search and rescue
    legitimate customer)        - Security alerts
```

### 6.3 ROC Curve and AUC

The ROC (Receiver Operating Characteristic) curve plots **True Positive Rate** (Recall) vs. **False Positive Rate** at different classification thresholds.

```
  TPR (Recall)
  1.0 │       ___________
      │    __/            \___
      │   /                   \__
  0.5 │  /    Perfect model:       \___
      │ /     AUC = 1.0               \
      │/      Random model:            \
  0.0 │       AUC = 0.5 (diagonal)     \
      └─────────────────────────────────
      0.0          0.5               1.0
                                   FPR (1 - Specificity)

  AUC interpretation:
  AUC = 1.0  → Perfect classifier
  AUC = 0.9  → Excellent
  AUC = 0.7  → Acceptable
  AUC = 0.5  → No better than random guessing
  AUC < 0.5  → Worse than random (model is inverted)
```

**When to use PR-AUC instead of ROC-AUC:** When the positive class is rare (< 5%). ROC-AUC is optimistic in this setting because TN dominates the FPR denominator.

### 6.4 Cross-Validation Strategies

Cross-validation gives a reliable estimate of generalization performance using all available data.

#### k-Fold Cross-Validation

```
  Dataset: [──────────────────────────────────────────]
  
  Fold 1:  [  VAL  ][─────────── TRAIN ──────────────]
  Fold 2:  [TRAIN] [  VAL  ][────────── TRAIN ────────]
  Fold 3:  [──TRAIN──] [  VAL  ][───────── TRAIN ──────]
  Fold 4:  [────TRAIN────] [  VAL  ][─────── TRAIN ────]
  Fold 5:  [──────────── TRAIN ──────────────][  VAL  ]
  
  Final score = mean(score_fold1, ..., score_fold5)
  Variance   = std(score_fold1, ..., score_fold5)

  k=5 or k=10 are standard choices.
  k=n (Leave-One-Out) is expensive but useful for tiny datasets.
```

#### Stratified k-Fold

For classification: ensures each fold has the same class distribution as the full dataset. Always use this for imbalanced datasets.

```python
from sklearn.model_selection import StratifiedKFold

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
    X_train, X_val = X[train_idx], X[val_idx]
    y_train, y_val = y[train_idx], y[val_idx]
    # ... fit and evaluate
```

#### Time-Series Cross-Validation (Walk-Forward)

For sequential data, you **cannot** randomly shuffle — future data cannot inform past predictions.

```
  Fold 1:  [TRAIN────────][VAL]
  Fold 2:  [TRAIN─────────────][VAL]
  Fold 3:  [TRAIN──────────────────][VAL]
  Fold 4:  [TRAIN───────────────────────][VAL]
  
  Always: training data is BEFORE validation data in time.
```

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)
for train_idx, val_idx in tscv.split(X):
    # time-respecting split
    pass
```

---

## 7. The No Free Lunch Theorem

### Statement

The No Free Lunch (NFL) theorem (Wolpert & Macready, 1997) states:

> *Averaged over all possible data-generating distributions, every learning algorithm has the same expected performance.*

In plain terms: **there is no universally best algorithm**. An algorithm that excels on one type of problem will be outperformed on another.

### What This Means for Practitioners

| Common Misunderstanding | Reality |
|------------------------|---------|
| "Deep learning always wins" | On small tabular data, gradient boosting routinely beats neural nets |
| "Random forests are safe defaults" | On sequential/image data, they are usually wrong tool choice |
| "XGBoost is best for tabular data" | Still depends heavily on the data distribution and size |

### Practical Implications

1. **Domain knowledge matters:** Choose algorithms informed by the structure of your data (sequential, spatial, relational).

2. **Always establish a baseline:** Even a trivial model (predict the mean, predict majority class) tells you the floor.

3. **Empirical comparison beats theoretical arguments:** Run experiments. The theorem is about averages over all possible problems; your problem is specific.

4. **Problem structure narrows the space:** Images → CNNs; sequences → RNNs/Transformers; tabular → gradient boosting or trees; graphs → GNNs. These are empirical heuristics, not theorems, but they are well-supported.

---

## 8. Feature Engineering Fundamentals

> *"Coming up with features is difficult, time-consuming, requires expert knowledge. Applied machine learning is basically feature engineering."* — Andrew Ng

### 8.1 Encoding Categorical Variables

| Method | When to Use | Code |
|--------|------------|------|
| **One-Hot Encoding** | Nominal, low cardinality (< ~20 categories) | `pd.get_dummies(df['color'])` |
| **Label Encoding** | Ordinal categories only | `LabelEncoder().fit_transform(y)` |
| **Target Encoding** | High cardinality, regression/binary classification | Replace each category with the mean target value (use cross-val to prevent leakage!) |
| **Frequency Encoding** | High cardinality, when frequency is informative | Replace each category with its count |
| **Embedding** | Very high cardinality (zip codes, user IDs) | Learned by neural net |

**Warning:** Never use label encoding for nominal features in linear models — it implies an ordering that does not exist.

### 8.2 Scaling

Tree-based models (random forest, gradient boosting, decision trees) are **scale-invariant**. Distance-based and gradient-based models (KNN, SVM, neural nets, linear/logistic regression) **require scaling**.

| Scaler | Formula | When |
|--------|---------|------|
| **StandardScaler** | (x − μ) / σ | Gaussian-like data; SVM, PCA, linear models |
| **MinMaxScaler** | (x − min) / (max − min) | Bounded features; neural nets |
| **RobustScaler** | (x − median) / IQR | Data with outliers |
| **Log transform** | log(1 + x) | Right-skewed distributions (income, counts) |

**Critical:** Fit the scaler **only** on training data, then transform both train and test. Fitting on the full dataset leaks test distribution into training.

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)  # fit + transform train
X_test_scaled  = scaler.transform(X_test)        # transform only (no fit!)
```

### 8.3 Handling Missing Values

First, understand **why** values are missing:

```
MCAR (Missing Completely at Random):
  → Missingness is unrelated to any variable
  → Safe to drop rows or impute with mean/median

MAR (Missing at Random):
  → Missingness depends on observed variables
  → Impute using other features (KNN imputer, iterative imputer)

MNAR (Missing Not at Random):
  → Missingness depends on the missing value itself
  → Very hard to handle; may need domain knowledge
  → Example: high earners omit income, so "missing income" correlates with high income
```

| Method | When |
|--------|------|
| Drop rows | Data is abundant, MCAR, < 1% missing |
| Mean / median imputation | MCAR, non-skewed / skewed respectively |
| Mode imputation | Categorical variables |
| KNN imputation | MAR, moderate dataset |
| Iterative imputation | MAR, complex dependencies between features |
| Add "was_missing" indicator feature | MNAR, or when missingness is informative |

### 8.4 Feature Creation

Domain knowledge generates the best features. Common techniques:

```python
# Interaction features
df['price_per_sqft'] = df['price'] / df['sqft']

# Polynomial features (use carefully — explosion in feature count)
from sklearn.preprocessing import PolynomialFeatures
poly = PolynomialFeatures(degree=2, include_bias=False)
X_poly = poly.fit_transform(X)

# Date decomposition
df['hour']      = df['timestamp'].dt.hour
df['dayofweek'] = df['timestamp'].dt.dayofweek
df['is_weekend']= df['dayofweek'].isin([5, 6]).astype(int)
df['month']     = df['timestamp'].dt.month

# Aggregation features (window statistics)
df['rolling_7d_mean'] = df['sales'].rolling(window=7).mean()
df['lag_1']           = df['sales'].shift(1)
```

### 8.5 Feature Selection

Too many features cause overfitting, slow training, and make models harder to interpret.

| Method | Type | Pros / Cons |
|--------|------|-------------|
| Variance threshold | Filter | Fast; removes near-constant features |
| Correlation filter | Filter | Fast; misses non-linear relationships |
| Mutual information | Filter | Captures non-linear; slower |
| Recursive Feature Elimination (RFE) | Wrapper | Accurate; expensive |
| LASSO regularization | Embedded | Sets irrelevant feature weights to zero |
| Feature importance (tree models) | Embedded | Fast; biased toward high-cardinality |
| SHAP values | Post-hoc | Most reliable; model-agnostic |

---

## 9. Data Splitting and Data Leakage

### 9.1 The Three-Way Split

```
FULL DATASET
┌──────────────────────────────────────────────────────┐
│                                                      │
│  TRAINING SET (60–70%)  │  VAL (15–20%)  │TEST(15%)  │
│                         │                │           │
│  Model learns from this │ Hyperparam     │ Final,    │
│                         │ tuning,        │ unbiased  │
│                         │ model select.  │ evaluation│
└──────────────────────────────────────────────────────┘

RULES:
  - Split BEFORE any preprocessing
  - Test set is LOCKED until final evaluation
  - Never tune on the test set (even once)
  - Use cross-validation on train+val for better estimates
```

### 9.2 Data Leakage — The Silent Killer

Data leakage occurs when information from outside the training window (i.e., from the future or from the test set) contaminates the training process, causing optimistically biased evaluation metrics that do not generalize to production.

**Types of leakage:**

#### Type 1: Target Leakage

A feature is only available because the outcome happened. Example:

```
Predicting loan default:
  Feature: "number_of_late_payment_notices_sent"
  Problem: notices are sent AFTER the customer defaults
  Result:  model appears perfect in evaluation; useless in production
           (the feature doesn't exist at prediction time)
```

#### Type 2: Train-Test Contamination

```python
# WRONG — scaler fitted on full dataset (leaks test stats into train)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # includes test rows!
X_train, X_test = train_test_split(X_scaled)

# CORRECT
X_train, X_test, y_train, y_test = train_test_split(X, y)
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test  = scaler.transform(X_test)  # NO fit!
```

#### Type 3: Target Encoding Leakage

```python
# WRONG — target encoding fitted on full training fold
df['city_mean_price'] = df.groupby('city')['price'].transform('mean')
# The current row's price is included in its own city mean → leakage

# CORRECT — use out-of-fold target encoding
from category_encoders import TargetEncoder
encoder = TargetEncoder()
X_train['city_enc'] = encoder.fit_transform(X_train['city'], y_train)
X_test['city_enc']  = encoder.transform(X_test['city'])
```

#### Type 4: Time-Series Leakage

Using future data to predict the past. Always ensure your feature engineering window uses only data that was available at the time of prediction.

### 9.3 Using sklearn Pipelines to Prevent Leakage

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('model',  LogisticRegression())
])

# cross_val_score will fit the scaler only on the training fold
# in each split — no leakage possible
scores = cross_val_score(pipe, X, y, cv=5, scoring='roc_auc')
```

**Rule of thumb:** Put all preprocessing inside a pipeline. If it can't go in a pipeline, think carefully about where fitting happens.

---

## 10. Class Imbalance

Class imbalance is when one class is far more frequent than another. Common examples: fraud detection (0.1% fraud), medical diagnosis (1–5% disease), churn prediction (5–15% churn).

### Why It's a Problem

A naive model that predicts "Not Fraud" for all transactions achieves 99.9% accuracy on a dataset that is 0.1% fraud. This is useless. Accuracy is a misleading metric here.

### 10.1 Resampling Strategies

```
ORIGINAL:        [─────── Majority (90%) ────────][─ Minority (10%) ─]

OVERSAMPLING:    [─────── Majority ───────][─────── Minority ────────]
                 (copies or synthesizes minority samples)

UNDERSAMPLING:   [── Majority ──][─ Minority ─]
                 (removes majority samples — loses information)

COMBINATION:     Both — oversample minority, undersample majority
```

#### SMOTE (Synthetic Minority Oversampling Technique)

SMOTE generates **synthetic** minority samples by interpolating between existing ones.

```
  Minority point A: (1.0, 2.0)
  Minority point B: (2.0, 4.0)  ← one of A's k nearest neighbors
  
  Synthetic point: A + rand(0,1) * (B - A) = (1.5, 3.0)
  
  Result: new synthetic minority sample that is plausible but not a copy
```

```python
from imblearn.over_sampling import SMOTE

sm = SMOTE(random_state=42)
X_resampled, y_resampled = sm.fit_resample(X_train, y_train)
# Note: apply ONLY to training data, never to test data
```

**SMOTE variants:**
- **ADASYN:** generates more samples in harder-to-learn regions
- **Borderline-SMOTE:** focuses on minority samples near the decision boundary
- **SMOTE-Tomek:** SMOTE + Tomek link removal (combined approach)

### 10.2 Class Weights

Instead of resampling, penalize misclassification of the minority class more heavily during training.

```python
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

# Automatically compute balanced weights
lr = LogisticRegression(class_weight='balanced')
rf = RandomForestClassifier(class_weight='balanced')

# Or manually specify
weights = {0: 1, 1: 10}  # misclassifying class 1 costs 10x more
lr = LogisticRegression(class_weight=weights)
```

Most sklearn classifiers accept `class_weight`. XGBoost uses `scale_pos_weight`:

```python
import xgboost as xgb

ratio = (y == 0).sum() / (y == 1).sum()
model = xgb.XGBClassifier(scale_pos_weight=ratio)
```

### 10.3 Threshold Tuning

By default, classifiers use a 0.5 probability threshold to assign a class. On imbalanced data, the optimal threshold is almost never 0.5.

```python
from sklearn.metrics import precision_recall_curve
import numpy as np

y_probs = model.predict_proba(X_val)[:, 1]
precision, recall, thresholds = precision_recall_curve(y_val, y_probs)

# Find threshold maximizing F1
f1_scores = 2 * precision * recall / (precision + recall + 1e-9)
best_threshold = thresholds[np.argmax(f1_scores)]

# Apply custom threshold
y_pred = (y_probs >= best_threshold).astype(int)
```

### 10.4 Use the Right Metric

| Metric | Good For Imbalance? |
|--------|-------------------|
| Accuracy | No — dominated by majority class |
| Precision | Partially — ignores FN |
| Recall | Partially — ignores FP |
| F1 | Yes — balances P and R |
| F-beta (β>1) | Yes — emphasizes recall |
| ROC-AUC | OK — can be optimistic |
| PR-AUC | Yes — best for severe imbalance |
| Matthews Correlation Coefficient (MCC) | Yes — robust, single score |

---

## 11. Case Study: End-to-End ML Problem

### Problem: Predicting Employee Attrition

**Business context:** HR wants to identify employees at high risk of leaving so managers can intervene proactively.

#### Step 1: Problem Framing

- **Task type:** Binary classification (leave / stay)
- **Label:** `attrition` (0 = stayed, 1 = left)
- **Prediction horizon:** 6 months
- **Key constraint:** FN is costly (missing a high-risk employee means no intervention); some FP is acceptable
- **Metric:** F2 score (recall-weighted F-beta), PR-AUC

#### Step 2: EDA

```python
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv('hr_data.csv')

print(df['attrition'].value_counts(normalize=True))
# attrition
# 0    0.839  ← 84% stay (imbalanced)
# 1    0.161  ← 16% leave

# Check distributions of numeric features
df.hist(figsize=(16, 12), bins=20)

# Correlation heatmap
sns.heatmap(df.corr(), cmap='coolwarm', center=0)

# Attrition rate by department
df.groupby('department')['attrition'].mean().sort_values().plot(kind='barh')
```

Key findings from EDA:
- Employees in Sales have 2x higher attrition rate
- Overtime workers have 3x higher attrition
- Employees with < 2 years at the company have higher attrition
- Job satisfaction score is strongly negatively correlated with attrition

#### Step 3: Feature Engineering

```python
# Encode categoricals
df = pd.get_dummies(df, columns=['department', 'job_role', 'marital_status'],
                    drop_first=True)

# Binary encode yes/no
df['overtime'] = (df['overtime'] == 'Yes').astype(int)

# Create interaction feature
df['satisfaction_tenure_ratio'] = df['job_satisfaction'] / (df['years_at_company'] + 1)

# Flag new employees
df['is_new_employee'] = (df['years_at_company'] < 2).astype(int)
```

#### Step 4: Data Splitting

```python
from sklearn.model_selection import train_test_split

X = df.drop('attrition', axis=1)
y = df['attrition']

# Stratify to maintain class ratio in each split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
```

#### Step 5: Model Training with Pipeline

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

pipe = ImbPipeline([
    ('smote',  SMOTE(random_state=42)),
    ('scaler', StandardScaler()),
    ('model',  GradientBoostingClassifier(
                    n_estimators=200,
                    max_depth=4,
                    learning_rate=0.05,
                    random_state=42))
])

pipe.fit(X_train, y_train)
```

#### Step 6: Evaluation

```python
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score

y_pred  = pipe.predict(X_test)
y_probs = pipe.predict_proba(X_test)[:, 1]

print(classification_report(y_test, y_pred))
print(f"ROC-AUC: {roc_auc_score(y_test, y_probs):.3f}")
print(f"PR-AUC:  {average_precision_score(y_test, y_probs):.3f}")
```

**Results:**

| Metric | Value |
|--------|-------|
| Precision (attrition) | 0.71 |
| Recall (attrition) | 0.83 |
| F1 (attrition) | 0.77 |
| ROC-AUC | 0.89 |
| PR-AUC | 0.76 |

#### Step 7: Feature Importance & Interpretation

```python
import shap

explainer = shap.TreeExplainer(pipe['model'])
shap_values = explainer.shap_values(X_test_scaled)

# Summary plot shows most important features
shap.summary_plot(shap_values, X_test, feature_names=X.columns)
```

**Top features:** overtime, satisfaction_tenure_ratio, job_satisfaction, monthly_income, is_new_employee

#### Step 8: Deployment Considerations

- Retrain monthly with new data (employee records change)
- Monitor for concept drift: attrition drivers change over time (e.g., during a recession vs. a boom market)
- Threshold: lower from 0.5 to 0.35 to capture more at-risk employees (recall emphasis)
- Output a risk score (probability), not just a binary flag, so managers can prioritize

---

## 12. Quiz: 15 Questions with Solutions

### Questions

**1.** You have a model with 98% accuracy on a binary classification problem. Is this a good model?

**2.** What is the difference between precision and recall? When would you prioritize each?

**3.** Your training accuracy is 97% and validation accuracy is 63%. What is likely happening, and how do you fix it?

**4.** Explain L1 vs. L2 regularization. Which one performs feature selection and why?

**5.** What is data leakage? Give one concrete example.

**6.** You are building a fraud detection model. The dataset is 0.5% fraud. Which evaluation metric is most appropriate and why?

**7.** What is the bias-variance tradeoff? How does increasing model complexity affect each?

**8.** Why should you never fit your scaler on the test set?

**9.** What is stratified k-fold cross-validation, and when is it necessary?

**10.** Explain the No Free Lunch theorem in your own words. What does it mean practically?

**11.** What is SMOTE? What is it doing at a geometric level?

**12.** What is the difference between supervised and self-supervised learning?

**13.** When would you use t-SNE vs. PCA?

**14.** Your model performs well in cross-validation but poorly in production. List three possible causes.

**15.** What is early stopping, and why does it help prevent overfitting?

---

### Solutions

**1.** Not necessarily. If 98% of the data belongs to one class (e.g., "not fraud"), a model that always predicts the majority class achieves 98% accuracy while being completely useless. Always check class distribution and use appropriate metrics like F1, PR-AUC, or MCC.

**2.** Precision = TP/(TP+FP): of all the positives I predicted, how many were real? Recall = TP/(TP+FN): of all actual positives, how many did I find? Prioritize precision when false positives are costly (spam filter — losing real emails is bad). Prioritize recall when false negatives are costly (cancer screening — missing a case is catastrophic).

**3.** The model is overfitting. The gap between train and validation accuracy is too large. Remedies: add regularization (L1/L2/dropout), reduce model complexity, gather more training data, use data augmentation, apply early stopping.

**4.** L1 adds `λ * Σ|wᵢ|` to the loss; L2 adds `λ * Σwᵢ²`. L1 performs feature selection because its gradient is constant in magnitude — it drives small weights to exactly zero. L2's gradient is proportional to the weight itself, so it shrinks weights toward zero but never exactly to zero.

**5.** Data leakage is when information that would not be available at prediction time is used during training, causing unrealistically good evaluation results. Example: using "account_closed_date" as a feature to predict account closure — the date only exists after the closure happens.

**6.** PR-AUC (Precision-Recall Area Under the Curve). When the positive class is very rare, ROC-AUC can be misleadingly high because TN dominates the denominator of FPR. PR-AUC focuses on the performance on the minority (positive) class.

**7.** Bias is error from wrong assumptions (underfitting); variance is sensitivity to training data (overfitting). Increasing model complexity decreases bias but increases variance. The goal is to find the sweet spot where total error (bias² + variance) is minimized.

**8.** The scaler learns statistics (mean, std) from the data it is fitted on. If you fit on the test set, those statistics "leak" into your model — the model has indirectly "seen" the test distribution during training. This gives optimistically biased evaluation metrics.

**9.** Stratified k-fold ensures each fold maintains the same class proportion as the full dataset. It is necessary for imbalanced classification problems, where random splits could place all minority class examples in one fold, making that fold's results uninformative.

**10.** No algorithm is universally best across all possible problems. When averaged over all possible data distributions, all algorithms perform equally. In practice, this means: do not assume any single algorithm will win — use domain knowledge to narrow choices, establish baselines, and run experiments.

**11.** SMOTE (Synthetic Minority Oversampling Technique) creates new synthetic minority-class examples by interpolating between existing ones. Geometrically: pick a minority point, find its k nearest minority neighbors, and place a new point at a random position along the line segment connecting the original point to one of those neighbors.

**12.** Supervised learning uses human-labeled examples (input→label pairs). Self-supervised learning creates its own labels from the raw data structure — for example, masking a word and predicting it (BERT), or predicting the next word (GPT). Self-supervised learning scales to unlabeled data, enabling large-scale pretraining.

**13.** Use t-SNE for visualization of high-dimensional data (especially to visually inspect cluster structure). Use PCA when you need a linear, interpretable reduction, or as a preprocessing step to reduce dimensionality before downstream models. t-SNE is non-deterministic, does not preserve global structure, and cannot be applied to new data without re-running. PCA is deterministic, preserves global variance, and can transform new data with `transform()`.

**14.** Possible causes: (a) Data distribution shift — production data has different characteristics than training data. (b) Data leakage — evaluation was optimistically biased. (c) Concept drift — the relationship between features and target has changed over time. (d) Feature unavailability — a feature used in training is not available in production. (e) Labeling inconsistency — training labels were generated differently than production outcomes.

**15.** Early stopping monitors the validation loss during training and halts training when the validation loss stops improving (or starts worsening). It prevents overfitting by not letting the model continue learning noise from the training set after it has extracted the true signal. A model checkpoint is saved at the epoch with the best validation performance.

---

## 13. References and Learning Resources

### Free Resources

| Resource | Type | Scope |
|----------|------|-------|
| **CS229 Stanford** (cs229.stanford.edu) | Course notes + lectures | Rigorous mathematical foundations; supervised, unsupervised, RL |
| **fast.ai** (fast.ai) | Interactive course | Top-down practical approach; deep learning with PyTorch |
| **The Hundred-Page ML Book** — Andriy Burkov (themlbook.com) | Book (free summary on website) | Dense, complete survey; excellent for review and breadth |
| **Google ML Crash Course** (developers.google.com/machine-learning) | Interactive course | Practical intro; TensorFlow examples |
| **An Introduction to Statistical Learning** (statlearning.com) | Textbook (free PDF) | Rigorous coverage of classical ML with R examples |
| **Made With ML** (madewithml.com) | Online guide | MLOps-focused; production-ready practices |
| **Scikit-learn User Guide** (scikit-learn.org/stable/user_guide) | Documentation | Best API reference for classical ML |

### Paid Resources

| Resource | Platform | Best For |
|----------|---------|---------|
| **Machine Learning Specialization** — Andrew Ng | Coursera | Structured curriculum with assignments; excellent for beginners |
| **Deep Learning Specialization** — Andrew Ng | Coursera | Neural networks, CNNs, RNNs, transformers |
| **Hands-On Machine Learning with Scikit-Learn, Keras and TensorFlow** — Aurélien Géron | Book (O'Reilly) | Best single-volume practical reference; highly recommended |
| **Machine Learning A-Z** | Udemy | Project-based; Python and R; broad coverage |
| **Practical Deep Learning for Coders** — fast.ai (paid tiers) | fast.ai | Cutting-edge techniques taught bottom-up |

### Key Papers to Read

| Paper | Why |
|-------|-----|
| *A Few Useful Things to Know About Machine Learning* — Domingos (2012) | Broad practitioner wisdom in one paper |
| *No Free Lunch Theorems for Optimization* — Wolpert & Macready (1997) | Foundational theory |
| *Random Forests* — Breiman (2001) | Classic ensemble method |
| *XGBoost: A Scalable Tree Boosting System* — Chen & Guestrin (2016) | Most-used tabular ML method |
| *Attention Is All You Need* — Vaswani et al. (2017) | Transformer architecture |

---

## Quick Reference Cheat Sheet

```
┌─────────────────────────────────────────────────────────────────┐
│                    ML QUICK REFERENCE                           │
├─────────────────────────────────────────────────────────────────┤
│ CHOOSING AN ALGORITHM                                           │
│  Tabular, < 100k rows → Gradient Boosting (XGBoost/LightGBM)   │
│  Tabular, > 1M rows   → LightGBM or deep tabular models        │
│  Images               → CNN or Vision Transformer               │
│  Text                 → Transformer (BERT, GPT fine-tune)       │
│  Time Series          → LSTM, Temporal Fusion Transformer, ARIMA│
│  Graphs               → GNN                                     │
├─────────────────────────────────────────────────────────────────┤
│ DIAGNOSING YOUR MODEL                                           │
│  High train acc, low val acc  → Overfitting → regularize        │
│  Low train acc, low val acc   → Underfitting → more complexity  │
│  High val acc, low prod acc   → Leakage or distribution shift   │
│  Good metrics, bad business   → Wrong metric or wrong problem   │
├─────────────────────────────────────────────────────────────────┤
│ METRIC SELECTION                                                │
│  Balanced classes, accuracy ok  → Accuracy                      │
│  Imbalanced, FP costly          → Precision, ROC-AUC            │
│  Imbalanced, FN costly          → Recall, F2                    │
│  Severely imbalanced (< 5%)     → PR-AUC, MCC                   │
│  Regression                     → RMSE (normal errors)          │
│                                   MAE (robust to outliers)      │
├─────────────────────────────────────────────────────────────────┤
│ PREPROCESSING CHECKLIST                                         │
│  [ ] Split data FIRST, before any preprocessing                 │
│  [ ] Fit all transformers on train only                         │
│  [ ] Scale continuous features (except trees)                   │
│  [ ] Encode categoricals (OHE or target encode)                 │
│  [ ] Handle missing values (understand MCAR/MAR/MNAR)           │
│  [ ] Check for target leakage                                   │
│  [ ] Use stratified splits for classification                   │
│  [ ] Use time-respecting splits for time-series                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Next in this series:* `02-neural-networks-fundamentals.md` — Perceptrons, backpropagation, activation functions, optimizers, batch normalization, and building your first neural network from scratch.
