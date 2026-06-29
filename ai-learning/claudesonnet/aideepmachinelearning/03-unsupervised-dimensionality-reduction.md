# Unsupervised Learning, Dimensionality Reduction & Anomaly Detection

> **Series:** AI / Deep Machine Learning — Module 03
> **Prerequisites:** Module 01 (ML Foundations), Module 02 (Supervised Learning)
> **Difficulty:** Intermediate → Advanced
> **Estimated Reading Time:** 60–90 minutes

---

## Table of Contents

1. [Introduction — The Unsupervised Paradigm](#1-introduction)
2. [Clustering Algorithms](#2-clustering)
   - 2.1 K-Means
   - 2.2 Hierarchical Clustering
   - 2.3 DBSCAN
   - 2.4 Gaussian Mixture Models (GMM)
   - 2.5 HDBSCAN
3. [Dimensionality Reduction](#3-dimensionality-reduction)
   - 3.1 Principal Component Analysis (PCA)
   - 3.2 t-SNE
   - 3.3 UMAP
   - 3.4 Linear Discriminant Analysis (LDA)
   - 3.5 Autoencoders
4. [Anomaly Detection](#4-anomaly-detection)
   - 4.1 Statistical Methods (Z-score, IQR)
   - 4.2 Isolation Forest
   - 4.3 One-Class SVM
   - 4.4 Autoencoders for Anomaly Detection
5. [Applications](#5-applications)
6. [Quiz — 10 Questions with Solutions](#6-quiz)
7. [Project — Customer Segmentation with RFM Analysis](#7-project)
8. [References](#8-references)

---

## 1. Introduction — The Unsupervised Paradigm

In supervised learning, every training example carries a label. A human expert has already decided "this email is spam", "this image is a cat". Unsupervised learning removes that crutch entirely. The algorithm receives raw data **X** and must discover latent structure on its own.

Why does this matter in practice?

- **Labeling is expensive.** A single ImageNet annotation round cost millions of dollars. Unlabelled data is abundant and nearly free.
- **Structure precedes labels.** Before you can classify customers you must understand how many meaningfully distinct groups even exist.
- **Compression and representation.** Real-world data lives in high-dimensional spaces (thousands of pixels, genes, word dimensions). Reducing to a lower-dimensional representation improves downstream model accuracy, memory, and interpretability.
- **Anomaly detection.** Fraud, equipment failure, and network intrusion are rare. Training a supervised classifier requires thousands of fraud examples. Unsupervised approaches learn "normal" and flag deviations.

The three pillars of this module are therefore:

| Pillar | Core Question | Example Algorithms |
|---|---|---|
| **Clustering** | Which examples naturally group together? | K-Means, DBSCAN, GMM, HDBSCAN |
| **Dimensionality Reduction** | What is the fewest dimensions that preserve information? | PCA, t-SNE, UMAP, Autoencoders |
| **Anomaly Detection** | Which examples are unlike the rest? | Isolation Forest, One-Class SVM |

---

## 2. Clustering Algorithms

Clustering partitions a dataset **X = {x₁, x₂, …, xₙ}** into groups (clusters) such that intra-cluster similarity is high and inter-cluster similarity is low. There is no universal definition of "cluster" — different algorithms formalise it differently, which is why you need multiple tools.

---

### 2.1 K-Means Clustering

#### The Objective

K-Means minimises the **Within-Cluster Sum of Squares (WCSS)**, also called inertia:

```
Minimise:  J = Σᵢ Σ_{x ∈ Cᵢ}  ||x − μᵢ||²

where μᵢ is the centroid of cluster Cᵢ
```

#### The Lloyd's Algorithm (Standard K-Means)

```
Algorithm: K-Means (Lloyd's)
─────────────────────────────────────────────────────────
Input : X (n × d matrix), K (number of clusters)
Output: centroids μ₁…μ_K, assignments z₁…zₙ

1. INITIALISE  μ₁…μ_K  (random sample, or K-Means++)
2. REPEAT until convergence:
   a. ASSIGN  zᵢ ← argmin_k  ||xᵢ − μ_k||²   (for all i)
   b. UPDATE  μ_k ← mean({xᵢ : zᵢ = k})         (for all k)
3. RETURN μ, z
─────────────────────────────────────────────────────────
```

#### ASCII Art — K-Means Iteration Steps

```
ITERATION 0 — Random initialization
  · · · ✦ · ·       ✦ = centroid
· · ✦ · · ·
    · ·   · · · ✦

ITERATION 1 — Assign each point to nearest centroid
  A A A ✦ B B
A A ✦ A B B
    A A   B B B ✦

ITERATION 2 — Recompute centroids (✦ shifts to true mean)
  A A A ✦ B B
A A   A   B B
    A A ✦ B B B

ITERATION 3 — Stable assignment, centroids converged
  A A A ✦ B B
A A   A   B B
    A A ✦ B B B
         (no change → STOP)
```

#### K-Means++ Initialisation

Naive random initialisation often leads to poor local minima. K-Means++ selects centroids with probability proportional to distance squared from the nearest already-chosen centroid, guaranteeing an O(log K) approximation ratio.

#### The Elbow Method — Choosing K

```python
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.datasets import make_blobs

X, _ = make_blobs(n_samples=500, centers=4, random_state=42)

inertias = []
K_range = range(1, 11)

for k in K_range:
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    km.fit(X)
    inertias.append(km.inertia_)

plt.figure(figsize=(8, 4))
plt.plot(K_range, inertias, marker='o', linewidth=2)
plt.xlabel('K (number of clusters)')
plt.ylabel('Inertia (WCSS)')
plt.title('Elbow Method — Optimal K at the "elbow"')
plt.xticks(K_range)
plt.grid(alpha=0.3)
plt.show()
```

```
Elbow Plot (schematic)
 Inertia
  |
8000 ┤ ●
  |   \
6000 ┤    ●
  |      \
4000 ┤       ●
  |         \
2000 ┤          ● ─ ─ ● ─ ─ ● ─ ─ ●
  |
  └──┬──┬──┬──┬──┬──┬──┬──┬──┬──── K
     1  2  3  4  5  6  7  8  9  10
                ^
               elbow at K=4  ← optimal K
```

**Silhouette score** provides a complementary metric:

```
s(i) = (b(i) − a(i)) / max(a(i), b(i))

a(i) = mean intra-cluster distance for point i
b(i) = mean distance to nearest other cluster
s(i) ∈ [−1, 1]; higher is better
```

#### Limitations

- Assumes **spherical** clusters of **equal size**.
- Sensitive to outliers (squared distance amplifies them).
- Must specify K in advance.
- Non-convex clusters confuse it (use DBSCAN or GMM instead).

---

### 2.2 Hierarchical Clustering

Hierarchical clustering builds a **tree (dendrogram)** of nested clusters without requiring K upfront. It comes in two flavours:

| Type | Direction | Complexity |
|---|---|---|
| **Agglomerative** (bottom-up) | Start: n singleton clusters, merge greedily | O(n² log n) |
| **Divisive** (top-down) | Start: 1 cluster, split recursively | O(2ⁿ) — rarely used |

#### Linkage Methods

The algorithm must decide how to measure distance between two **sets** of points:

| Linkage | Formula | Behaviour |
|---|---|---|
| **Single** | min distance between any pair | Chaining — elongated clusters |
| **Complete** | max distance between any pair | Compact, roughly equal clusters |
| **Average (UPGMA)** | mean of all pairwise distances | Balanced |
| **Ward** | minimise increase in WCSS on merge | Best for compact spherical clusters |

#### ASCII Art — Dendrogram

```
Dendrogram (5 observations)
Height
  │
5 ┤                    ╔════════╗
  │                    ║        ║
4 ┤          ╔═════════╝        ╚═══╗
  │          ║                     ║
3 ┤   ╔══════╝                     ║
  │   ║                            ║
2 ┤ ╔═╝                            ║
  │ ║                              ║
1 ┤ ║       ╔════╗                 ║
  │ ║       ║    ║                 ║
  └─╫───────╫────╫─────────────────╫──
    A       B    C                 D E

Cut at height 3 → 2 clusters: {A,B,C} and {D,E}
Cut at height 2 → 3 clusters: {A,B}, {C}, {D,E}
```

```python
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.preprocessing import StandardScaler

X_scaled = StandardScaler().fit_transform(X)
Z = linkage(X_scaled, method='ward')

plt.figure(figsize=(10, 5))
dendrogram(Z, truncate_mode='level', p=5)
plt.title('Ward Linkage Dendrogram')
plt.xlabel('Sample index or (cluster size)')
plt.ylabel('Distance')
plt.show()
```

---

### 2.3 DBSCAN — Density-Based Spatial Clustering

DBSCAN (Density-Based Spatial Clustering of Applications with Noise) is fundamentally different: it defines clusters as **dense regions** separated by sparse regions. It can find arbitrarily shaped clusters and explicitly labels **noise points** (outliers).

#### Core Concepts

| Term | Definition |
|---|---|
| **ε (epsilon)** | Neighbourhood radius |
| **MinPts** | Minimum points to form a dense region |
| **Core point** | Has ≥ MinPts points within ε |
| **Border point** | Within ε of a core point, but < MinPts neighbours |
| **Noise point** | Neither core nor border |

#### Algorithm

```
DBSCAN(X, ε, MinPts)
────────────────────────────────────────
For each unvisited point p in X:
  Mark p as visited
  N ← neighbourhood(p, ε)
  If |N| < MinPts:
    Label p as NOISE
  Else:
    Create new cluster C
    ExpandCluster(p, N, C, ε, MinPts)
────────────────────────────────────────
ExpandCluster(p, N, C, ε, MinPts)
  Add p to C
  For each q in N:
    If q is not visited:
      Mark q as visited
      N' ← neighbourhood(q, ε)
      If |N'| ≥ MinPts: N ← N ∪ N'
    If q is not a member of any cluster: add q to C
```

**Time complexity:** O(n log n) with spatial indexing (k-d tree or ball tree), O(n²) naively.

```python
from sklearn.cluster import DBSCAN
from sklearn.datasets import make_moons

X_moons, _ = make_moons(n_samples=300, noise=0.05, random_state=42)
db = DBSCAN(eps=0.2, min_samples=5)
labels = db.fit_predict(X_moons)
# labels == -1 indicates noise
n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise = list(labels).count(-1)
print(f"Clusters: {n_clusters}, Noise points: {n_noise}")
```

**Choosing ε:** Plot the k-nearest-neighbour distance (sorted) and look for a "knee". Good ε is where the curve bends sharply.

---

### 2.4 Gaussian Mixture Models (GMM)

GMM is a **probabilistic generative model** that assumes the data is drawn from a mixture of K Gaussian distributions. Unlike K-Means (hard assignment), GMM performs **soft clustering** — each point has a probability of belonging to each cluster.

#### The Model

```
p(x) = Σ_{k=1}^{K}  πₖ · N(x | μₖ, Σₖ)

πₖ = mixing coefficient  (Σ πₖ = 1)
μₖ = mean of component k
Σₖ = covariance matrix of component k
```

#### Expectation-Maximisation (EM) Algorithm

```
EM for GMM
──────────────────────────────────────────────────────
Initialise: μₖ, Σₖ, πₖ  (e.g. from K-Means)

REPEAT until log-likelihood converges:

  E-STEP (soft assignment):
    rᵢₖ = πₖ·N(xᵢ|μₖ,Σₖ) / Σⱼ πⱼ·N(xᵢ|μⱼ,Σⱼ)
    (rᵢₖ is the "responsibility" of cluster k for xᵢ)

  M-STEP (update parameters):
    Nₖ  = Σᵢ rᵢₖ
    μₖ  = (1/Nₖ) Σᵢ rᵢₖ xᵢ
    Σₖ  = (1/Nₖ) Σᵢ rᵢₖ (xᵢ−μₖ)(xᵢ−μₖ)ᵀ
    πₖ  = Nₖ / n
──────────────────────────────────────────────────────
```

EM is guaranteed to increase the log-likelihood at every iteration, converging to a local maximum.

**Model selection** — use BIC (Bayesian Information Criterion) to choose K:

```
BIC = −2 · log L̂ + p · log(n)
p = number of free parameters
```

Lower BIC is better. It penalises complexity, preventing overfitting.

```python
from sklearn.mixture import GaussianMixture

bic_scores = []
for k in range(1, 9):
    gmm = GaussianMixture(n_components=k, covariance_type='full',
                          random_state=42)
    gmm.fit(X_scaled)
    bic_scores.append(gmm.bic(X_scaled))

optimal_k = np.argmin(bic_scores) + 1
print(f"Optimal components by BIC: {optimal_k}")
```

---

### 2.5 HDBSCAN — Hierarchical DBSCAN

HDBSCAN extends DBSCAN by building a full **cluster hierarchy** and then extracting the most persistent (stable) clusters. Key advantages:

- Works with **varying density** clusters (DBSCAN's biggest weakness).
- Produces a **soft clustering** variant.
- Requires only one meaningful parameter: `min_cluster_size`.
- Returns an **outlier score** (GLOSH) for every point.

```python
import hdbscan

clusterer = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=5)
labels = clusterer.fit_predict(X_scaled)
outlier_scores = clusterer.outlier_scores_
```

The algorithm internally builds a **minimum spanning tree** over a mutual reachability graph, then extracts the condensed cluster tree and selects clusters by maximum stability.

---

## 3. Dimensionality Reduction

High-dimensional data suffers from the **curse of dimensionality**: data becomes sparse, distances become meaningless, and visualisation is impossible beyond 3D. Dimensionality reduction transforms **X ∈ ℝⁿˣᵈ → Z ∈ ℝⁿˣᵏ** where k ≪ d.

---

### 3.1 Principal Component Analysis (PCA)

PCA is the workhorse of dimensionality reduction. It finds the **orthogonal directions of maximum variance** in the data.

#### Mathematical Derivation

**Step 1 — Centre the data:**
```
X̃ᵢ = Xᵢ − x̄     (subtract column means)
```

**Step 2 — Compute the covariance matrix:**
```
C = (1/(n−1)) · X̃ᵀ X̃     ∈ ℝ^{d×d}
```

**Step 3 — Eigendecomposition:**
```
C = V Λ Vᵀ

V = matrix of eigenvectors (principal components)
Λ = diagonal matrix of eigenvalues λ₁ ≥ λ₂ ≥ … ≥ λ_d
```

**Step 4 — Project onto top-k eigenvectors:**
```
Z = X̃ · V_k     where V_k contains the first k columns of V
```

Each principal component (PC) is a linear combination of original features. The first PC captures the most variance; subsequent PCs capture decreasing amounts and are orthogonal to all previous ones.

**Equivalently**, PCA can be computed via **Singular Value Decomposition (SVD)**:
```
X̃ = U Σ Vᵀ
PCs are the right singular vectors (columns of V)
```

SVD is numerically more stable for high-dimensional data.

#### ASCII Art — PCA Projection

```
Original 2D data          After PCA projection to 1D
(high correlation)        (PC1 axis)

    ·  ·                        ← PC2 (discarded, low variance)
  ·  ·   ·                    │
·   ·   ·   ·            ─────┼──────────────────── PC1
  ·   ·   ·                   │
    ·   ·                     ↓
      ·                 projected points on PC1:
                         · · ·  · · · · · ·  · ·

PC1 direction: ↗ (diagonal, captures correlation)
PC2 direction: ↖ (perpendicular, captures residual)
```

#### Explained Variance and Scree Plot

```python
from sklearn.decomposition import PCA
from sklearn.datasets import load_digits

digits = load_digits()
X_digits = digits.data  # 1797 × 64

pca = PCA(n_components=64)
pca.fit(X_digits)

explained_var = pca.explained_variance_ratio_
cumulative_var = np.cumsum(explained_var)

# Scree plot
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].bar(range(1, 21), explained_var[:20], alpha=0.8, color='steelblue')
axes[0].set_xlabel('Principal Component')
axes[0].set_ylabel('Explained Variance Ratio')
axes[0].set_title('Scree Plot')

axes[1].plot(range(1, 65), cumulative_var, linewidth=2, color='coral')
axes[1].axhline(y=0.95, color='gray', linestyle='--', label='95% threshold')
axes[1].set_xlabel('Number of Components')
axes[1].set_ylabel('Cumulative Explained Variance')
axes[1].set_title('Cumulative Explained Variance')
axes[1].legend()
plt.tight_layout()
plt.show()

# How many components for 95% variance?
n_95 = np.argmax(cumulative_var >= 0.95) + 1
print(f"Components needed for 95% variance: {n_95}")  # typically ~29 for digits
```

```
Scree Plot (schematic)
Explained
Variance
  │
30%┤ █
  │ █
20%┤ █ █
  │ █ █
10%┤ █ █ █
  │ █ █ █ █ █
 5%┤ █ █ █ █ █ █ ▄ ▄ ▄ ▄ ─ ─ ─ ─
  └──┬──┬──┬──┬──┬──┬──┬──┬──┬──
     1  2  3  4  5  6  7  8  9  10  PC
```

#### Key Properties

- **Linear** method — cannot capture non-linear manifolds.
- **Orthogonal** components — decorrelates features (useful for downstream linear models).
- **Reversible** (lossy reconstruction): `X̃_reconstructed = Z · V_kᵀ`
- **Whitening** option: divide by √λ to give components unit variance.

---

### 3.2 t-SNE — t-Distributed Stochastic Neighbour Embedding

t-SNE (van der Maaten & Hinton, 2008) is a **non-linear** dimensionality reduction technique specialised for **visualisation** (2D or 3D output).

#### Core Idea

1. In high-D space, model pairwise similarity as conditional probabilities using a **Gaussian kernel**:
```
pⱼ|ᵢ = exp(−||xᵢ−xⱼ||² / 2σᵢ²) / Σ_{k≠i} exp(−||xᵢ−xₖ||² / 2σᵢ²)
pᵢⱼ = (pⱼ|ᵢ + pᵢ|ⱼ) / 2n
```

2. In low-D space, model pairwise similarity using a **Student-t distribution** (heavy tails):
```
qᵢⱼ = (1 + ||yᵢ−yⱼ||²)⁻¹ / Σ_{k≠l} (1 + ||yₖ−yₗ||²)⁻¹
```

3. Minimise KL divergence between P and Q via gradient descent:
```
C = KL(P||Q) = Σᵢ Σⱼ pᵢⱼ log(pᵢⱼ/qᵢⱼ)
```

The **heavy-tailed t-distribution** in low-D space alleviates the "crowding problem": points that are moderately distant in high-D get pushed far apart in 2D, producing well-separated clusters.

#### Perplexity

Perplexity controls the effective number of neighbours each point considers:
```
Perplexity = 2^{H(Pᵢ)}     where H is the Shannon entropy of Pᵢ
```
Typical values: **5–50**. Higher perplexity → more global structure preserved.

#### When to Use t-SNE

| Use t-SNE when | Avoid t-SNE when |
|---|---|
| Visualising cluster structure | You need preserved global distances |
| Exploring high-D embeddings | You need reproducibility (stochastic) |
| Input < 50D (run PCA first otherwise) | Dataset > ~50k points (slow, O(n²)) |
| Confirming clustering results | Axes have no interpretable meaning |

#### Critical Pitfalls

```
⚠ WARNING: t-SNE visualisation traps

1. Cluster SIZE in t-SNE plot is meaningless (not proportional to true density)
2. Cluster DISTANCE in t-SNE plot is meaningless
3. Different random seeds → different layouts (always set random_state)
4. Perplexity too low → fragmented clusters; too high → merged clusters
5. Running on raw pixels/text — always reduce with PCA to ~50D first
```

```python
from sklearn.manifold import TSNE

# Good practice: PCA to 50D first, then t-SNE
pca_50 = PCA(n_components=50, random_state=42)
X_50 = pca_50.fit_transform(X_digits)

tsne = TSNE(n_components=2, perplexity=30, n_iter=1000,
            learning_rate='auto', init='pca', random_state=42)
X_2d = tsne.fit_transform(X_50)
```

---

### 3.3 UMAP — Uniform Manifold Approximation and Projection

UMAP (McInnes et al., 2018) is the modern successor to t-SNE. It is faster, scales to larger datasets, and — crucially — **better preserves global structure**.

#### Theoretical Foundation

UMAP is grounded in **Riemannian geometry** and **algebraic topology**. It models the data manifold as a fuzzy simplicial set. The key idea:

1. Construct a **weighted k-nearest-neighbour graph** in high-D, with edge weights representing local connectivity.
2. Construct an analogous graph in low-D.
3. Optimise the low-D layout to match the high-D topology using **cross-entropy** loss (rather than KL divergence).

The low-D similarity uses a smooth approximation:
```
v(yᵢ, yⱼ) = (1 + a·||yᵢ−yⱼ||^{2b})⁻¹
```
where a, b are fitted to approximate a t-distribution. Parameters `min_dist` and `spread` control these.

#### UMAP vs t-SNE

| Property | t-SNE | UMAP |
|---|---|---|
| **Speed** | O(n² ) or O(n log n) with BH | O(n^{1.14}) — much faster |
| **Global structure** | Poorly preserved | Better preserved |
| **Scalability** | ~50k points practical limit | Millions of points feasible |
| **Reproducibility** | Stochastic, poor | Better, `random_state` effective |
| **Parameters** | `perplexity`, `learning_rate` | `n_neighbors`, `min_dist` |
| **Parametric extension** | No (non-parametric) | Yes (parametric UMAP) |

#### Key Parameters

| Parameter | Effect |
|---|---|
| `n_neighbors` (default 15) | Low = local structure; High = global structure |
| `min_dist` (default 0.1) | Low = tight clusters; High = spread out |
| `metric` | Distance function (euclidean, cosine, manhattan…) |
| `n_components` | Output dimensions (2 for visualisation, more for downstream ML) |

```python
import umap

reducer = umap.UMAP(n_neighbors=15, min_dist=0.1,
                    n_components=2, metric='euclidean',
                    random_state=42)
X_umap = reducer.fit_transform(X_digits)

# For downstream ML (not just visualisation), use higher n_components
reducer_50 = umap.UMAP(n_components=50, random_state=42)
X_umap_50 = reducer_50.fit_transform(X_digits)
```

**Inverse transform** — UMAP supports approximate reconstruction:
```python
X_reconstructed = reducer.inverse_transform(X_umap)
```

---

### 3.4 Linear Discriminant Analysis (LDA)

LDA is a **supervised** dimensionality reduction technique (unlike PCA/t-SNE/UMAP). It finds projections that **maximise class separability**.

```
Objective: maximise  J(w) = (wᵀ Sᴮ w) / (wᵀ Sᵂ w)

Sᴮ = between-class scatter matrix
Sᵂ = within-class scatter matrix
```

Solved via generalised eigenvalue problem: `Sᴮ w = λ Sᵂ w`.

Maximum number of discriminant directions = min(n_classes − 1, n_features).

LDA is particularly powerful when class labels are available and you want the best projection for classification, not just variance preservation.

---

### 3.5 Autoencoders — Neural Dimensionality Reduction

An **autoencoder** is a neural network trained to reconstruct its own input through a **bottleneck layer** (latent space). The encoder learns a compressed representation; the decoder learns to reconstruct.

```
Architecture:

Input x ∈ ℝᵈ
    │
  ┌─┴─────────────────────────────┐
  │  ENCODER                      │
  │  fc(d→256) → ReLU             │
  │  fc(256→128) → ReLU           │
  │  fc(128→k) → (linear/sigmoid) │
  └─────────────────┬─────────────┘
                    │  z ∈ ℝᵏ  (latent code, k ≪ d)
  ┌─────────────────┴─────────────┐
  │  DECODER                      │
  │  fc(k→128) → ReLU             │
  │  fc(128→256) → ReLU           │
  │  fc(256→d) → sigmoid/linear   │
  └─────────────┬─────────────────┘
               x̂ ∈ ℝᵈ  (reconstruction)

Loss: MSE(x, x̂) = ||x − x̂||²
```

```python
import torch
import torch.nn as nn

class Autoencoder(nn.Module):
    def __init__(self, input_dim, latent_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 256), nn.ReLU(),
            nn.Linear(256, 128),       nn.ReLU(),
            nn.Linear(128, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128), nn.ReLU(),
            nn.Linear(128, 256),        nn.ReLU(),
            nn.Linear(256, input_dim),  nn.Sigmoid()
        )

    def forward(self, x):
        z = self.encoder(x)
        x_hat = self.decoder(z)
        return x_hat, z

model = Autoencoder(input_dim=784, latent_dim=32)
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
```

**Variational Autoencoder (VAE)** extends this by making the latent space a **probability distribution** (Gaussian), enabling generative sampling and smoother interpolation.

---

## 4. Anomaly Detection

Anomaly detection identifies **rare, unusual observations** that deviate significantly from the expected pattern. Applications include fraud detection, network intrusion, manufacturing defects, and medical anomalies.

---

### 4.1 Statistical Methods — Z-Score and IQR

These are the simplest, most interpretable methods.

#### Z-Score (Assumes Gaussian Distribution)

```
z = (x − μ) / σ

Threshold: |z| > 3  →  anomaly  (flags ~0.3% of normal data)
```

```python
from scipy import stats

z_scores = np.abs(stats.zscore(X))
anomalies_zscore = (z_scores > 3).any(axis=1)
```

**Limitation:** Breaks down if the feature is not normally distributed, and masked outliers can distort μ and σ.

#### IQR Method (Robust, Distribution-Free)

```
IQR = Q3 − Q1
Lower fence = Q1 − 1.5 × IQR
Upper fence = Q3 + 1.5 × IQR

Points outside the fences are flagged as anomalies.
```

```python
Q1 = np.percentile(X, 25, axis=0)
Q3 = np.percentile(X, 75, axis=0)
IQR = Q3 - Q1

lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR

anomalies_iqr = ((X < lower) | (X > upper)).any(axis=1)
```

#### Mahalanobis Distance (Multivariate Generalisation)

```
D²(x) = (x − μ)ᵀ Σ⁻¹ (x − μ)

Follows chi-squared distribution with d degrees of freedom.
Threshold at chi2.ppf(0.975, df=d) for 2.5% contamination.
```

Mahalanobis accounts for **correlations** between features, unlike per-feature z-scores.

---

### 4.2 Isolation Forest

Isolation Forest (Liu et al., 2008) is based on a beautifully simple insight: **anomalies are few and different — they are easier to isolate**.

#### Algorithm

1. Build an ensemble of **isolation trees** (iTrees) by randomly selecting a feature and a random split value.
2. **Anomalies require fewer splits** to isolate than normal points.
3. The anomaly score is based on the **average path length** across all trees.

```
Anomaly Score:
  s(x, n) = 2^{−E[h(x)] / c(n)}

E[h(x)] = mean path length across trees
c(n) = average path length of an unsuccessful BST search (normalisation)
     = 2·H(n−1) − 2(n−1)/n

Score → 1:   anomaly  (short path → isolated quickly)
Score → 0.5: normal
Score → 0:   very normal (deep in the tree)
```

```
Isolation Tree (schematic)
         [Feature F3 < 2.1]
        /                  \
  [F1 < 0.5]         [F7 < 11.3]
   /      \            /      \
NORMAL   NORMAL  ANOMALY    NORMAL
(depth 3) (depth 4) (depth 2!) (depth 5)

Anomalies bubble up to the root faster.
```

```python
from sklearn.ensemble import IsolationForest

iso_forest = IsolationForest(
    n_estimators=100,
    contamination=0.05,  # expected fraction of anomalies
    random_state=42
)
predictions = iso_forest.fit_predict(X_scaled)
# predictions: 1 = normal, -1 = anomaly
anomaly_scores = iso_forest.decision_function(X_scaled)
```

**Advantages:** Fast (O(n log n)), works well in high dimensions, no distributional assumptions.

---

### 4.3 One-Class SVM

One-Class SVM learns a **decision boundary** around the normal data in a high-dimensional feature space (via the kernel trick). It is sensitive to hyperparameter tuning.

```
Objective (Schölkopf et al.):
  Minimise:  ½ ||w||² + (1/νn) Σᵢ ξᵢ − ρ
  Subject to: wᵀ φ(xᵢ) ≥ ρ − ξᵢ,  ξᵢ ≥ 0

ν ∈ (0,1): upper bound on fraction of anomalies (outliers)
φ: kernel-induced feature map (typically RBF)
```

```python
from sklearn.svm import OneClassSVM

oc_svm = OneClassSVM(kernel='rbf', gamma='scale', nu=0.05)
oc_svm.fit(X_train_normal)  # fit on normal data only
predictions = oc_svm.predict(X_test)
# 1 = normal, -1 = anomaly
```

**Use when:** Data is clean and well-characterised at training time; you have no anomaly examples at all.

---

### 4.4 Autoencoders for Anomaly Detection

A powerful **deep learning approach**: train an autoencoder **only on normal data**. At inference time, anomalies will have high **reconstruction error** because the autoencoder has never learned to reconstruct them.

```
Training:   Autoencoder learns to reconstruct normal patterns
Inference:  reconstruction_error(x) = ||x − decoder(encoder(x))||²
Threshold:  error > τ  →  anomaly
```

```python
class AnomalyAutoencoder(nn.Module):
    def __init__(self, input_dim, latent_dim=16):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64), nn.ReLU(),
            nn.Linear(64, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64), nn.ReLU(),
            nn.Linear(64, input_dim)
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))

# Train only on normal data
model = AnomalyAutoencoder(input_dim=30, latent_dim=8)
# ... training loop on X_normal ...

# Detect anomalies
with torch.no_grad():
    X_tensor = torch.FloatTensor(X_test)
    recon = model(X_tensor)
    recon_error = torch.mean((X_tensor - recon) ** 2, dim=1)
    anomalies = recon_error > recon_error.quantile(0.95)
```

**Key advantage over Isolation Forest / OCSVM:** Can capture **complex, non-linear patterns** in very high-dimensional data (images, time-series).

---

## 5. Applications

### 5.1 Customer Segmentation

Use clustering (K-Means or GMM) on behavioural features (RFM — see Project section) to identify distinct customer personas: champions, at-risk customers, hibernating customers. Each segment receives tailored marketing.

### 5.2 Topic Modelling

**Latent Dirichlet Allocation (LDA)** is a generative probabilistic model for discovering latent topics in document corpora. Each document is modelled as a mixture of topics; each topic is a distribution over words. Non-negative Matrix Factorisation (NMF) is a faster matrix-decomposition alternative.

```python
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

vectorizer = CountVectorizer(max_df=0.95, min_df=2, stop_words='english')
X_docs = vectorizer.fit_transform(documents)

lda = LatentDirichletAllocation(n_components=10, random_state=42)
lda.fit(X_docs)
```

### 5.3 Data Compression

PCA and autoencoders reduce storage and bandwidth requirements. JPEG uses a transform (DCT, related to PCA) to compress images. Autoencoders achieve better compression for domain-specific data (e.g. medical images) than JPEG.

### 5.4 Visualisation

t-SNE and UMAP are standard tools for visualising high-dimensional embeddings: word vectors (Word2Vec, GloVe), sentence transformers, neural network activations, single-cell RNA-seq profiles, and more.

---

## 6. Quiz — 10 Questions with Solutions

---

**Q1.** K-Means is guaranteed to converge. Is the solution guaranteed to be globally optimal?

<details>
<summary>Solution</summary>

**No.** K-Means converges to a **local minimum** of the WCSS objective. The final solution depends on initialisation. K-Means++ reduces (but does not eliminate) this risk by providing a better starting point.

</details>

---

**Q2.** A dataset has clusters shaped like concentric rings. Which algorithms can correctly identify them, and which cannot?

<details>
<summary>Solution</summary>

**Can:** DBSCAN (density-based, shape-agnostic), HDBSCAN, Spectral Clustering.
**Cannot:** K-Means (assumes convex spherical clusters), GMM with standard covariances, Agglomerative with complete/Ward linkage.

</details>

---

**Q3.** You run PCA on a dataset with 1000 features. The first 2 principal components explain 92% of variance. What does this tell you about the data?

<details>
<summary>Solution</summary>

The data lies (approximately) on a **2-dimensional linear manifold** embedded in 1000-dimensional space — the features are highly correlated/redundant. You can safely reduce to 2D for most downstream tasks with minimal information loss.

</details>

---

**Q4.** Why does t-SNE use a Student-t distribution in low-dimensional space but a Gaussian in high-dimensional space?

<details>
<summary>Solution</summary>

The **crowding problem**: in high-D there is exponentially more space at moderate distances than in 2D. Moderate-distance high-D neighbours would get crushed together in 2D. The heavy-tailed Student-t allows moderate-distance pairs to be mapped much farther apart, preventing cluster overlap.

</details>

---

**Q5.** What is the difference between "hard" and "soft" clustering? Give one example of each.

<details>
<summary>Solution</summary>

- **Hard clustering**: each point belongs to exactly one cluster. Example: K-Means (`labels_` is a single integer per point).
- **Soft clustering**: each point has a probability vector over all clusters. Example: GMM (`predict_proba()` returns probabilities). Soft clustering is more informative when cluster boundaries are fuzzy.

</details>

---

**Q6.** Isolation Forest anomaly scores near 0.5 — should you flag these as anomalies?

<details>
<summary>Solution</summary>

**No.** A score near 0.5 indicates a **normal** point. Scores approaching **1.0** indicate anomalies. The contamination parameter sets the threshold — by default, the top `contamination` fraction by score is flagged.

</details>

---

**Q7.** What is the "elbow" in a WCSS vs. K plot, and why does it indicate the optimal K?

<details>
<summary>Solution</summary>

The elbow is where adding another cluster yields **diminishing returns** in WCSS reduction. Below the elbow, splitting clusters removes genuine structure. Above the elbow, K-Means is just splitting natural clusters arbitrarily. The elbow represents the **best balance** between model complexity and fit.

</details>

---

**Q8.** You train an autoencoder on normal transactions for fraud detection. A new transaction has reconstruction error in the 99th percentile. What do you conclude?

<details>
<summary>Solution</summary>

The transaction is likely **anomalous (potentially fraudulent)**. The autoencoder, trained only on normal patterns, cannot reconstruct unusual transactions well, resulting in high error. The 99th percentile threshold means only 1% of normal transactions would be falsely flagged.

</details>

---

**Q9.** UMAP's `n_neighbors` parameter is set to 2. What visual artifact do you expect?

<details>
<summary>Solution</summary>

Very **fragmented, disconnected clusters** with excessive local detail — each point only looks at 2 neighbours, so the embedding captures hyper-local structure and completely loses global topology. The plot will look like scattered noise rather than meaningful clusters.

</details>

---

**Q10.** Name two situations where DBSCAN would fail, and suggest a better algorithm for each.

<details>
<summary>Solution</summary>

1. **Clusters of varying density** — a single ε cannot capture both dense and sparse clusters simultaneously. Use **HDBSCAN** instead.
2. **Very high-dimensional data** (d > ~20)** — distances become uniformly similar (curse of dimensionality), so ε-neighbourhood loses meaning. Apply **PCA/UMAP first**, then DBSCAN.

</details>

---

## 7. Project — Customer Segmentation with RFM Analysis

### 7.1 Overview

**RFM Analysis** is the gold standard for customer segmentation in e-commerce and retail. Each customer is characterised by three features:

| Feature | Description | Higher = ? |
|---|---|---|
| **R**ecency | Days since last purchase | More recently active |
| **F**requency | Number of purchases in the period | More engaged |
| **M**onetary | Total spend in the period | Higher value |

### 7.2 Dataset Setup

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from datetime import datetime

# Synthetic transaction data (replace with your retail dataset)
np.random.seed(42)
n_customers = 1000

data = {
    'CustomerID': range(1, n_customers + 1),
    'last_purchase_days_ago': np.random.exponential(scale=60, size=n_customers),
    'purchase_count': np.random.negative_binomial(n=5, p=0.3, size=n_customers),
    'total_spend': np.random.lognormal(mean=5, sigma=1.5, size=n_customers)
}

df = pd.DataFrame(data)
df.columns = ['CustomerID', 'Recency', 'Frequency', 'Monetary']
df['Recency'] = df['Recency'].astype(int).clip(1, 365)
df['Frequency'] = df['Frequency'].clip(1, 50)
df['Monetary'] = df['Monetary'].round(2)

print(df.describe())
```

### 7.3 Feature Engineering and Normalisation

```python
# Log-transform skewed features (especially Monetary)
rfm = df[['Recency', 'Frequency', 'Monetary']].copy()
rfm['Recency_log'] = np.log1p(rfm['Recency'])
rfm['Frequency_log'] = np.log1p(rfm['Frequency'])
rfm['Monetary_log'] = np.log1p(rfm['Monetary'])

features = ['Recency_log', 'Frequency_log', 'Monetary_log']
scaler = StandardScaler()
rfm_scaled = scaler.fit_transform(rfm[features])

print("Skewness before log transform:")
print(rfm[['Recency', 'Frequency', 'Monetary']].skew())
print("\nSkewness after log transform:")
print(rfm[['Recency_log', 'Frequency_log', 'Monetary_log']].skew())
```

### 7.4 Optimal K Selection

```python
# Elbow + Silhouette combined
inertias = []
silhouettes = []
K_range = range(2, 11)

for k in K_range:
    km = KMeans(n_clusters=k, init='k-means++', n_init=20, random_state=42)
    labels = km.fit_predict(rfm_scaled)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(rfm_scaled, labels))

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].plot(K_range, inertias, 'bo-', linewidth=2, markersize=8)
axes[0].set_xlabel('Number of Clusters K', fontsize=12)
axes[0].set_ylabel('Inertia (WCSS)', fontsize=12)
axes[0].set_title('Elbow Method', fontsize=14)
axes[0].grid(alpha=0.3)

axes[1].plot(K_range, silhouettes, 'rs-', linewidth=2, markersize=8)
axes[1].set_xlabel('Number of Clusters K', fontsize=12)
axes[1].set_ylabel('Silhouette Score', fontsize=12)
axes[1].set_title('Silhouette Scores', fontsize=14)
axes[1].grid(alpha=0.3)

plt.tight_layout()
plt.show()

optimal_k = K_range[np.argmax(silhouettes)]
print(f"Optimal K by silhouette: {optimal_k}")
```

### 7.5 Final Segmentation

```python
# Fit final model
km_final = KMeans(n_clusters=4, init='k-means++', n_init=50, random_state=42)
rfm['Segment'] = km_final.fit_predict(rfm_scaled)

# Analyse segment characteristics
segment_profile = rfm.groupby('Segment').agg({
    'Recency': 'mean',
    'Frequency': 'mean',
    'Monetary': 'mean',
    'Segment': 'count'
}).rename(columns={'Segment': 'Count'})

print("\n=== Segment Profiles ===")
print(segment_profile.round(2))

# Map segments to business labels
def label_segment(row):
    # Champions: low recency (recent), high frequency, high monetary
    if row['Recency'] < 30 and row['Frequency'] > 10:
        return 'Champions'
    elif row['Recency'] < 60 and row['Frequency'] > 5:
        return 'Loyal Customers'
    elif row['Recency'] > 180:
        return 'At Risk / Churned'
    else:
        return 'Potential Loyalists'

rfm['Segment_Label'] = rfm.apply(label_segment, axis=1)

# Distribution plot
plt.figure(figsize=(10, 6))
segment_counts = rfm['Segment_Label'].value_counts()
colors = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12']
bars = plt.bar(segment_counts.index, segment_counts.values,
               color=colors, edgecolor='white', linewidth=1.5)

for bar, count in zip(bars, segment_counts.values):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             str(count), ha='center', fontsize=11, fontweight='bold')

plt.title('Customer Segments Distribution', fontsize=16, fontweight='bold')
plt.xlabel('Segment', fontsize=12)
plt.ylabel('Number of Customers', fontsize=12)
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.show()
```

### 7.6 Visualising with UMAP

```python
import umap

reducer = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1,
                    random_state=42, metric='euclidean')
rfm_2d = reducer.fit_transform(rfm_scaled)

plt.figure(figsize=(10, 8))
scatter_colors = {'Champions': '#2ecc71', 'Loyal Customers': '#3498db',
                  'Potential Loyalists': '#f39c12', 'At Risk / Churned': '#e74c3c'}

for label, colour in scatter_colors.items():
    mask = rfm['Segment_Label'] == label
    plt.scatter(rfm_2d[mask, 0], rfm_2d[mask, 1],
                c=colour, label=label, alpha=0.7, s=30, edgecolors='none')

plt.title('RFM Customer Segments — UMAP Projection', fontsize=16, fontweight='bold')
plt.xlabel('UMAP Dimension 1')
plt.ylabel('UMAP Dimension 2')
plt.legend(title='Segment', fontsize=11, title_fontsize=12)
plt.grid(alpha=0.2)
plt.tight_layout()
plt.show()
```

### 7.7 Business Recommendations by Segment

| Segment | Characteristics | Recommended Actions |
|---|---|---|
| **Champions** | Recent, frequent, high spend | Reward with loyalty programme; ask for reviews; early access to new products |
| **Loyal Customers** | Regular buyers, good spend | Upsell higher-tier products; personalised offers |
| **Potential Loyalists** | Recent first/second purchase | Onboarding email series; discount on second purchase |
| **At Risk / Churned** | Long time since last purchase | Win-back campaign; "We miss you" email; significant discount |

---

## 8. References

### Foundational Papers

- **K-Means:** Lloyd, S. P. (1982). Least squares quantization in PCM. *IEEE Transactions on Information Theory*, 28(2), 129–137.
- **K-Means++:** Arthur, D., & Vassilvitskii, S. (2007). k-means++: The Advantages of Careful Seeding. *SODA 2007*.
- **DBSCAN:** Ester, M. et al. (1996). A density-based algorithm for discovering clusters in large spatial databases with noise. *KDD 1996*.
- **EM / GMM:** Dempster, A. P., Laird, N. M., & Rubin, D. B. (1977). Maximum likelihood from incomplete data via the EM algorithm. *JRSS-B*, 39(1).
- **t-SNE:** van der Maaten, L., & Hinton, G. (2008). Visualizing Data using t-SNE. *JMLR*, 9, 2579–2605.
- **UMAP:** McInnes, L., Healy, J., & Melville, J. (2018). UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction. *arXiv:1802.03426*.
- **Isolation Forest:** Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation Forest. *ICDM 2008*.
- **One-Class SVM:** Schölkopf, B. et al. (2001). Estimating the support of a high-dimensional distribution. *Neural Computation*, 13(7).
- **HDBSCAN:** Campello, R. J. et al. (2013). Density-based clustering based on hierarchical density estimates. *PAKDD 2013*.

### Course Notes and Books

- **CS229 (Stanford):** Machine Learning course notes by Andrew Ng. [cs229.stanford.edu](https://cs229.stanford.edu) — Lecture notes on unsupervised learning, EM algorithm, PCA.
- **Bishop, C. M. (2006).** *Pattern Recognition and Machine Learning*. Springer. Chapters 9 (EM), 12 (PCA).
- **Murphy, K. P. (2012).** *Machine Learning: A Probabilistic Perspective*. MIT Press. Chapters 11 (mixture models), 12 (latent linear models).
- **Goodfellow, I., Bengio, Y., & Courville, A. (2016).** *Deep Learning*. MIT Press. Chapter 14 (autoencoders). [deeplearningbook.org](https://deeplearningbook.org)

### Documentation and Tutorials

- **scikit-learn Clustering:** [scikit-learn.org/stable/modules/clustering.html](https://scikit-learn.org/stable/modules/clustering.html)
- **scikit-learn Decomposition:** [scikit-learn.org/stable/modules/decomposition.html](https://scikit-learn.org/stable/modules/decomposition.html)
- **UMAP Documentation:** [umap-learn.readthedocs.io](https://umap-learn.readthedocs.io)
- **UMAP — How it Works:** [umap-learn.readthedocs.io/en/latest/how_umap_works.html](https://umap-learn.readthedocs.io/en/latest/how_umap_works.html)
- **HDBSCAN Documentation:** [hdbscan.readthedocs.io](https://hdbscan.readthedocs.io)
- **scikit-learn Anomaly Detection:** [scikit-learn.org/stable/modules/outlier_detection.html](https://scikit-learn.org/stable/modules/outlier_detection.html)

---

*Module 03 complete. Next: Module 04 — Neural Networks & Deep Learning Foundations.*

---
