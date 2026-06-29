# Linear Algebra Foundations for AI/ML/Deep Learning

> "The key to understanding machine learning is understanding the geometry of high-dimensional spaces — and linear algebra is the language of that geometry."

---

## Table of Contents

1. [Why Linear Algebra for AI/ML?](#1-why-linear-algebra-for-aiml)
2. [Vectors](#2-vectors)
3. [Vector Operations](#3-vector-operations)
4. [Matrices](#4-matrices)
5. [Matrix Operations](#5-matrix-operations)
6. [Special Matrices](#6-special-matrices)
7. [Linear Transformations](#7-linear-transformations)
8. [Norms and Distance](#8-norms-and-distance)
9. [Dot Products and Inner Products](#9-dot-products-and-inner-products)
10. [Matrix Rank and Linear Independence](#10-matrix-rank-and-linear-independence)
11. [Systems of Linear Equations](#11-systems-of-linear-equations)
12. [Determinants](#12-determinants)
13. [Eigenvalues and Eigenvectors](#13-eigenvalues-and-eigenvectors)
14. [Matrix Decompositions](#14-matrix-decompositions)
15. [Singular Value Decomposition (SVD)](#15-singular-value-decomposition-svd)
16. [Principal Component Analysis (PCA)](#16-principal-component-analysis-pca)
17. [Tensor Operations](#17-tensor-operations)
18. [Quiz: 10 Questions with Solutions](#18-quiz-10-questions-with-solutions)
19. [Exercises: 5 Practical Problems](#19-exercises-5-practical-problems)
20. [Learning Resources](#20-learning-resources)

---

## 1. Why Linear Algebra for AI/ML?

Linear algebra is not a prerequisite you grudge through — it *is* machine learning. Every major operation in deep learning reduces to linear algebra:

| ML Operation | Linear Algebra Concept |
|---|---|
| Neural network forward pass | Matrix-vector multiplication |
| Backpropagation | Jacobians, chain rule on matrices |
| Word embeddings (Word2Vec, BERT) | Vectors in high-dimensional space |
| Dimensionality reduction (PCA, t-SNE) | Eigendecomposition, SVD |
| Recommender systems | Matrix factorization |
| Convolutional layers | Tensor contractions |
| Attention mechanism (Transformers) | Scaled dot-product, outer products |
| Gradient descent | Vector operations, norms |
| Data normalization | Projection, orthogonalization |
| Covariance, PCA | Symmetric matrix diagonalization |

Understanding these connections transforms you from someone who *uses* ML libraries to someone who can *design, debug, and extend* them.

---

## 2. Vectors

### Intuition

A vector is a directed arrow in space. In ML, a vector typically represents a **data point** (a row in your dataset), an **embedding** (how a word or image is represented), or a **weight** (parameters of a model).

### Formal Definition

A vector **v** in n-dimensional space is an ordered list of n real numbers:

```
v = [v₁, v₂, ..., vₙ]ᵀ  ∈ ℝⁿ
```

The superscript `ᵀ` denotes the transpose (column vector by convention).

### Worked Example

A house can be represented as a 3D vector of features:

```
house = [area_sqft, num_bedrooms, distance_to_city_km]ᵀ
      = [1500, 3, 12.5]ᵀ
```

### ASCII Diagram: 2D and 3D Vectors

```
2D Vector v = [3, 4]ᵀ          3D Vector u = [1, 2, 3]ᵀ

    y                               z
    |                               |
  4 +.........*  v                  |    * (1,2,3)
    |        /                     /|   /
    |       /                     / |  /
    |      /                     /  | /
    |     /                     /   |/
    +----+-------> x            +---+--------> y
    0    3                     /
                              x
```

### Python Code

```python
import numpy as np

# Create vectors
v = np.array([3, 4])           # 1D → treated as row vector
v_col = np.array([[3], [4]])   # 2D → explicit column vector
u = np.array([1, 2, 3])

print(f"v shape: {v.shape}")        # (2,)
print(f"v_col shape: {v_col.shape}") # (2, 1)
print(f"u shape: {u.shape}")        # (3,)

# Magnitude (Euclidean norm)
magnitude = np.linalg.norm(v)
print(f"|v| = {magnitude}")          # 5.0

# Unit vector (normalize)
v_unit = v / np.linalg.norm(v)
print(f"unit v = {v_unit}")          # [0.6, 0.8]
print(f"|unit v| = {np.linalg.norm(v_unit)}")  # 1.0
```

### How This Connects to AI/ML

- **Feature vectors**: Every data point is a vector. A 28x28 MNIST image is a 784-dimensional vector.
- **Embeddings**: Word2Vec maps words to ~300-dimensional vectors so that `king - man + woman ≈ queen`.
- **Gradient vector**: During training, the gradient `∇L` is a vector pointing in the direction of steepest loss increase.

---

## 3. Vector Operations

### Addition and Scalar Multiplication

```
u + v = [u₁+v₁, u₂+v₂, ..., uₙ+vₙ]
α·v   = [α·v₁, α·v₂, ..., α·vₙ]
```

### ASCII Diagram: Vector Addition

```
    y
    |
  5 |        *  u+v = [4,5]
    |       /|
  4 |      / |
    |   v /  | u=[1,4]
  3 |    /   |
    |   /    |
  2 |  /     |
    | / u=[3,1]
  1 |/
    +---------> x
    0  1  2  3  4
```

### Linear Combinations and Span

A **linear combination** of vectors `v₁, v₂, ..., vₖ` is:

```
α₁v₁ + α₂v₂ + ... + αₖvₖ   where α₁...αₖ ∈ ℝ
```

The **span** is the set of ALL possible linear combinations — the entire subspace reachable.

### Python Code

```python
import numpy as np

u = np.array([1, 4])
v = np.array([3, 1])

# Addition
print(u + v)           # [4, 5]

# Scalar multiplication
print(3 * u)           # [3, 12]

# Linear combination
alpha, beta = 2, -1
combo = alpha * u + beta * v
print(combo)           # [2*1 + (-1)*3, 2*4 + (-1)*1] = [-1, 7]

# Broadcasting in ML: add bias to all rows
X = np.random.randn(100, 5)  # 100 data points, 5 features
bias = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
X_biased = X + bias  # NumPy broadcasts: adds bias to every row
print(X_biased.shape)  # (100, 5)
```

### How This Connects to AI/ML

- **Attention**: The output of a Transformer attention head is a **weighted sum** (linear combination) of value vectors.
- **Residual connections**: `x + F(x)` is vector addition — the foundation of ResNets.
- **Gradient updates**: `θ ← θ - α·∇L` is scalar multiplication + vector subtraction.

---

## 4. Matrices

### Intuition

A matrix is a rectangular grid of numbers. In ML, matrices encode **datasets** (rows = samples, columns = features), **weight tensors** (linear layers), and **transformations** (rotation, scaling, projection).

### Formal Definition

An m×n matrix A has m rows and n columns:

```
        n columns
    ┌                    ┐
    │ a₁₁  a₁₂  ...  a₁ₙ │  ← row 1
m   │ a₂₁  a₂₂  ...  a₂ₙ │  ← row 2
rows│  .    .    ...   .  │
    │ aₘ₁  aₘ₂  ...  aₘₙ │  ← row m
    └                    ┘
```

Entry `aᵢⱼ` is at row i, column j.

### Python Code

```python
import numpy as np

# Create a 3x4 matrix
A = np.array([
    [1, 2, 3, 4],
    [5, 6, 7, 8],
    [9, 10, 11, 12]
])

print(f"Shape: {A.shape}")    # (3, 4)
print(f"Rows: {A.shape[0]}")  # 3
print(f"Cols: {A.shape[1]}")  # 4
print(f"Entry A[1,2] = {A[1,2]}")  # 7  (0-indexed)

# Transpose: flip rows and columns
A_T = A.T
print(f"Transpose shape: {A_T.shape}")  # (4, 3)

# Random matrix initialization (Xavier/Glorot for neural networks)
fan_in, fan_out = 512, 256
limit = np.sqrt(6 / (fan_in + fan_out))
W = np.random.uniform(-limit, limit, (fan_in, fan_out))
print(f"Weight matrix shape: {W.shape}")  # (512, 256)
```

### How This Connects to AI/ML

- **Dataset matrix X**: Shape `(n_samples, n_features)` — every ML algorithm starts here.
- **Weight matrix W**: A fully connected layer transforms `x → Wx + b`, where W is learned.
- **Attention matrix**: The `n×n` attention scores matrix determines which tokens attend to which.

---

## 5. Matrix Operations

### Matrix Multiplication

The most important operation in all of ML. Matrix C = A·B where A is m×k and B is k×n:

```
Cᵢⱼ = Σₗ Aᵢₗ · Bₗⱼ   (dot product of row i of A with column j of B)
```

### ASCII Diagram: Matrix Multiplication

```
A (2×3)      B (3×2)         C = A·B (2×2)

┌         ┐  ┌      ┐        ┌            ┐
│ 1  2  3 │  │ 7  8 │        │ 1·7+2·9+3·11  1·8+2·10+3·12 │
│ 4  5  6 │  │ 9 10 │   =    │ 4·7+5·9+6·11  4·8+5·10+6·12 │
└         ┘  │11 12 │        └            ┘
             └      ┘
                              ┌         ┐
                          =   │ 58   64 │
                              │139  154 │
                              └         ┘

Key constraint: inner dimensions must match!
A: (m × k) · B: (k × n) → C: (m × n)
        ↑___↑ must match
```

### Python Code

```python
import numpy as np

A = np.array([[1, 2, 3],
              [4, 5, 6]])    # shape (2, 3)

B = np.array([[7,  8],
              [9, 10],
              [11, 12]])     # shape (3, 2)

# Matrix multiplication
C = A @ B           # preferred syntax (Python 3.5+)
# C = np.matmul(A, B)  # equivalent
# C = np.dot(A, B)     # also equivalent for 2D

print(C)
# [[ 58  64]
#  [139 154]]

# Batch matrix multiplication (critical for deep learning)
batch_size = 32
seq_len = 128
d_model = 512
d_k = 64

Q = np.random.randn(batch_size, seq_len, d_k)   # Queries
K = np.random.randn(batch_size, seq_len, d_k)   # Keys

# Batched dot product: attention scores
scores = Q @ K.transpose(0, 2, 1)  # (32, 128, 128)
scores_scaled = scores / np.sqrt(d_k)
print(f"Attention scores shape: {scores_scaled.shape}")
```

### Element-wise Operations (Hadamard Product)

```python
A = np.array([[1, 2], [3, 4]])
B = np.array([[5, 6], [7, 8]])

hadamard = A * B   # NOT matrix multiply!
print(hadamard)
# [[ 5, 12],
#  [21, 32]]

# Used in: LSTM gates, attention masking, dropout
```

### How This Connects to AI/ML

- **Forward pass**: For a batch of inputs X (n×d) and weight W (d×h): `H = X @ W + b` — this single line IS the dense layer.
- **Computational efficiency**: GPUs are designed for matrix multiply (GEMM). Batching = doing many dot products in parallel.
- **Transformer attention**: `Attention(Q,K,V) = softmax(QKᵀ/√d_k)V` — two matrix multiplies.

---

## 6. Special Matrices

### Identity Matrix

```
I₃ = ┌         ┐
     │ 1  0  0 │
     │ 0  1  0 │
     │ 0  0  1 │
     └         ┘
A·I = I·A = A   (multiplicative identity)
```

### Symmetric Matrix

A matrix where `A = Aᵀ` (equal to its own transpose). Covariance matrices are always symmetric.

### Orthogonal Matrix

A square matrix Q where `QᵀQ = QQᵀ = I`, meaning `Qᵀ = Q⁻¹`. Columns are orthonormal vectors.

Orthogonal matrices **preserve lengths and angles** — they represent pure rotations/reflections.

### Diagonal Matrix

Only has non-zero entries on the main diagonal. Efficient to work with: `D·v` just scales each component.

### Python Code

```python
import numpy as np

# Identity
I = np.eye(4)
print(I)

# Diagonal matrix
D = np.diag([2, 0.5, 3, 1])
print(D)

# Check symmetry
A = np.array([[4, 2, 1],
              [2, 5, 3],
              [1, 3, 6]])
print(np.allclose(A, A.T))  # True — symmetric

# Covariance matrix is always symmetric positive semi-definite
X = np.random.randn(1000, 5)
X = X - X.mean(axis=0)      # center data
cov = (X.T @ X) / (len(X) - 1)
print(f"Covariance matrix shape: {cov.shape}")  # (5, 5)
print(f"Symmetric: {np.allclose(cov, cov.T)}")  # True

# Check positive semi-definite (all eigenvalues >= 0)
eigenvalues = np.linalg.eigvalsh(cov)
print(f"All eigenvalues >= 0: {np.all(eigenvalues >= -1e-10)}")  # True
```

### How This Connects to AI/ML

- **Batch Normalization**: Normalizing by a diagonal covariance approximation.
- **Rotation invariance**: Orthogonal matrices in data augmentation.
- **Efficient parameterization**: Some architectures constrain weight matrices to be orthogonal for stable training.

---

## 7. Linear Transformations

### Intuition

A matrix **IS** a linear transformation. Multiplying a vector by a matrix transforms it — stretches, rotates, reflects, or projects it into another space.

### Key Geometric Operations

```
Scaling by 2 along x:           Rotation by 45°:
┌     ┐                         ┌              ┐
│ 2 0 │                         │ cos45  -sin45 │
│ 0 1 │                         │ sin45   cos45 │
└     ┘                         └              ┘

Projection onto x-axis:         Shear:
┌     ┐                         ┌     ┐
│ 1 0 │                         │ 1 k │
│ 0 0 │                         │ 0 1 │
└     ┘                         └     ┘
```

### ASCII Diagram: Transformation Effect

```
Before transformation:          After rotation (90° CCW):
                                A = [[0,-1],[1,0]]
   y                               y
   |  *  *  *                      |
 2 | * grid *                    2 |  *--*
   |  *  *  *                      | *|  |*
   +---------> x           →       +--*--*---> x
   0  1  2  3                      0  1  2  3
                                     *  *
```

### Python Code

```python
import numpy as np
import matplotlib.pyplot as plt

# Rotation matrix by angle theta
def rotation_matrix(theta_deg):
    theta = np.radians(theta_deg)
    return np.array([
        [np.cos(theta), -np.sin(theta)],
        [np.sin(theta),  np.cos(theta)]
    ])

R = rotation_matrix(45)
v = np.array([1, 0])
v_rotated = R @ v
print(f"Rotating [1,0] by 45°: {v_rotated}")
# [0.707, 0.707] — moved to 45° angle

# Composition of transformations: T₂(T₁(v)) = (T₂·T₁)v
scale = np.diag([2, 0.5])
rotate = rotation_matrix(30)

# Apply scale first, then rotate
combined = rotate @ scale
v = np.array([1, 1])
print(f"Scale then rotate: {combined @ v}")
# Note: order matters! (T₂·T₁ ≠ T₁·T₂ in general)
```

### How This Connects to AI/ML

- **Every layer is a transformation**: `W·x` transforms the input space into a new representation space.
- **Deep networks = composition**: A 10-layer network applies 10 transformations sequentially.
- **Data augmentation**: Rotation, scaling, flipping — all linear (or affine) transformations.
- **Equivariance in CNNs**: Convolution is a specific linear transformation that respects spatial structure.

---

## 8. Norms and Distance

### Intuition

Norms measure the "size" or "length" of a vector. Different norms penalize differently, which is why the choice of norm matters profoundly in ML.

### Common Norms

| Norm | Formula | Also Called | Shape of Unit Ball |
|---|---|---|---|
| L0 | # non-zero entries | L0 "norm" | (not truly a norm) |
| L1 | Σ\|vᵢ\| | Manhattan / Taxicab | Diamond (2D) |
| L2 | √(Σvᵢ²) | Euclidean | Circle/Sphere |
| L∞ | max\|vᵢ\| | Max / Chebyshev | Square/Cube |
| Lp | (Σ\|vᵢ\|ᵖ)^(1/p) | General Lp | Depends on p |

### ASCII Diagram: Unit Balls in 2D

```
         L1 (diamond)    L2 (circle)    L∞ (square)

              y               y               y
              |               |               |
           1 _|_ 1         ___|___         ___|___
            /|\            /  |  \         |   |   |
           / | \          /   |   \        |   |   |
    ------/--+--\------  /    |    \  -----+---+---+-----
    -1   /   |   \ 1    |(    |    )|  -1  |   |   |  1
          \  |  /        \    |    /        |   |   |
           \ | /          \   |   /        |___|___|
            \|/            \__|__/              |
            -1              -1               -1
```

### Python Code

```python
import numpy as np

v = np.array([3.0, -4.0, 1.0, -2.0])

# Various norms
l1 = np.linalg.norm(v, ord=1)   # |3|+|-4|+|1|+|-2| = 10
l2 = np.linalg.norm(v, ord=2)   # sqrt(9+16+1+4) = sqrt(30) ≈ 5.477
linf = np.linalg.norm(v, ord=np.inf)  # max(3,4,1,2) = 4

print(f"L1 norm: {l1}")
print(f"L2 norm: {l2:.4f}")
print(f"L∞ norm: {linf}")

# Frobenius norm for matrices (generalized L2)
A = np.array([[1, 2], [3, 4]])
frob = np.linalg.norm(A, 'fro')  # sqrt(1+4+9+16) = sqrt(30)
print(f"Frobenius norm: {frob:.4f}")

# Distance between vectors
a = np.array([1.0, 2.0, 3.0])
b = np.array([4.0, 6.0, 3.0])

l2_dist = np.linalg.norm(a - b)        # Euclidean distance = 5
l1_dist = np.linalg.norm(a - b, ord=1) # Manhattan distance = 7
print(f"L2 distance: {l2_dist}")
print(f"L1 distance: {l1_dist}")

# Cosine similarity (used in NLP embeddings)
cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
print(f"Cosine similarity: {cos_sim:.4f}")
```

### How This Connects to AI/ML

- **L1 regularization (Lasso)**: Adds `λ·||W||₁` to loss → promotes **sparsity** in weights (feature selection).
- **L2 regularization (Ridge/Weight Decay)**: Adds `λ·||W||₂²` to loss → shrinks weights uniformly, prevents overfitting.
- **Gradient clipping**: `g ← g · (max_norm / ||g||₂)` if `||g||₂ > max_norm` — prevents exploding gradients.
- **Cosine similarity**: Used in semantic search, sentence transformers, and nearest-neighbor retrieval.
- **KNN**: K-Nearest Neighbors literally uses L2 (or L1) distance to find similar points.

---

## 9. Dot Products and Inner Products

### Formal Definition

The dot product of two vectors u and v in ℝⁿ:

```
u · v = uᵀv = Σᵢ uᵢvᵢ = |u| · |v| · cos(θ)
```

where θ is the angle between the vectors.

### Geometric Interpretation

```
 u · v > 0   →  angle < 90°  → vectors point "same direction"
 u · v = 0   →  angle = 90°  → vectors are ORTHOGONAL (perpendicular)
 u · v < 0   →  angle > 90°  → vectors point "opposite directions"

       u·v = |u||v|cos(θ)

             u
            /
           /  θ
          /___________
         v

   projection of u onto v = (u·v / |v|²) · v
```

### Python Code

```python
import numpy as np

u = np.array([1.0, 2.0, 3.0])
v = np.array([4.0, 5.0, 6.0])

# Dot product
dot = np.dot(u, v)           # 1·4 + 2·5 + 3·6 = 32
dot_alt = u @ v              # same thing
dot_manual = np.sum(u * v)   # same thing

print(f"Dot product: {dot}")  # 32

# Angle between vectors
cos_theta = dot / (np.linalg.norm(u) * np.linalg.norm(v))
theta_deg = np.degrees(np.arccos(np.clip(cos_theta, -1, 1)))
print(f"Angle: {theta_deg:.2f}°")  # 12.93°

# Orthogonality check
a = np.array([1, 0])
b = np.array([0, 1])
print(f"Are [1,0] and [0,1] orthogonal? {np.isclose(np.dot(a, b), 0)}")  # True

# Projection of u onto v
proj = (np.dot(u, v) / np.dot(v, v)) * v
print(f"Projection of u onto v: {proj}")

# Matrix-vector as a set of dot products
W = np.random.randn(10, 3)  # weight matrix
x = np.array([1.0, 2.0, 3.0])
output = W @ x  # each output neuron computes a dot product with x
print(f"Linear layer output shape: {output.shape}")  # (10,)
```

### How This Connects to AI/ML

- **Neuron activation**: Each neuron computes `w·x + b` — literally a dot product plus bias.
- **Attention scores**: `score(qᵢ, kⱼ) = qᵢ · kⱼ` — how much query i attends to key j.
- **Cosine similarity search**: Finding the nearest embedding = finding the max dot product (after normalization).
- **Matrix multiply as batched dot products**: The entire forward pass is just many dot products computed in parallel.

---

## 10. Matrix Rank and Linear Independence

### Linear Independence

Vectors `v₁, ..., vₖ` are **linearly independent** if no vector can be written as a linear combination of the others. Equivalently, the only solution to `α₁v₁ + ... + αₖvₖ = 0` is all αᵢ = 0.

### Rank

The **rank** of a matrix A is the number of linearly independent rows (= number of linearly independent columns — always equal). It measures the "true dimensionality" of the information in A.

```
Rank deficiency examples:

Full rank (rank 2):         Rank 1 (row 2 = 2×row 1):
┌     ┐                     ┌      ┐
│ 1 2 │                     │ 1  2 │
│ 3 4 │  rank = 2           │ 2  4 │  rank = 1
└     ┘                     └      ┘
```

### Python Code

```python
import numpy as np

A = np.array([[1, 2, 3],
              [4, 5, 6],
              [7, 8, 9]])

rank_A = np.linalg.matrix_rank(A)
print(f"Rank of A: {rank_A}")  # 2 (row 3 = row 1 + row 2 scaled)

B = np.array([[1, 0, 0],
              [0, 1, 0],
              [0, 0, 1]])
print(f"Rank of B: {np.linalg.matrix_rank(B)}")  # 3 (full rank)

# Null space: vectors x where Ax = 0
# Use SVD to find null space
U, S, Vt = np.linalg.svd(A)
null_mask = S < 1e-10
null_space = Vt[null_mask]
print(f"Null space basis: {null_space}")

# Check effective rank with tolerance (numerical rank)
S = np.linalg.svd(A, compute_uv=False)
print(f"Singular values: {S}")
```

### How This Connects to AI/ML

- **Low-rank approximation**: Many weight matrices in transformers are approximately low-rank → LoRA (Low-Rank Adaptation) exploits this to fine-tune LLMs with far fewer parameters.
- **Intrinsic dimensionality**: Even though datasets live in high-dimensional spaces, their rank (effective dimension) is often much lower.
- **Underdetermined systems**: If you have fewer data points than features, your system is rank-deficient → regularization is essential.

---

## 11. Systems of Linear Equations

### Formal Setup

```
a₁₁x₁ + a₁₂x₂ + ... + a₁ₙxₙ = b₁
a₂₁x₁ + a₂₂x₂ + ... + a₂ₙxₙ = b₂
...
aₘ₁x₁ + aₘ₂x₂ + ... + aₘₙxₙ = bₘ

Matrix form:  Ax = b
```

### Solutions

| Condition | # Solutions |
|---|---|
| A is square, full rank | Exactly one: `x = A⁻¹b` |
| More equations than unknowns (overdetermined) | Usually 0 — use least squares |
| Fewer equations than unknowns (underdetermined) | Infinitely many |

### Python Code

```python
import numpy as np

# Exact solution (square, full rank)
A = np.array([[2, 1, -1],
              [-3, -1, 2],
              [-2, 1, 2]], dtype=float)
b = np.array([8, -11, -3], dtype=float)

x = np.linalg.solve(A, b)
print(f"Solution: {x}")          # [2. 3. -1.]
print(f"Verify Ax=b: {A @ x}")   # [8. -11. -3.]

# Least squares solution (overdetermined system)
# Classic linear regression: minimize ||Xw - y||²
X = np.random.randn(1000, 10)   # 1000 samples, 10 features
true_w = np.random.randn(10)
y = X @ true_w + 0.01 * np.random.randn(1000)  # with noise

# Closed-form normal equations: w = (XᵀX)⁻¹Xᵀy
w_lstsq, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)
print(f"Max parameter error: {np.max(np.abs(w_lstsq - true_w)):.6f}")

# Pseudoinverse (handles any shape and rank)
A_pinv = np.linalg.pinv(A)
x_pinv = A_pinv @ b
print(f"Pseudoinverse solution: {x_pinv}")
```

### How This Connects to AI/ML

- **Linear regression**: The entire problem is `Xw = y` → solution is `w = (XᵀX)⁻¹Xᵀy` (normal equations).
- **Least squares everywhere**: Losses of the form `||Ax - b||²` appear in regression, physics-informed NNs, and optimal control.
- **Pseudoinverse**: Appears in linear probing, representation learning benchmarks, and theoretical analysis.

---

## 12. Determinants

### Intuition

The determinant of a square matrix measures the **signed volume scaling factor** of the transformation it represents. `det(A) = 0` means the transformation collapses space to a lower dimension (matrix is singular, not invertible).

### Key Properties

```
det(A)  > 0 → orientation preserved, |det(A)| = volume scale
det(A)  < 0 → orientation flipped
det(A)  = 0 → matrix is singular (not invertible, rank-deficient)
det(AB) = det(A)·det(B)
det(Aᵀ) = det(A)
det(A⁻¹) = 1/det(A)
```

### Python Code

```python
import numpy as np

A = np.array([[1, 2],
              [3, 4]])

det_A = np.linalg.det(A)
print(f"det(A) = {det_A}")       # -2.0 (orientation flipped, scales by 2)

# Singular matrix (det = 0)
B = np.array([[1, 2],
              [2, 4]])
print(f"det(B) = {np.linalg.det(B):.2f}")  # 0.00 — row 2 = 2·row 1

# Rotation matrix — always det = 1 (preserves volume and orientation)
theta = np.radians(45)
R = np.array([[np.cos(theta), -np.sin(theta)],
              [np.sin(theta),  np.cos(theta)]])
print(f"det(rotation) = {np.linalg.det(R):.4f}")  # 1.0

# Invertibility check
try:
    A_inv = np.linalg.inv(A)
    print(f"A⁻¹ = {A_inv}")
    print(f"A·A⁻¹ ≈ I: {np.allclose(A @ A_inv, np.eye(2))}")
except np.linalg.LinAlgError:
    print("Matrix is singular, cannot invert")
```

### How This Connects to AI/ML

- **Change of variables**: In normalizing flows (generative models), the log-determinant of the Jacobian tracks how probability densities transform.
- **Invertible networks**: Architectures like NICE/RealNVP require invertible layers with tractable determinants.
- **Numerical stability**: Near-zero determinants signal ill-conditioned matrices → poor conditioning → numerical issues in training.

---

## 13. Eigenvalues and Eigenvectors

### Intuition

An eigenvector of a matrix A is a **special vector that only gets scaled** (not rotated) when A is applied to it. The scaling factor is the eigenvalue.

```
A · v = λ · v

where:  v = eigenvector (direction that is preserved)
        λ = eigenvalue (how much it is scaled)
```

### ASCII Diagram: Eigenvalue Decomposition

```
Matrix A acting on a random vector:     Matrix A acting on eigenvector:

         *  v_rotated                        *  v_stretched
        /                                   /
       /   A·v (rotated AND scaled)         /  A·v = λ·v (ONLY scaled, not rotated)
      /                                    /
 ----*------> v                       ----*------> v
  origin                           origin

The eigenvector v just slides along its own line!
```

### Formal Definition

For a square matrix A ∈ ℝⁿˣⁿ:
- Eigenvalue equation: `Av = λv`  ⟺  `(A - λI)v = 0`
- The characteristic polynomial: `det(A - λI) = 0`
- An n×n matrix has at most n eigenvalues

### Worked Example

```
A = [[3, 1],      Characteristic polynomial:
     [0, 2]]      det([[3-λ, 1], [0, 2-λ]]) = (3-λ)(2-λ) = 0
                  λ₁ = 3, λ₂ = 2

For λ₁=3:   (A-3I)v = 0  →  [[0,1],[0,-1]]v = 0  →  v₁ = [1, 0]ᵀ
For λ₂=2:   (A-2I)v = 0  →  [[1,1],[0,0]]v = 0   →  v₂ = [1,-1]ᵀ (normalized)
```

### Python Code

```python
import numpy as np

A = np.array([[3, 1],
              [0, 2]], dtype=float)

# Eigendecomposition
eigenvalues, eigenvectors = np.linalg.eig(A)
print(f"Eigenvalues: {eigenvalues}")        # [3. 2.]
print(f"Eigenvectors (columns):\n{eigenvectors}")

# Verify: A·v = λ·v
for i, (lam, v) in enumerate(zip(eigenvalues, eigenvectors.T)):
    Av = A @ v
    lv = lam * v
    print(f"λ{i}: A·v = {Av}, λ·v = {lv}, match: {np.allclose(Av, lv)}")

# Eigendecomposition: A = V Λ V⁻¹
V = eigenvectors
Lambda = np.diag(eigenvalues)
V_inv = np.linalg.inv(V)
A_reconstructed = V @ Lambda @ V_inv
print(f"A reconstructed correctly: {np.allclose(A, A_reconstructed)}")  # True

# For symmetric matrices: use eigh (more stable, guaranteed real eigenvalues)
cov = np.array([[4, 2], [2, 3]])
eigenvalues_sym, eigenvectors_sym = np.linalg.eigh(cov)
print(f"\nSymmetric eigenvalues: {eigenvalues_sym}")  # always real, sorted ascending

# Power of a matrix using eigendecomposition: Aⁿ = VΛⁿV⁻¹
n = 10
A_power = V @ np.diag(eigenvalues**n) @ V_inv
print(f"A^10 via eigendecomposition:\n{A_power}")
print(f"Verify via direct: {np.allclose(A_power, np.linalg.matrix_power(A, 10))}")
```

### Spectral Theorem

For a **real symmetric** matrix (like a covariance matrix): all eigenvalues are real, and eigenvectors are orthogonal. This means:

```
A = QΛQᵀ    where Q is orthogonal (Qᵀ=Q⁻¹) and Λ is diagonal
```

### How This Connects to AI/ML

- **PCA**: The principal components ARE the eigenvectors of the covariance matrix; variances = eigenvalues.
- **Graph Neural Networks**: Spectral graph convolution is defined via the eigendecomposition of the graph Laplacian.
- **Stability of RNNs**: The largest eigenvalue of the recurrent weight matrix controls vanishing/exploding gradients. `|λ_max| < 1` → vanishing; `|λ_max| > 1` → exploding.
- **PageRank**: Google's PageRank is the dominant eigenvector of the web's adjacency matrix.
- **Power iteration**: Training large-scale ML often requires spectral properties estimated via power iteration (e.g., spectral normalization).

---

## 14. Matrix Decompositions

### LU Decomposition

Any square matrix (with appropriate pivoting) can be factored as:
`A = LU` where L is lower triangular and U is upper triangular.

Used to solve `Ax = b` efficiently: first solve `Ly = b` (forward substitution), then `Ux = y` (backward substitution).

### Cholesky Decomposition

For **symmetric positive definite** matrices: `A = LLᵀ`

Half the work of LU since L is unique. Used in Gaussian processes and Kalman filters.

### QR Decomposition

Any matrix `A = QR` where Q is orthogonal and R is upper triangular.

Key use: computing eigenvalues (QR algorithm) and solving least squares.

### Python Code

```python
import numpy as np
from scipy import linalg

A = np.array([[4, 3], [6, 3]], dtype=float)

# LU decomposition
P, L, U = linalg.lu(A)
print(f"L:\n{L}")
print(f"U:\n{U}")
print(f"P·L·U ≈ A: {np.allclose(P @ L @ U, A)}")

# QR decomposition
Q, R = np.linalg.qr(A)
print(f"\nQ (orthogonal):\n{Q}")
print(f"R (upper triangular):\n{R}")
print(f"QᵀQ ≈ I: {np.allclose(Q.T @ Q, np.eye(2))}")

# Cholesky decomposition (requires positive definite matrix)
S = np.array([[4, 2], [2, 3]], dtype=float)  # symmetric positive definite
L_chol = np.linalg.cholesky(S)
print(f"\nCholesky L:\n{L_chol}")
print(f"LLᵀ ≈ S: {np.allclose(L_chol @ L_chol.T, S)}")
```

### How This Connects to AI/ML

- **Cholesky in Gaussian Processes**: Efficiently computing `(K + σ²I)⁻¹` via Cholesky avoids full matrix inversion.
- **QR in optimization**: QR decomposition underlies many numerical eigenvalue algorithms used in second-order optimization (L-BFGS, Newton methods).
- **Numerical stability**: Decompositions are numerically stable — direct matrix inversion `A⁻¹` is almost never used in practice.

---

## 15. Singular Value Decomposition (SVD)

### Intuition

SVD is the generalization of eigendecomposition to **any** matrix (not just square). It reveals the fundamental geometry of a transformation:

> Every linear transformation can be decomposed into: **rotate → scale → rotate**

### Formal Definition

For any matrix A ∈ ℝᵐˣⁿ:

```
A = U · Σ · Vᵀ

where:
  U ∈ ℝᵐˣᵐ  — left singular vectors (orthogonal matrix)
  Σ ∈ ℝᵐˣⁿ  — singular values on diagonal (non-negative, sorted descending)
  Vᵀ ∈ ℝⁿˣⁿ — right singular vectors (orthogonal matrix)
```

### ASCII Diagram: SVD Structure

```
A = U  ·  Σ  ·  Vᵀ

m×n   m×m   m×n   n×n

┌   ┐   ┌   ┐   ┌σ₁        ┐   ┌   ┐
│   │   │   │   │  σ₂      │   │   │
│   │ = │ U │ · │    σ₃    │ · │Vᵀ │
│   │   │   │   │      ...  │   │   │
└   ┘   └   ┘   └          ┘   └   ┘

σ₁ ≥ σ₂ ≥ σ₃ ≥ ... ≥ 0

Low-rank approximation (keep top k singular values):

Aₖ = σ₁u₁v₁ᵀ + σ₂u₂v₂ᵀ + ... + σₖuₖvₖᵀ
     \_________________________________________/
       sum of k rank-1 matrices, best approximation of rank k
```

### Python Code

```python
import numpy as np
import matplotlib.pyplot as plt

# Generate a sample matrix
np.random.seed(42)
A = np.random.randn(5, 3)

# Full SVD
U, S, Vt = np.linalg.svd(A, full_matrices=True)
print(f"U shape: {U.shape}")   # (5, 5)
print(f"S shape: {S.shape}")   # (3,) — just the diagonal values
print(f"Vt shape: {Vt.shape}") # (3, 3)
print(f"Singular values: {S}")

# Reconstruct A
Sigma = np.zeros_like(A, dtype=float)
np.fill_diagonal(Sigma, S)
A_reconstructed = U @ Sigma @ Vt
print(f"Reconstructed correctly: {np.allclose(A, A_reconstructed)}")

# Economical/thin SVD (more practical)
U_thin, S_thin, Vt_thin = np.linalg.svd(A, full_matrices=False)
print(f"\nThin SVD shapes: U={U_thin.shape}, S={S_thin.shape}, Vt={Vt_thin.shape}")

# Low-rank approximation (image compression example)
# Simulate a 100x100 image
image = np.random.randn(100, 100)
U_img, S_img, Vt_img = np.linalg.svd(image, full_matrices=False)

for k in [1, 5, 10, 50]:
    A_k = U_img[:, :k] @ np.diag(S_img[:k]) @ Vt_img[:k, :]
    error = np.linalg.norm(image - A_k, 'fro') / np.linalg.norm(image, 'fro')
    compression = k * (100 + 1 + 100) / (100 * 100)
    print(f"k={k:3d}: relative error={error:.4f}, storage={compression:.3f}x")

# Explained variance ratio (like PCA)
variance_explained = S_img**2 / np.sum(S_img**2)
cumulative = np.cumsum(variance_explained)
k_95 = np.searchsorted(cumulative, 0.95) + 1
print(f"\nComponents needed for 95% variance: {k_95}")

# Moore-Penrose Pseudoinverse via SVD
# A⁺ = V Σ⁺ Uᵀ  where Σ⁺ = 1/σᵢ for σᵢ > 0
A_pinv_svd = Vt_thin.T @ np.diag(1/S_thin) @ U_thin.T
A_pinv_numpy = np.linalg.pinv(A)
print(f"Pseudoinverse matches: {np.allclose(A_pinv_svd, A_pinv_numpy)}")
```

### How This Connects to AI/ML

- **Recommender systems**: Matrix factorization for collaborative filtering. User-item matrix ≈ UΣVᵀ with low rank k.
- **LoRA (Low-Rank Adaptation)**: Fine-tuning LLMs by adding low-rank updates `ΔW = AB` (inspired by the observation that weight updates have low intrinsic rank).
- **GloVe word embeddings**: SVD on word co-occurrence matrix → dense word representations.
- **Latent Semantic Analysis (LSA)**: SVD on TF-IDF matrix for document similarity.
- **Truncated SVD / LSA in scikit-learn**: `sklearn.decomposition.TruncatedSVD` for sparse text data.
- **Image compression**: JPEG-like lossy compression via rank-k approximation.
- **Condition number**: `κ(A) = σ_max/σ_min` — measures sensitivity of linear system; high κ → ill-conditioned.

---

## 16. Principal Component Analysis (PCA)

### Intuition

PCA finds the directions of **maximum variance** in your data. It answers: "If I had to project my data onto k dimensions to preserve as much information as possible, which k directions should I choose?"

These directions are the **principal components**.

### ASCII Diagram: PCA Projection

```
Original 2D data             After PCA (rotated to PC axes)

    y                              PC2 (min variance)
    |  *                             |
    | * *                          * *
    |* * *           →           * * *
    |  * *                          * *
    |   *                            *
    +--------> x               ------+-------> PC1 (max variance)

PC1 = direction of maximum spread
PC2 = direction of maximum spread perpendicular to PC1

Data projected onto PC1 alone: best 1D summary
```

### Algorithm Steps

```
1. Center the data:     X_c = X - mean(X)
2. Compute covariance:  C = (1/(n-1)) · X_cᵀ · X_c
3. Eigendecompose:      C = V Λ Vᵀ   (Vᵀ = matrix of eigenvectors)
4. Sort by eigenvalue:  λ₁ ≥ λ₂ ≥ ... ≥ λₙ
5. Project:             X_pca = X_c · V[:, :k]   (keep top k components)
```

### Python Code

```python
import numpy as np
from sklearn.decomposition import PCA
from sklearn.datasets import load_iris

# Manual PCA implementation
def manual_pca(X, k):
    # Step 1: center
    X_c = X - X.mean(axis=0)

    # Step 2: covariance matrix
    n = X.shape[0]
    C = (X_c.T @ X_c) / (n - 1)

    # Step 3: eigendecomposition (use eigh for symmetric matrices)
    eigenvalues, eigenvectors = np.linalg.eigh(C)

    # Step 4: sort descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Step 5: project
    components = eigenvectors[:, :k]
    X_pca = X_c @ components

    # Explained variance ratio
    explained = eigenvalues / eigenvalues.sum()

    return X_pca, components, explained

# Load Iris dataset (4 features → 2 PCs)
iris = load_iris()
X = iris.data
y = iris.target

X_pca_manual, components, explained = manual_pca(X, k=2)
print(f"Explained variance ratio: {explained[:2]}")  # ~[0.925, 0.053]
print(f"Cumulative (top 2): {explained[:2].sum():.4f}")  # ~0.978

# Using scikit-learn (handles edge cases, more robust)
pca = PCA(n_components=2)
X_pca_sklearn = pca.fit_transform(X)
print(f"\nsklearn PCA explained variance: {pca.explained_variance_ratio_}")
print(f"Components shape: {pca.components_.shape}")  # (2, 4)

# Reconstruction from reduced dimensions
X_reconstructed = pca.inverse_transform(X_pca_sklearn)
reconstruction_error = np.mean((X - X_reconstructed)**2)
print(f"Reconstruction MSE: {reconstruction_error:.6f}")

# Scree plot (explained variance per component)
pca_full = PCA()
pca_full.fit(X)
print("\nVariance explained per component:")
for i, ev in enumerate(pca_full.explained_variance_ratio_):
    bar = '#' * int(ev * 50)
    print(f"PC{i+1}: {bar} {ev:.4f}")
```

### SVD Connection

PCA via SVD is numerically more stable than via the covariance matrix:

```python
# PCA via SVD (preferred for numerical stability)
X_c = X - X.mean(axis=0)
U, S, Vt = np.linalg.svd(X_c, full_matrices=False)

# Principal components = rows of Vt
# Projections = U * S (or equivalently X_c @ Vt.T)
X_pca_svd = X_c @ Vt[:2].T
print(f"PCA via SVD shape: {X_pca_svd.shape}")

# Singular values → eigenvalues of covariance matrix
n = X.shape[0]
eigenvalues_from_svd = S**2 / (n - 1)
```

### How This Connects to AI/ML

- **Dimensionality reduction**: Compress high-dimensional data (e.g., 1000-feature tabular dataset → 50 PCs) before training.
- **Visualization**: Project to 2D/3D for exploratory analysis (though t-SNE/UMAP often better for clusters).
- **Noise reduction**: Keeping top k PCs removes noise (low-variance directions often = noise).
- **Whitening**: Transform data so covariance = identity matrix (used before ICA, some deep learning preprocessing).
- **Representation probing**: In LLM research, PCA on hidden states reveals what information models encode.
- **Kernel PCA**: Nonlinear extension using the kernel trick — same math, operates in a feature space defined by a kernel function.

---

## 17. Tensor Operations

### Intuition

A tensor is a generalization of scalars, vectors, and matrices to arbitrary dimensions (called "axes" or "modes"):

```
Scalar:  rank-0 tensor   →  a single number:  x ∈ ℝ
Vector:  rank-1 tensor   →  1D array:         v ∈ ℝⁿ
Matrix:  rank-2 tensor   →  2D array:         A ∈ ℝᵐˣⁿ
Tensor:  rank-k tensor   →  kD array:         T ∈ ℝⁿ¹ˣⁿ²ˣ...ˣⁿᵏ
```

In deep learning, tensors are the fundamental data structure for EVERYTHING.

### Common Tensor Shapes in Deep Learning

| Data Type | Typical Shape | Axes |
|---|---|---|
| Grayscale image | `(H, W)` | height, width |
| Color image | `(H, W, C)` or `(C, H, W)` | height, width, channels |
| Image batch | `(N, C, H, W)` | batch, channels, height, width |
| Text sequence | `(N, L)` | batch, sequence length |
| Token embeddings | `(N, L, D)` | batch, seq_len, d_model |
| Video | `(N, T, C, H, W)` | batch, time, channels, h, w |

### Key Tensor Operations

```python
import numpy as np

# Tensor creation
T = np.random.randn(2, 3, 4)  # rank-3 tensor
print(f"Tensor shape: {T.shape}")  # (2, 3, 4)

# Reshape (view in PyTorch)
T_flat = T.reshape(2, 12)      # flatten last two dims
T_flat2 = T.reshape(-1, 4)     # -1 infers dimension
print(f"Reshaped: {T_flat.shape}")  # (2, 12)

# Transpose/permute axes
T_perm = T.transpose(0, 2, 1)  # swap axes 1 and 2
print(f"Permuted: {T_perm.shape}")  # (2, 4, 3)

# Squeeze and unsqueeze
v = np.array([1, 2, 3])        # shape (3,)
v_col = v[:, np.newaxis]       # shape (3, 1) — add axis
v_row = v[np.newaxis, :]       # shape (1, 3) — add axis
v_squeezed = v_col.squeeze()   # back to (3,)

# Broadcasting: automatic shape alignment
A = np.ones((3, 4))            # (3, 4)
b = np.array([1, 2, 3, 4])     # (4,)
C = A + b                      # broadcasts b to (3, 4)
print(f"After broadcast: {C.shape}")  # (3, 4)

# Einstein summation notation (einsum) — expressive and efficient
# Matrix multiply: ij,jk->ik
A = np.random.randn(3, 4)
B = np.random.randn(4, 5)
C = np.einsum('ij,jk->ik', A, B)
print(f"Matmul via einsum: {C.shape}")  # (3, 5)

# Batch matrix multiply: bij,bjk->bik
batch = 8
A_batch = np.random.randn(batch, 3, 4)
B_batch = np.random.randn(batch, 4, 5)
C_batch = np.einsum('bij,bjk->bik', A_batch, B_batch)
print(f"Batch matmul: {C_batch.shape}")  # (8, 3, 5)

# Outer product: i,j->ij
u = np.array([1, 2, 3])
v = np.array([4, 5])
outer = np.einsum('i,j->ij', u, v)
print(f"Outer product:\n{outer}")
# [[4, 5], [8, 10], [12, 15]]

# Trace: ii->  (sum of diagonal)
A_sq = np.random.randn(4, 4)
trace = np.einsum('ii->', A_sq)
print(f"Trace: {trace:.4f}")
print(f"Matches np.trace: {np.isclose(trace, np.trace(A_sq))}")

# Attention mechanism (full scaled dot-product attention)
def scaled_dot_product_attention(Q, K, V, mask=None):
    """
    Q, K, V: (batch, heads, seq_len, d_k)
    """
    d_k = Q.shape[-1]
    # Scores: (batch, heads, seq_len, seq_len)
    scores = np.einsum('bhid,bhjd->bhij', Q, K) / np.sqrt(d_k)
    if mask is not None:
        scores = np.where(mask, scores, -1e9)
    # Softmax over last axis
    exp_scores = np.exp(scores - scores.max(axis=-1, keepdims=True))
    attn_weights = exp_scores / exp_scores.sum(axis=-1, keepdims=True)
    # Output: (batch, heads, seq_len, d_k)
    output = np.einsum('bhij,bhjd->bhid', attn_weights, V)
    return output, attn_weights

# Test attention
batch, heads, seq_len, d_k = 2, 4, 8, 32
Q = np.random.randn(batch, heads, seq_len, d_k)
K = np.random.randn(batch, heads, seq_len, d_k)
V = np.random.randn(batch, heads, seq_len, d_k)
out, weights = scaled_dot_product_attention(Q, K, V)
print(f"\nAttention output: {out.shape}")   # (2, 4, 8, 32)
print(f"Attention weights: {weights.shape}") # (2, 4, 8, 8)
```

### How This Connects to AI/ML

- **Mini-batch training**: Every forward pass operates on a batch tensor `(N, ...)` for GPU parallelism.
- **Convolutional layers**: Convolution is a tensor contraction between input `(N,C,H,W)` and filter `(F,C,kH,kW)`.
- **Multi-head attention**: Requires batched tensor operations over heads simultaneously.
- **Einsum notation**: Used throughout PyTorch/TensorFlow internals; understanding it lets you implement custom operations efficiently.
- **Tensor decompositions**: CP/Tucker decompositions compress weight tensors in neural networks (model compression).

---

## 18. Quiz: 10 Questions with Solutions

**Instructions**: Try each question before reading the solution.

---

### Q1: Dot product and angle

> Vectors `a = [1, 0]` and `b = [1, 1]/√2`. What is `a·b` and what angle do they make?

**Solution**:
```
a·b = 1·(1/√2) + 0·(1/√2) = 1/√2 ≈ 0.707
|a| = 1, |b| = √(1/2 + 1/2) = 1
cos(θ) = (a·b)/(|a||b|) = 0.707/1 = 0.707
θ = arccos(0.707) = 45°
```
```python
import numpy as np
a = np.array([1, 0])
b = np.array([1, 1]) / np.sqrt(2)
print(np.degrees(np.arccos(np.dot(a, b))))  # 45.0
```

---

### Q2: Matrix multiplication

> Compute `A·B` where `A = [[1,2],[3,4]]` and `B = [[5,6],[7,8]]`.

**Solution**:
```
C[0,0] = 1·5 + 2·7 = 19
C[0,1] = 1·6 + 2·8 = 22
C[1,0] = 3·5 + 4·7 = 43
C[1,1] = 3·6 + 4·8 = 50
C = [[19, 22], [43, 50]]
```
```python
A = np.array([[1,2],[3,4]])
B = np.array([[5,6],[7,8]])
print(A @ B)  # [[19 22] [43 50]]
```

---

### Q3: Eigenvalues

> Find the eigenvalues of `A = [[2, 1], [1, 2]]`.

**Solution**:
```
det(A - λI) = det([[2-λ, 1], [1, 2-λ]])
            = (2-λ)² - 1 = 0
            = λ² - 4λ + 3 = 0
            = (λ-1)(λ-3) = 0
→ λ₁ = 1, λ₂ = 3
```
```python
A = np.array([[2., 1.], [1., 2.]])
print(np.linalg.eigvalsh(A))  # [1. 3.]
```

---

### Q4: Rank

> What is the rank of `A = [[1,2,3],[2,4,6],[1,2,4]]`?

**Solution**:
Row 2 = 2 × Row 1, so rows 1 and 2 are linearly dependent. Row 3 is independent of both. Rank = 2.
```python
A = np.array([[1,2,3],[2,4,6],[1,2,4]])
print(np.linalg.matrix_rank(A))  # 2
```

---

### Q5: L1 vs L2 norm

> Vector `v = [3, -4, 0, 0]`. Compute L1 and L2 norms. Which is larger?

**Solution**:
```
L1: |3| + |-4| + |0| + |0| = 7
L2: √(9 + 16 + 0 + 0) = √25 = 5
L1 > L2 (always true when there are non-zero components > 1)
```
```python
v = np.array([3., -4., 0., 0.])
print(f"L1={np.linalg.norm(v,1)}, L2={np.linalg.norm(v,2)}")  # L1=7.0, L2=5.0
```

---

### Q6: SVD rank-1 approximation

> For `A = [[3,0],[0,2]]`, what is the rank-1 SVD approximation?

**Solution**:
A is already diagonal. SVD: U=I, Σ=[[3,0],[0,2]], Vᵀ=I.
Rank-1 approximation = σ₁·u₁·v₁ᵀ = 3·[1,0]·[1,0]ᵀ = [[3,0],[0,0]]
```python
A = np.array([[3.,0.],[0.,2.]])
U, S, Vt = np.linalg.svd(A)
A1 = S[0] * np.outer(U[:,0], Vt[0,:])
print(A1)  # [[3. 0.] [0. 0.]]
```

---

### Q7: Orthogonality

> Vectors `u=[1,1,0]/√2` and `v=[1,-1,0]/√2`. Are they orthogonal? Compute `u·v`.

**Solution**:
```
u·v = (1/√2)(1/√2) + (1/√2)(-1/√2) + 0·0
    = 1/2 - 1/2 = 0   → YES, orthogonal
```

---

### Q8: Determinant interpretation

> Matrix `A = [[2,0],[0,3]]`. What does `det(A)=6` mean geometrically?

**Solution**: A is a scaling matrix that stretches the x-axis by 2 and y-axis by 3. Any region in the plane gets scaled by a factor of 6 (= 2×3) in area. A unit square becomes a 2×3 rectangle.

---

### Q9: PCA variance

> A dataset has covariance matrix eigenvalues `[8.5, 1.2, 0.2, 0.1]`. How many PCs explain >95% of variance?

**Solution**:
```
Total variance = 8.5 + 1.2 + 0.2 + 0.1 = 10.0
PC1: 8.5/10 = 85%
PC1+PC2: 9.7/10 = 97% > 95%
→ 2 principal components suffice
```

---

### Q10: Gradient as vector

> Loss `L = w₁² + 2w₂² + w₁w₂`. Compute the gradient vector at `w = [1, 1]`.

**Solution**:
```
∂L/∂w₁ = 2w₁ + w₂   →  at [1,1]: 2·1 + 1 = 3
∂L/∂w₂ = 4w₂ + w₁   →  at [1,1]: 4·1 + 1 = 5
∇L = [3, 5]

Gradient descent step (α=0.1):
w_new = [1,1] - 0.1·[3,5] = [0.7, 0.5]
```

---

## 19. Exercises: 5 Practical Problems

### Exercise 1: Image Compression via SVD

**Problem**: Load a grayscale image (or simulate one), apply SVD, and plot the reconstruction quality vs. number of singular values. Find the minimum k to achieve < 5% reconstruction error.

**Solution**:
```python
import numpy as np

# Simulate a structured image (rank-deficient by design)
np.random.seed(0)
true_rank = 20
m, n = 200, 150
U_true = np.linalg.qr(np.random.randn(m, true_rank))[0]
V_true = np.linalg.qr(np.random.randn(n, true_rank))[0]
S_true = np.sort(np.random.uniform(1, 100, true_rank))[::-1]
image = U_true @ np.diag(S_true) @ V_true.T + 0.5*np.random.randn(m, n)

# SVD decomposition
U, S, Vt = np.linalg.svd(image, full_matrices=False)
total_energy = np.linalg.norm(image, 'fro')**2

print(f"Image shape: {image.shape}")
print(f"Max singular values: {S[:5]}")

results = []
for k in range(1, min(50, len(S))+1):
    A_k = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
    rel_error = np.linalg.norm(image - A_k, 'fro') / np.linalg.norm(image, 'fro')
    results.append((k, rel_error))
    if rel_error < 0.05:
        print(f"k={k} achieves {rel_error*100:.2f}% relative error (<5%)")
        break

for k, err in results[::5]:
    bar = '#' * int((1-err)*30)
    print(f"k={k:3d}: error={err:.4f}  [{bar}]")
```

---

### Exercise 2: Build PCA from Scratch and Validate

**Problem**: Implement PCA from scratch using eigendecomposition. Validate by comparing with `sklearn.decomposition.PCA` on the Iris dataset. Report explained variance for each component.

**Solution**:
```python
import numpy as np
from sklearn.decomposition import PCA
from sklearn.datasets import load_iris

iris = load_iris()
X = iris.data.astype(float)

# Scratch implementation
def pca_scratch(X, n_components):
    X_c = X - X.mean(axis=0)
    C = X_c.T @ X_c / (len(X) - 1)
    vals, vecs = np.linalg.eigh(C)
    # Sort descending
    idx = np.argsort(vals)[::-1]
    vals, vecs = vals[idx], vecs[:, idx]
    explained = vals / vals.sum()
    X_proj = X_c @ vecs[:, :n_components]
    return X_proj, vecs[:, :n_components], explained

X_proj, components, explained = pca_scratch(X, 2)
print("Scratch PCA explained variance:", explained[:4])

# Validate
pca = PCA(n_components=2)
X_sklearn = pca.fit_transform(X)
print("sklearn PCA explained variance:", pca.explained_variance_ratio_)

# Projections may differ by sign (eigenvectors have arbitrary sign)
for i in range(2):
    corr = np.corrcoef(X_proj[:, i], X_sklearn[:, i])[0, 1]
    print(f"PC{i+1} correlation (scratch vs sklearn): {abs(corr):.6f}")  # should be ~1.0
```

---

### Exercise 3: Implement Linear Regression via Normal Equations

**Problem**: Implement linear regression using the normal equation `w = (XᵀX)⁻¹Xᵀy`. Generate synthetic data with known true weights, add noise, and compare recovered weights vs. true weights.

**Solution**:
```python
import numpy as np

np.random.seed(42)
n_samples, n_features = 500, 5
true_w = np.array([2.5, -1.3, 0.8, 3.1, -0.5])
true_b = 1.7

X = np.random.randn(n_samples, n_features)
y = X @ true_w + true_b + 0.5 * np.random.randn(n_samples)

# Add bias column
X_aug = np.hstack([X, np.ones((n_samples, 1))])  # (500, 6)

# Normal equations: w = (XᵀX)⁻¹Xᵀy
# (using lstsq for numerical stability — equivalent but more robust)
w_hat, _, _, _ = np.linalg.lstsq(X_aug, y, rcond=None)
w_recovered, b_recovered = w_hat[:-1], w_hat[-1]

print("True weights:      ", true_w)
print("Recovered weights: ", np.round(w_recovered, 4))
print(f"True bias: {true_b}, Recovered bias: {b_recovered:.4f}")
print(f"Max weight error: {np.max(np.abs(w_recovered - true_w)):.6f}")

# Compute R²
y_pred = X_aug @ w_hat
ss_res = np.sum((y - y_pred)**2)
ss_tot = np.sum((y - y.mean())**2)
r2 = 1 - ss_res/ss_tot
print(f"R² score: {r2:.6f}")  # should be close to 1.0
```

---

### Exercise 4: Cosine Similarity in Word Embeddings

**Problem**: Given a small set of word vectors, compute a cosine similarity matrix. Find which word is most similar to "king" after applying the analogy `king - man + woman`.

**Solution**:
```python
import numpy as np

# Toy word embeddings (normally 300-dimensional GloVe vectors)
words = ['king', 'queen', 'man', 'woman', 'prince', 'princess']
np.random.seed(7)
embeddings_base = {
    'king':     np.array([0.9, 0.7, 0.1, 0.8]),
    'queen':    np.array([0.8, 0.7, 0.9, 0.8]),
    'man':      np.array([0.9, 0.2, 0.1, 0.2]),
    'woman':    np.array([0.8, 0.2, 0.9, 0.2]),
    'prince':   np.array([0.7, 0.5, 0.1, 0.6]),
    'princess': np.array([0.6, 0.5, 0.9, 0.6]),
}

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

# Cosine similarity matrix
E = np.array([embeddings_base[w] for w in words])
n = len(words)
sim_matrix = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        sim_matrix[i, j] = cosine_similarity(E[i], E[j])

print("Cosine similarity matrix:")
header = "       " + "  ".join(f"{w[:6]:6s}" for w in words)
print(header)
for i, w in enumerate(words):
    row = f"{w[:6]:8s}" + "  ".join(f"{sim_matrix[i,j]:.3f}" for j in range(n))
    print(row)

# Analogy: king - man + woman ≈ ?
analogy_vec = embeddings_base['king'] - embeddings_base['man'] + embeddings_base['woman']
sims = {w: cosine_similarity(analogy_vec, embeddings_base[w]) for w in words}
best_word = max((w for w in words if w not in ['king', 'man', 'woman']),
                key=lambda w: sims[w])
print(f"\nking - man + woman ≈ {best_word} (similarity={sims[best_word]:.4f})")
```

---

### Exercise 5: Power Iteration for Dominant Eigenvector

**Problem**: Implement the power iteration algorithm to find the dominant eigenvector (largest eigenvalue) of a matrix. Verify convergence against `numpy.linalg.eig`.

**Solution**:
```python
import numpy as np

def power_iteration(A, n_iterations=1000, tol=1e-10):
    """
    Find the dominant eigenvector of A via power iteration.
    Works for matrices where largest eigenvalue is strictly dominant.
    """
    n = A.shape[0]
    # Start with random vector
    v = np.random.randn(n)
    v = v / np.linalg.norm(v)

    eigenvalue_prev = 0
    for i in range(n_iterations):
        # Matrix-vector product
        Av = A @ v
        # Rayleigh quotient: best eigenvalue estimate
        eigenvalue = v @ Av
        # Normalize
        v = Av / np.linalg.norm(Av)

        if abs(eigenvalue - eigenvalue_prev) < tol:
            print(f"Converged at iteration {i+1}")
            break
        eigenvalue_prev = eigenvalue

    return eigenvalue, v

# Test on a symmetric positive definite matrix
np.random.seed(42)
A_rand = np.random.randn(6, 6)
A = A_rand.T @ A_rand  # symmetric positive definite

lambda_power, v_power = power_iteration(A)
print(f"Power iteration eigenvalue: {lambda_power:.8f}")
print(f"Power iteration eigenvector (first 3): {v_power[:3]}")

# Verify with numpy
eigenvalues, eigenvectors = np.linalg.eigh(A)
lambda_true = eigenvalues[-1]  # eigh sorts ascending
v_true = eigenvectors[:, -1]

print(f"NumPy eigenvalue:           {lambda_true:.8f}")
print(f"Eigenvalue error: {abs(lambda_power - lambda_true):.2e}")

# Eigenvectors may differ by sign
overlap = abs(np.dot(v_power, v_true))
print(f"Eigenvector overlap |v·v_true| = {overlap:.8f}")  # should be ~1.0
```

---

## 20. Learning Resources

### Free Resources

| Resource | Description | Best For |
|---|---|---|
| **3Blue1Brown: Essence of Linear Algebra** (YouTube) | Visual, intuitive 15-video series; best introduction to geometric intuition | Building intuition from scratch |
| **Gilbert Strang: MIT 18.06 Linear Algebra** (MIT OCW) | The gold standard university course; rigorous yet accessible | Deep theoretical understanding |
| **Mathematics for Machine Learning** (mml-book.github.io) | Free PDF; bridges pure linear algebra to ML applications directly | ML practitioners |
| **Khan Academy Linear Algebra** | Self-paced, interactive; excellent for fundamentals | Beginners and review |
| **Goodfellow et al. "Deep Learning" Chapter 2** (deeplearningbook.org) | Terse but complete reference for DL-relevant linear algebra | Quick DL-specific reference |
| **fast.ai Computational Linear Algebra** (GitHub + YouTube) | Practical, numerical focus; uses Python throughout | Applied/numerical methods |

### Paid / Structured Courses

| Resource | Platform | Cost | Best For |
|---|---|---|---|
| **Mathematics for Machine Learning Specialization** | Coursera (Imperial College) | ~$49/month | Structured learning with graded projects |
| **Deep Learning Specialization** (Andrew Ng) | Coursera (deeplearning.ai) | ~$49/month | Linear algebra in deep learning context |
| **Computational Linear Algebra** (fast.ai) | fast.ai | Free (but has paid course materials) | Applied practitioners |

### Books

| Book | Authors | Level | Notes |
|---|---|---|---|
| *Introduction to Linear Algebra* | Gilbert Strang | Undergraduate | Pairs with MIT OCW lectures |
| *Mathematics for Machine Learning* | Deisenroth, Faisal, Ong | Intermediate | Free PDF; ML-focused |
| *Matrix Analysis* | Horn & Johnson | Graduate | Comprehensive reference |
| *Numerical Linear Algebra* | Trefethen & Bau | Graduate | Computational focus, SVD/QR in depth |

### Practice Tools

```
- NumPy documentation:    numpy.org/doc
- SciPy linalg:           docs.scipy.org/doc/scipy/reference/linalg.html
- 3b1b Manim (animate):   github.com/3b1b/manim
- Wolfram Alpha:          wolframalpha.com  (verify by-hand calculations)
- Jupyter + matplotlib:   for interactive exploration
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                   LINEAR ALGEBRA CHEAT SHEET                    │
├─────────────────────────────┬───────────────────────────────────┤
│ VECTORS                     │ MATRICES                          │
│ |v|₂ = √(Σvᵢ²)             │ (AB)ᵀ = BᵀAᵀ                    │
│ u·v = Σuᵢvᵢ = |u||v|cosθ  │ (AB)⁻¹ = B⁻¹A⁻¹                 │
│ proj_v(u) = (u·v/v·v)v     │ det(AB) = det(A)det(B)           │
│ cos_sim = u·v/(|u||v|)     │ rank(AB) ≤ min(rank(A),rank(B))  │
├─────────────────────────────┼───────────────────────────────────┤
│ EIGENDECOMPOSITION          │ SVD                               │
│ Av = λv                    │ A = UΣVᵀ                         │
│ det(A-λI) = 0              │ Aₖ = Σᵢ₌₁ᵏ σᵢuᵢvᵢᵀ             │
│ A = VΛV⁻¹ (diagonalizable)│ A⁺ = VΣ⁺Uᵀ (pseudoinverse)      │
│ A = QΛQᵀ (symmetric)      │ κ(A) = σ_max/σ_min               │
├─────────────────────────────┼───────────────────────────────────┤
│ NORMS (Regularization)      │ PCA                               │
│ L1: Σ|vᵢ| → sparsity       │ C = XᵀX/(n-1)                   │
│ L2: √(Σvᵢ²) → smoothness  │ C = QΛQᵀ                         │
│ Frobenius: √(ΣΣaᵢⱼ²)       │ X_pca = X_c · Q[:, :k]          │
│ Nuclear: Σσᵢ → low rank    │ var_explained = λᵢ/Σλ            │
└─────────────────────────────┴───────────────────────────────────┘
```

---

*Last updated: 2026-06-29 | Part of the AI/ML Math Foundations series*

*Next: [02-calculus-optimization.md](02-calculus-optimization.md) — Derivatives, Gradients, Backpropagation*
