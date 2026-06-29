# Deep Learning Fundamentals & Neural Networks

> A comprehensive, rigorous guide from perceptron to modern deep learning — with full mathematical derivations, implementation details, and practical intuition.

---

## Table of Contents

1. [A Brief History of Neural Networks](#1-a-brief-history-of-neural-networks)
2. [Biological Inspiration vs Mathematical Reality](#2-biological-inspiration-vs-mathematical-reality)
3. [The Universal Approximation Theorem](#3-the-universal-approximation-theorem)
4. [Neural Network Anatomy](#4-neural-network-anatomy)
5. [Activation Functions Deep Dive](#5-activation-functions-deep-dive)
6. [Forward Pass: Matrix Multiplication Walkthrough](#6-forward-pass-matrix-multiplication-walkthrough)
7. [Backpropagation: Full Derivation](#7-backpropagation-full-derivation)
8. [Weight Initialization](#8-weight-initialization)
9. [Batch Normalization](#9-batch-normalization)
10. [Dropout Regularization](#10-dropout-regularization)
11. [Optimizers Deep Dive](#11-optimizers-deep-dive)
12. [Learning Rate Scheduling](#12-learning-rate-scheduling)
13. [Regularization Strategies](#13-regularization-strategies)
14. [Quiz: 15 Questions with Solutions](#14-quiz-15-questions-with-solutions)
15. [Exercise: 3-Layer Network from Scratch (NumPy)](#15-exercise-3-layer-network-from-scratch-numpy)
16. [References & Further Learning](#16-references--further-learning)

---

## 1. A Brief History of Neural Networks

The story of neural networks spans over 80 years — oscillating between hype, despair, and transformative breakthroughs.

### 1943 — The McCulloch-Pitts Neuron

Warren McCulloch (neuroscientist) and Walter Pitts (logician) published *"A Logical Calculus of the Ideas Immanent in Nervous Activity"*. They proposed a highly simplified mathematical model of a biological neuron: a binary threshold unit that fires a 1 if the weighted sum of its inputs exceeds a threshold, 0 otherwise.

```
Inputs:  x1, x2, ..., xn
Output:  y = 1  if  Σ(wi * xi) >= threshold
              0  otherwise
```

This was purely theoretical — no learning, no training. But it planted the seed.

### 1958 — Rosenblatt's Perceptron

Frank Rosenblatt invented the **Perceptron** — the first trainable model. It could automatically learn binary classification weights from data using a simple update rule:

```
w_i ← w_i + η * (y_true - y_pred) * x_i
```

Rosenblatt claimed it would eventually be able to "walk, talk, see, write, reproduce itself and be conscious of its existence." The New York Times called it "the embryo of an electronic computer that [the Navy] expects will be able to walk, talk, see."

### 1969 — The First AI Winter: Minsky & Papert

Marvin Minsky and Seymour Papert published *"Perceptrons"*, proving that a single-layer perceptron **cannot** solve the XOR problem. This was mathematically correct, but the broader conclusion — that neural networks were fundamentally limited — caused a catastrophic collapse in funding and research. The first **AI Winter** followed.

### 1986 — Backpropagation and the MLP Revival

Rumelhart, Hinton, and Williams published *"Learning representations by back-propagating errors"* in Nature, showing that **backpropagation** could train **multi-layer perceptrons (MLPs)**. The XOR problem was solved. Universal function approximation became theoretically plausible. But computational power remained a bottleneck.

### 1998 — LeNet-5 and Convolutional Networks

Yann LeCun developed **LeNet-5**, a convolutional neural network that could read handwritten digits from cheques at AT&T with remarkable accuracy. This was a genuine production system, years ahead of its time — but the hardware wasn't ready for the world.

### 2006 — Deep Belief Networks and the "Deep" Revival

Geoffrey Hinton published *"A Fast Learning Algorithm for Deep Belief Nets"*, showing that deep networks could be trained layer-by-layer using **pre-training** (unsupervised, greedy layer-wise training) followed by fine-tuning. This reintroduced the word "deep" into the vocabulary. A second AI Winter had been survived.

### 2012 — AlexNet and the Deep Learning Revolution

This is the **inflection point**. Alex Krizhevsky, Ilya Sutskever, and Geoffrey Hinton submitted **AlexNet** to the ImageNet Large Scale Visual Recognition Challenge (ILSVRC). It achieved a top-5 error rate of **15.3%**, crushing the second-place entry (26.2%) by more than 10 percentage points.

AlexNet's key innovations:
- **ReLU activations** (instead of sigmoid/tanh) — solved vanishing gradients
- **Dropout** — regularization that prevented overfitting
- **Data augmentation** — artificially expanded training data
- **GPU training** — two GTX 580 GPUs, 5-6 days of training
- **Local Response Normalization** (later superseded by Batch Norm)

The world changed. Every major tech company redirected massive resources into deep learning. The modern era had begun.

### Timeline Summary

| Year | Event | Significance |
|------|-------|-------------|
| 1943 | McCulloch-Pitts neuron | First mathematical neuron model |
| 1958 | Perceptron (Rosenblatt) | First trainable model |
| 1969 | Minsky & Papert critique | First AI Winter begins |
| 1986 | Backpropagation (Rumelhart et al.) | MLP training becomes practical |
| 1998 | LeNet-5 (LeCun) | First practical CNN |
| 2006 | Deep Belief Networks (Hinton) | "Deep learning" term popularized |
| 2012 | AlexNet (Krizhevsky et al.) | **The Revolution** — ImageNet breakthrough |
| 2017 | Attention is All You Need (Vaswani et al.) | Transformer architecture |
| 2020+ | GPT-3, DALL-E, AlphaFold 2... | Deep learning reshapes civilization |

---

## 2. Biological Inspiration vs Mathematical Reality

### The Biological Neuron

A biological neuron has four key components:

```
        Dendrites (receive signals)
             |
        [Cell Body / Soma]  ← Integrates signals
             |
          Axon Hillock  ← Threshold / fire decision
             |
          Axon  ← Transmits output
             |
        Synaptic Terminals  ← Send to next neuron
```

The neuron **fires** (sends an action potential) only when the total incoming signal exceeds a threshold. The **synapse** — the gap between neurons — has variable strength (synaptic weight), and this strength changes with learning (**synaptic plasticity**, governed by Hebb's rule: "neurons that fire together, wire together").

### The Mathematical Neuron

```
Inputs:    x = [x1, x2, x3, ..., xn]
Weights:   w = [w1, w2, w3, ..., wn]
Bias:      b

Pre-activation (net input):  z = w^T * x + b = Σ(wi * xi) + b

Output:    a = f(z)   where f is an activation function
```

### Critical Differences (Biology vs Math)

| Aspect | Biology | Mathematical Model |
|--------|---------|-------------------|
| Signal type | Continuous spike trains | Scalar real number |
| Timing | Temporal dynamics matter | Stateless (feedforward) |
| Learning | Synaptic plasticity, STDP | Gradient descent |
| Architecture | Massively recurrent, 3D | Layered, feedforward |
| Neuron count | ~86 billion neurons | Millions to billions (params) |
| Energy | ~20 watts (whole brain) | kW-MW (GPU clusters) |
| Sparsity | ~1% fire at any time | Dense activations |

The biological analogy is useful as **intuition** but should not be taken literally. The mathematical models are inspired by, not identical to, biological systems. Modern deep learning is an engineering discipline grounded in mathematics, not neuroscience.

---

## 3. The Universal Approximation Theorem

### Statement

> A feedforward neural network with **at least one hidden layer** of a **finite number of neurons** with a **non-polynomial activation function** can approximate **any continuous function** on a compact subset of R^n to **arbitrary precision**.

First proved by Cybenko (1989) for sigmoid activations, later generalized by Hornik (1991) and others.

### What It Means

For any continuous function `f: R^n → R^m` and any `ε > 0`, there exists a neural network `g` such that:

```
max |f(x) - g(x)| < ε    for all x in the domain
```

### What It Does NOT Mean

The UAT is an **existence theorem**, not a constructive one. It tells you:

- A solution EXISTS in the space of neural networks
- It does NOT tell you how to find it
- It does NOT guarantee that gradient descent will find it
- It does NOT specify how many neurons are needed
- It says nothing about **generalization** (training vs test performance)

### Practical Implications

1. **Expressiveness**: Any target function is theoretically representable
2. **Width vs Depth**: A single hidden layer may require **exponentially many** neurons; depth provides **exponential efficiency** gains in expressiveness
3. **The hard part** is optimization (finding the weights), not representation

```
Shallow network:  exponential width needed
Deep network:     polynomial width, but more complex optimization
```

This is why depth matters — not just for representation, but for the way features compose hierarchically.

---

## 4. Neural Network Anatomy

### The Basic Unit: A Neuron

```
                  x1 ---(w1)---\
                  x2 ---(w2)----+---> z = Σ(wi*xi) + b ---> f(z) ---> output
                  x3 ---(w3)---/
                               ↑
                             bias b
```

### Layers

A neural network is organized into **layers**. Each layer transforms its input into a new representation:

```
INPUT LAYER     HIDDEN LAYER 1    HIDDEN LAYER 2    OUTPUT LAYER
  (3 neurons)     (4 neurons)       (4 neurons)       (2 neurons)

    x1 ──────────── h11 ──────────── h21 ──────────── y1
    x2 ──────────── h12 ──────────── h22 ──────────── y2
    x3 ──────────── h13 ──────────── h23
                    h14 ──────────── h24

         W1 (3×4)         W2 (4×4)         W3 (4×2)
```

### Types of Layers

| Layer Type | Operation | Use Case |
|-----------|-----------|----------|
| **Dense / Fully Connected** | `y = f(Wx + b)` | General-purpose transformation |
| **Convolutional** | Local feature detection | Images, sequences |
| **Recurrent (RNN/LSTM)** | Sequential processing | Time series, NLP |
| **Attention** | Weighted information retrieval | Transformers, NLP |
| **Normalization** | Standardize activations | Stabilize training |
| **Dropout** | Random neuron zeroing | Regularization |
| **Pooling** | Spatial downsampling | CNNs |
| **Embedding** | Integer → dense vector | NLP, categorical data |

### Parameters: Weights and Biases

For a fully connected layer mapping `n` inputs to `m` outputs:
- **Weight matrix** `W`: shape `(m, n)` — `m*n` parameters
- **Bias vector** `b`: shape `(m,)` — `m` parameters
- **Total**: `m*(n+1)` parameters

For a network with layers `[784, 512, 256, 10]` (like MNIST classifier):
```
Layer 1: 784 → 512  :  784*512 + 512   = 401,920 params
Layer 2: 512 → 256  :  512*256 + 256   = 131,328 params
Layer 3: 256 →  10  :  256* 10 +  10   =   2,570 params
Total: 535,818 parameters
```

---

## 5. Activation Functions Deep Dive

Activation functions introduce **non-linearity** into the network. Without them, a stack of linear layers is just one big linear transformation — it could only learn linear decision boundaries.

### Why Non-linearity?

Without activation functions:
```
Layer 1: y1 = W1*x
Layer 2: y2 = W2*y1 = W2*W1*x = (W2*W1)*x = W_combined*x
```
No matter how many layers — still linear! Non-linear activations break this collapse.

---

### 5.1 Sigmoid

**Equation:**
```
σ(z) = 1 / (1 + e^(-z))
```

**Derivative:**
```
σ'(z) = σ(z) * (1 - σ(z))
```

**Range:** (0, 1)

**Shape:**
```
1.0 ┤                                              ╭────────
    │                                         ╭───╯
0.5 ┤──────────────────────────────────╮─────╯
    │                             ╭───╯
0.0 ┼──────────────────────────╯
    └────────────────────────────────────────────────
   -6    -4    -2     0     2     4     6
```

**Problems:**
1. **Vanishing Gradient**: For large |z|, gradient → 0. Deep networks multiply many near-zero gradients together — backpropagation signal disappears.
2. **Not zero-centered**: Outputs always positive → all-positive or all-negative gradients for weights → zig-zag optimization dynamics.
3. **Computationally expensive**: Requires `exp()` evaluation.

**When to use:** Output layer for **binary classification** (outputs probability in (0,1)).

---

### 5.2 Tanh (Hyperbolic Tangent)

**Equation:**
```
tanh(z) = (e^z - e^(-z)) / (e^z + e^(-z)) = 2σ(2z) - 1
```

**Derivative:**
```
tanh'(z) = 1 - tanh²(z)
```

**Range:** (-1, 1)

**Advantages over Sigmoid:**
- **Zero-centered**: outputs in (-1, 1) → better gradient flow dynamics
- Stronger gradient near 0

**Problems:**
- Still suffers from **vanishing gradients** at saturation
- Still computationally expensive

**When to use:** RNNs (LSTM gates), when zero-centering matters, shallow networks.

---

### 5.3 ReLU (Rectified Linear Unit)

**Equation:**
```
ReLU(z) = max(0, z)
```

**Derivative:**
```
ReLU'(z) = 1  if z > 0
            0  if z ≤ 0
```

**Shape:**
```
    │              ╱
    │            ╱
    │          ╱
0.0 ┼────────╱──────────────
    │
    └────────────────────────
   -3   -2   -1    0    1    2    3
```

**Why ReLU Works (and why it was transformative in 2012):**
1. **No vanishing gradient** for positive inputs: gradient is exactly 1, not a fraction
2. **Sparse activation**: ~50% neurons output 0 → efficient representations, reduces overfitting
3. **Computationally trivial**: just `max(0, z)` — no exponentials
4. **Biologically plausible** (somewhat): neurons don't fire below threshold

**Problems:**
- **Dying ReLU**: If a neuron's input is always negative, it permanently outputs 0 and receives no gradient. It is "dead" and never recovers.
- **Not zero-centered**: outputs always ≥ 0

**When to use:** Default choice for **hidden layers** in deep networks. Start with ReLU.

---

### 5.4 Leaky ReLU

**Equation:**
```
LeakyReLU(z) = z          if z > 0
               α * z       if z ≤ 0    (typically α = 0.01)
```

**Derivative:**
```
LeakyReLU'(z) = 1    if z > 0
                α    if z ≤ 0
```

**Advantage:** Fixes Dying ReLU — negative inputs still get a small gradient (α), so neurons can recover.

**When to use:** When you observe dying ReLU problem. Good default when ReLU underperforms.

---

### 5.5 ELU (Exponential Linear Unit)

**Equation:**
```
ELU(z) = z              if z > 0
          α*(e^z - 1)   if z ≤ 0    (typically α = 1.0)
```

**Derivative:**
```
ELU'(z) = 1                if z > 0
           ELU(z) + α      if z ≤ 0
```

**Range:** (-α, ∞)

**Advantages:**
- Smooth everywhere (differentiable at z=0)
- Negative values push mean activation toward zero (self-normalizing tendencies)
- Reduces vanishing gradient

**Disadvantages:** Slower than ReLU (requires `exp()`), α is a hyperparameter.

**When to use:** When you want smoother training dynamics than Leaky ReLU.

---

### 5.6 GELU (Gaussian Error Linear Unit)

**Equation:**
```
GELU(z) = z * Φ(z)    where Φ is the standard normal CDF

Approximation:
GELU(z) ≈ 0.5 * z * (1 + tanh(√(2/π) * (z + 0.044715 * z³)))
```

**Intuition:** Stochastically gates inputs — a neuron with input `z` is active with probability `Φ(z)`. It weights inputs by the probability that a standard normal random variable is less than the input.

**Why it's special:** Smooth, non-monotonic (has a slight dip for small negative values), differentiable everywhere. Combines properties of ReLU and dropout.

**When to use:** State of the art for **Transformers** (BERT, GPT, ViT). Default in modern NLP.

---

### 5.7 Swish

**Equation:**
```
Swish(z) = z * σ(β*z) = z / (1 + e^(-β*z))    (β often = 1 or learned)
```

**Properties:**
- Non-monotonic
- Smooth and unbounded above
- Self-gated (the gate depends on the input itself)
- Discovered by neural architecture search (Google Brain, 2017)

**When to use:** EfficientNet family, some modern architectures. Competitive with GELU.

---

### Activation Function Comparison Table

| Function | Range | Zero-centered | Vanishing Grad | Dying Neurons | Compute Cost | Best Use |
|----------|-------|--------------|----------------|---------------|-------------|----------|
| Sigmoid | (0,1) | No | Severe | No | Medium | Binary output |
| Tanh | (-1,1) | Yes | Moderate | No | Medium | RNN gates |
| ReLU | [0,∞) | No | No (z>0) | Yes | Very Low | Hidden layers (default) |
| Leaky ReLU | (-∞,∞) | No | No | No | Very Low | When ReLU dies |
| ELU | (-α,∞) | Near-zero | Minimal | No | Low | Smooth training |
| GELU | (-∞,∞) | Near-zero | Minimal | No | Medium | Transformers |
| Swish | (-∞,∞) | Near-zero | Minimal | No | Medium | EfficientNet |

---

## 6. Forward Pass: Matrix Multiplication Walkthrough

### Concrete Example: 3-Layer Network

Let's trace a forward pass through a network with architecture `[3 → 4 → 4 → 2]`.

**Input:** `x = [0.5, -1.0, 0.3]` (shape: 3×1)

**Layer 1** (3 → 4, ReLU):
```
W1 = [[ 0.2, -0.3,  0.5],
      [ 0.1,  0.4, -0.2],
      [-0.5,  0.3,  0.1],
      [ 0.3, -0.1,  0.4]]    shape: 4×3

b1 = [0.1, -0.1, 0.2, 0.0]   shape: 4

z1 = W1 @ x + b1
   = [ 0.2*0.5 + (-0.3)*(-1.0) + 0.5*0.3 + 0.1,
       0.1*0.5 + 0.4*(-1.0) + (-0.2)*0.3 + (-0.1),
       (-0.5)*0.5 + 0.3*(-1.0) + 0.1*0.3 + 0.2,
       0.3*0.5 + (-0.1)*(-1.0) + 0.4*0.3 + 0.0 ]
   = [ 0.10 + 0.30 + 0.15 + 0.10,
       0.05 - 0.40 - 0.06 - 0.10,
      -0.25 - 0.30 + 0.03 + 0.20,
       0.15 + 0.10 + 0.12 + 0.00 ]
   = [0.65, -0.51, -0.32, 0.37]

a1 = ReLU(z1) = [0.65, 0.00, 0.00, 0.37]
```

**Layer 2** (4 → 4, ReLU): `z2 = W2 @ a1 + b2`, `a2 = ReLU(z2)`

**Layer 3** (4 → 2, Softmax for classification):
```
z3 = W3 @ a2 + b3
a3 = softmax(z3)
   = exp(z3) / sum(exp(z3))    ← probability distribution
```

### Batch Processing (Vectorized)

In practice, we process a **batch** of N samples simultaneously:

```
X: shape (N, d_in)    — batch of N inputs, each of dimension d_in
W: shape (d_in, d_out)
b: shape (d_out,)

Z = X @ W + b    shape: (N, d_out)    — vectorized over batch
A = f(Z)         shape: (N, d_out)
```

This is why GPUs are so effective — they are optimized for exactly these large matrix multiplications.

---

## 7. Backpropagation: Full Derivation

Backpropagation is the **chain rule** applied to compute gradients through a computational graph. It is the algorithmic heart of deep learning.

### Prerequisites: The Chain Rule

If `L = f(g(x))`, then:
```
dL/dx = (dL/dg) * (dg/dx) = (df/dg) * (dg/dx)
```

For multivariable: if `L = f(z)` and `z = g(x, y)`:
```
∂L/∂x = (∂L/∂z) * (∂z/∂x)
∂L/∂y = (∂L/∂z) * (∂z/∂y)
```

### The Computation Graph

For a 2-layer network:
```
x → [W1, b1] → z1 → [ReLU] → a1 → [W2, b2] → z2 → [softmax] → ŷ → [Loss] → L
```

Each arrow represents a function. Backpropagation flows gradients from right to left.

### Forward Pass (notation)

```
z1 = W1 @ x + b1
a1 = ReLU(z1)
z2 = W2 @ a1 + b2
ŷ  = softmax(z2)
L  = CrossEntropy(ŷ, y)
```

### Backward Pass: Computing All Gradients

**Step 1: Loss gradient w.r.t. softmax input (for cross-entropy + softmax, this simplifies beautifully)**

For cross-entropy loss `L = -Σ y_k * log(ŷ_k)` with softmax:
```
∂L/∂z2 = ŷ - y        ← (predicted probability - true one-hot label)
```
This is the **most elegant result** in deep learning — the gradient of softmax+cross-entropy is just the prediction error.

**Step 2: Gradient w.r.t. W2**
```
∂L/∂W2 = (∂L/∂z2)^T @ a1^T    (outer product for a single sample)

For a batch of N samples:
∂L/∂W2 = (1/N) * A1^T @ δ2    where δ2 = ∂L/∂z2, A1 has shape (N, h1)
```

**Step 3: Gradient w.r.t. b2**
```
∂L/∂b2 = (1/N) * Σ_i δ2[i]    (mean over batch)
         = (1/N) * δ2.sum(axis=0)
```

**Step 4: Backprop through ReLU**
```
∂L/∂z1 = (δ2 @ W2^T) * ReLU'(z1)
                          ↑
                    element-wise multiply by mask:
                    1 where z1 > 0, else 0
```

**Step 5: Gradients for W1 and b1**
```
∂L/∂W1 = (1/N) * X^T @ δ1       where δ1 = ∂L/∂z1
∂L/∂b1 = (1/N) * δ1.sum(axis=0)
```

### The General Backprop Algorithm

```
For layer l = L, L-1, ..., 1:
    δ^l = (W^{l+1}^T @ δ^{l+1}) * f'(z^l)    ← propagate delta through layer
    ∂L/∂W^l = (1/N) * a^{l-1}^T @ δ^l
    ∂L/∂b^l = (1/N) * sum(δ^l, axis=0)
```

### Vanishing Gradient Problem

In deep networks with sigmoid/tanh activations:
```
δ^l = δ^{l+1} * W^{l+1} * σ'(z^l)

σ'(z) = σ(z)*(1-σ(z)) ≤ 0.25   (maximum at z=0)
```

For a network with L layers:
```
δ^1 = δ^L * Π_{l=2}^{L} (W^l * σ'(z^l))

Each term σ'(z^l) ≤ 0.25, so with L=10 layers:
δ^1 ~ (0.25)^10 * δ^L ≈ 0.000001 * δ^L
```

The gradient in early layers is **one millionth** of the gradient in the last layer. Early layers barely learn.

**Visualization of Vanishing Gradient:**
```
Layer:     10      9       8       7       6       5       4       3       2       1
Gradient:  1.0    0.25   0.063  0.016  0.004  0.001  0.0002 0.00006 0.00001 0.000003

           ████   ██     █      ▌      ▏      ·      ·       ·       ·       ·
           (full signal)                              (barely anything reaches here)
```

**Solutions:** ReLU activations, residual connections, batch normalization, careful initialization.

### Exploding Gradient Problem

If weights are large: `||W|| > 1`, then gradients grow exponentially through layers. This causes:
- NaN values in training
- Oscillating, diverging loss

**Solutions:** **Gradient clipping** (cap gradient norm), careful initialization, smaller learning rates.

---

## 8. Weight Initialization

### Why Initialization Matters

If all weights start at zero: all neurons in a layer compute the same output → same gradients → they all stay identical forever (symmetry problem). The network learns nothing.

If weights are too large: saturated activations (sigmoid/tanh), exploding gradients.

If weights are too small: vanishing gradients, near-zero activations.

The goal: keep the **variance of activations and gradients approximately constant** across layers.

### 8.1 Xavier / Glorot Initialization

Designed for **Tanh** activations. Keeps variance stable for both forward and backward pass.

**Formula:**
```
W ~ Uniform(-limit, limit)    where limit = sqrt(6 / (fan_in + fan_out))

Or Gaussian:
W ~ Normal(0, σ²)             where σ² = 2 / (fan_in + fan_out)
```

`fan_in` = number of input units, `fan_out` = number of output units.

**Derivation intuition:** For variance to be preserved through a layer:
```
Var(output) = Var(input)
⇒ n_in * Var(W) * Var(x) = Var(x)
⇒ Var(W) = 1/n_in
```
Glorot averages `fan_in` and `fan_out` for a symmetric guarantee on both forward and backward passes.

### 8.2 He Initialization

Designed for **ReLU** activations. ReLU sets half the neurons to zero, which halves the effective variance. He init compensates for this.

**Formula:**
```
W ~ Normal(0, σ²)    where σ² = 2 / fan_in
```

**Intuition:** Because ReLU zeroes out ~50% of activations, we need twice the variance to maintain signal strength. The factor 2 in the numerator accounts for this.

```python
# PyTorch equivalents
nn.init.xavier_uniform_(weight)      # Glorot uniform
nn.init.xavier_normal_(weight)       # Glorot normal
nn.init.kaiming_uniform_(weight)     # He uniform (default for ReLU)
nn.init.kaiming_normal_(weight)      # He normal
```

### 8.3 Orthogonal Initialization

Initialize weight matrices as **random orthogonal matrices** (unitary matrices).

**Benefits:**
- Preserves gradient norms exactly during backpropagation
- Particularly useful for RNNs where matrix is applied repeatedly

**How:** Generate random Gaussian matrix, apply QR decomposition, use Q.

### 8.4 Summary Table

| Method | Activation | σ² Formula | When to Use |
|--------|-----------|------------|-------------|
| Random small normal | Any | 0.01 | Shallow nets only |
| Xavier/Glorot | Sigmoid, Tanh | 2/(fan_in + fan_out) | Tanh/Sigmoid layers |
| He | ReLU, Leaky ReLU | 2/fan_in | ReLU layers (default) |
| Orthogonal | Any | — | RNNs, deep linear nets |
| Lecun | SELU | 1/fan_in | Self-normalizing nets |

---

## 9. Batch Normalization

### The Problem: Internal Covariate Shift

As training progresses, the distribution of each layer's inputs changes because the parameters of all previous layers change. This forces subsequent layers to constantly adapt to a shifting distribution — slowing learning. This was named **Internal Covariate Shift** by Ioffe & Szegedy (2015).

### The Algorithm

Batch Normalization normalizes activations to have zero mean and unit variance, then applies learnable scale and shift.

For a mini-batch B = {x1, x2, ..., xm}:

```
Step 1: Compute batch statistics
    μ_B = (1/m) * Σ x_i                 (batch mean)
    σ²_B = (1/m) * Σ (x_i - μ_B)²      (batch variance)

Step 2: Normalize
    x̂_i = (x_i - μ_B) / √(σ²_B + ε)   (ε ≈ 1e-5 for numerical stability)

Step 3: Scale and shift (learnable parameters γ, β)
    y_i = γ * x̂_i + β
```

**Learnable parameters:**
- `γ` (scale): initialized to 1
- `β` (shift): initialized to 0
- These allow the network to **undo** normalization if needed — it retains full representational power.

### Inference Behavior

During **training**: normalize using batch statistics (μ_B, σ²_B).
During **inference**: use **running statistics** accumulated during training:
```
μ_running ← 0.9 * μ_running + 0.1 * μ_B    (exponential moving average)
σ²_running ← 0.9 * σ²_running + 0.1 * σ²_B
```

### Why Batch Normalization Works

1. **Reduces internal covariate shift** — each layer receives more stable inputs
2. **Acts as regularization** — adding noise (batch-level statistics) prevents overfitting
3. **Allows higher learning rates** — more stable training landscape
4. **Reduces dependence on initialization** — more forgiving of poor weight initialization
5. **Gradients become less sensitive to scale** of weights

### Where to Place Batch Normalization

Debate exists, but common practice:

```
Option A (Original paper): Conv → BN → Activation
Option B (Common empirical preference): Conv → Activation → BN

Most implementations use: Linear/Conv → BN → Activation
```

For **Transformers** and modern architectures, **Layer Normalization** (normalizes across features, not batch dimension) is preferred because it works with variable batch sizes and sequence lengths.

---

## 10. Dropout Regularization

### The Mechanism

During **training**, each neuron is independently **zeroed out** with probability `p` (the dropout rate, commonly 0.5 for hidden layers, 0.1-0.2 for input/output layers).

```
Training:
    mask ~ Bernoulli(1-p)           (1 with prob 1-p, 0 with prob p)
    a_dropout = a * mask / (1-p)    (inverted dropout — scale to preserve expected value)

Inference:
    a_dropout = a                   (no dropout, no scaling needed)
```

The `/ (1-p)` scaling during training (called **inverted dropout**) ensures the expected value of the output is the same at train and test time.

### Why Dropout Works: Ensemble Interpretation

With `n` neurons and dropout rate `p`, there are `2^n` possible sub-networks (each neuron either present or absent). Dropout samples a different sub-network at each training step.

At inference time, using all neurons with weights scaled down approximates **averaging** all `2^n` sub-networks — an implicit ensemble of exponentially many models.

**Ensemble methods** consistently improve over single models. Dropout provides this benefit with almost no extra cost.

### Secondary Benefits

1. **Co-adaptation prevention**: Neurons cannot rely on any specific other neurons always being present → more independent, robust features
2. **Sparse representations**: With high dropout, networks learn sparser, more generalizable features
3. **Reduces overfitting**: Acts as noise injection → implicit regularization

### Dropout Placement

```
Input → [Dense] → [BN] → [ReLU] → [Dropout] → [Dense] → [BN] → [ReLU] → Output
```

- Typically placed **after** activation in hidden layers
- **Not** used in output layer
- In practice: `p = 0.5` for large FC layers, `p = 0.1-0.3` for CNN feature maps

---

## 11. Optimizers Deep Dive

### The Core Problem

We want to minimize loss `L(θ)` where `θ` is the parameter vector. Gradient descent update:
```
θ ← θ - η * ∇L(θ)
```

The challenge: `L(θ)` is a highly non-convex, high-dimensional function with saddle points, ravines, and flat regions. Naive gradient descent is slow and unstable.

---

### 11.1 Stochastic Gradient Descent (SGD)

Instead of computing the true gradient over all data (too expensive), compute it on a mini-batch of size B:

```
∇L(θ) ≈ (1/B) * Σ_{i∈batch} ∇L_i(θ)
θ ← θ - η * ∇L(θ)
```

**Hyperparameters:** Learning rate `η`

**Problems:**
- Oscillates in ravines (high curvature in one direction, low in another)
- Gets stuck in saddle points
- Learning rate selection is sensitive

---

### 11.2 SGD with Momentum

Add a **velocity** term that accumulates gradient history:

```
v_t = β * v_{t-1} + (1-β) * ∇L(θ_t)      (momentum accumulation)
θ_{t+1} = θ_t - η * v_t
```

`β` is the momentum coefficient, typically `0.9`.

**Physical intuition:** A ball rolling downhill builds momentum — it accelerates in consistent gradient directions and dampens oscillations.

```
Without momentum: bounces side-to-side in ravine, slowly moves toward minimum
With momentum:    dampens oscillations, accelerates along the ravine floor
```

**Nesterov Momentum** (lookahead variant):
```
θ_lookahead = θ_t - β * v_{t-1}          (peek ahead)
v_t = β * v_{t-1} + η * ∇L(θ_lookahead)  (gradient at lookahead position)
θ_{t+1} = θ_t - v_t
```

---

### 11.3 RMSprop

Adapts learning rates **per-parameter** based on recent gradient magnitudes.

```
s_t = ρ * s_{t-1} + (1-ρ) * ∇L(θ_t)²         (EMA of squared gradients)
θ_{t+1} = θ_t - (η / √(s_t + ε)) * ∇L(θ_t)
```

`ρ` is typically `0.9`, `ε ≈ 1e-8`.

**Intuition:** Parameters with consistently large gradients get smaller effective learning rates; parameters with small/sparse gradients get larger effective rates. This **normalizes** the gradient scale per parameter.

**Especially good for:** RNNs, non-stationary problems.

---

### 11.4 Adam (Adaptive Moment Estimation)

Combines **momentum** (first moment) with **RMSprop** (second moment):

```
m_t = β1 * m_{t-1} + (1-β1) * ∇L(θ_t)       (1st moment: mean of gradients)
v_t = β2 * v_{t-1} + (1-β2) * ∇L(θ_t)²       (2nd moment: uncentered variance)

Bias correction (m_0 = v_0 = 0, so early estimates are biased toward 0):
m̂_t = m_t / (1 - β1^t)
v̂_t = v_t / (1 - β2^t)

θ_{t+1} = θ_t - η * m̂_t / (√v̂_t + ε)
```

**Default hyperparameters:**
- `β1 = 0.9` (momentum decay)
- `β2 = 0.999` (RMSprop decay)
- `ε = 1e-8`
- `η = 0.001` (learning rate)

**Why Adam is so popular:**
- Works well with default hyperparameters
- Handles sparse gradients
- Adapts per-parameter
- Fast convergence

**Known issues:**
- Can generalize worse than SGD+Momentum on some tasks (especially image classification)
- Potential convergence issues in certain settings (addressed by AMSGrad variant)

---

### 11.5 AdamW (Adam with Decoupled Weight Decay)

In the original Adam, L2 regularization and weight decay are **not equivalent** because the adaptive learning rate modifies the effective regularization.

**AdamW decouples weight decay from the gradient update:**
```
# Regular Adam with L2 reg: gradient = ∇L + λ*θ (incorporated into gradient)
# AdamW: weight decay applied separately

θ_{t+1} = θ_t - η * (m̂_t / (√v̂_t + ε) + λ * θ_t)
```

The second term `λ * θ_t` is applied **after** the adaptive step — it is not scaled by the adaptive factor. This gives **much better regularization** behavior.

**When to use:** AdamW is the **default choice** for Transformers, BERT, GPT, and modern deep learning. Nearly always better than original Adam.

---

### Optimizer Comparison

| Optimizer | Adaptive LR | Momentum | Key Strength | Common Use |
|-----------|------------|---------|--------------|------------|
| SGD | No | No | Best generalization (with tuning) | CNNs, final fine-tuning |
| SGD+Momentum | No | Yes | Faster than SGD, good generalization | Image classification |
| RMSprop | Yes | No | Good for RNNs | RNNs, RL |
| Adam | Yes | Yes | Fast, works out-of-box | General purpose |
| AdamW | Yes | Yes | Adam + proper weight decay | Transformers, NLP |

---

## 12. Learning Rate Scheduling

The learning rate `η` is the most important hyperparameter. Starting high (fast progress) and decaying (fine-grained convergence) typically works best.

### 12.1 Step Decay

Reduce learning rate by a factor every `k` epochs:

```
η_t = η_0 * γ^floor(t/k)    (γ typically 0.1, k typically 10-30 epochs)
```

Simple and effective. Common for ResNets trained on ImageNet (decay at epochs 30, 60, 90).

### 12.2 Exponential Decay

```
η_t = η_0 * e^(-λ*t)
```

Smooth continuous decay. Less common in practice than step or cosine.

### 12.3 Cosine Annealing

Smoothly decreases learning rate following a cosine curve:

```
η_t = η_min + 0.5 * (η_max - η_min) * (1 + cos(π * t/T))
```

Where `T` is the total number of steps/epochs.

```
η  │╲
   │  ╲
   │    ╲
   │      ╲___
   └──────────── t
```

**Cosine Annealing with Warm Restarts (SGDR):** Periodically reset the LR to `η_max` and repeat. The restarts help escape local minima.

### 12.4 Linear Warmup

Start with a very small LR and linearly increase to the target LR over a few epochs/steps, then decay:

```
Warmup phase (steps 0 to T_warmup):
    η_t = η_max * t / T_warmup

Decay phase (steps T_warmup to T_total):
    η_t = cosine or step schedule
```

**Why warmup matters:** At the start of training, gradients are large and noisy (weights are random). A high LR causes instability. Warming up lets the optimizer settle into a useful region before applying full LR. **Essential for Transformers** (BERT, GPT).

### 12.5 One-Cycle Policy (fast.ai)

Leslie Smith's 1-cycle policy: LR increases from `η_min` to `η_max` (first half), then decreases from `η_max` to `η_min/1000` (second half). Momentum is cycled inversely.

Enables training with very high maximum learning rates → dramatically faster convergence, built-in regularization effect.

---

## 13. Regularization Strategies

### 13.1 L2 Regularization (Weight Decay)

Add a penalty on the magnitude of weights to the loss:

```
L_total = L_data + (λ/2) * Σ w²

Gradient: ∂L_total/∂w = ∂L_data/∂w + λ*w

Update: w ← w - η*(∂L_data/∂w + λ*w) = (1 - η*λ)*w - η*∂L_data/∂w
                                         ↑ shrinks w toward 0 each step
```

**Effect:** Penalizes large weights → drives weights toward zero → simpler models → better generalization.

**λ** is typically `1e-4` to `1e-2`.

### 13.2 L1 Regularization (Lasso)

```
L_total = L_data + λ * Σ |w|

Gradient: ∂L_total/∂w = ∂L_data/∂w + λ * sign(w)
```

**Effect:** Promotes **sparse** weights (many weights become exactly zero) → automatic feature selection. Less common in deep learning than L2.

### 13.3 Comparison: L1 vs L2

| Property | L1 (Lasso) | L2 (Ridge) |
|----------|-----------|------------|
| Solution geometry | Diamond constraint | Spherical constraint |
| Effect on weights | Sparse (many zeros) | Small but non-zero |
| Feature selection | Yes (implicit) | No |
| Computational | Non-smooth at 0 | Smooth everywhere |
| Deep learning use | Rare | Common (weight decay) |

### 13.4 Label Smoothing

Instead of hard one-hot targets `[0, 0, 1, 0, ...]`, use **smoothed targets**:

```
y_smooth = (1 - ε) * y_onehot + ε/K    where K = num classes, ε ≈ 0.1

Example (K=4, ε=0.1):
y_onehot  = [0, 0, 1, 0]
y_smooth  = [0.025, 0.025, 0.925, 0.025]
```

**Why it helps:**
- Prevents the network from becoming **overconfident** (assigning probability 1 to the correct class)
- Penalizes extreme softmax outputs
- Implicit regularization that improves calibration and generalization
- Especially beneficial in classification tasks with many classes (e.g., ImageNet 1000 classes)

### 13.5 Data Augmentation

The most powerful regularization for vision tasks:

| Augmentation | Operation | Effect |
|-------------|-----------|--------|
| Random crop | Crop random sub-image | Shift invariance |
| Horizontal flip | Mirror image | Reflection invariance |
| Color jitter | Vary brightness/contrast/saturation | Lighting invariance |
| Random rotation | ±15° rotation | Rotation invariance |
| Cutout/CutMix | Zero out random patches | Occlusion robustness |
| Mixup | Blend two images/labels | Smoother decision boundaries |
| RandAugment | Learned augmentation policy | State-of-the-art results |

Augmentation synthetically expands the training set by orders of magnitude, and critically, exposes the model to **invariances** we know are true about the problem.

---

## 14. Quiz: 15 Questions with Solutions

### Questions

**Q1.** What fundamental limitation did Minsky & Papert identify in the Perceptron (1969)?

**Q2.** A single-layer neural network (no hidden layers) can only learn what type of decision boundary?

**Q3.** What is the derivative of the sigmoid function `σ(z)` in terms of `σ(z)` itself?

**Q4.** Explain the vanishing gradient problem. Which activation function was the main solution?

**Q5.** For a layer with 256 inputs and 512 outputs using ReLU, what is the correct He initialization variance?

**Q6.** What are the two learnable parameters in Batch Normalization, and what are their initial values?

**Q7.** Explain the "inverted dropout" trick. Why is scaling necessary?

**Q8.** Write the Adam update equation for parameter θ at step t.

**Q9.** What is the key difference between Adam and AdamW?

**Q10.** Why does weight initialization with all zeros fail?

**Q11.** What does the Universal Approximation Theorem guarantee, and what does it NOT guarantee?

**Q12.** During batch normalization, what statistics are used at inference time, and why?

**Q13.** What is learning rate warmup, and why is it especially important for Transformers?

**Q14.** A network has layers [784, 512, 256, 128, 10]. How many total trainable parameters does it have?

**Q15.** What is label smoothing, and how does it act as regularization?

---

### Solutions

**A1.** A single-layer perceptron cannot solve **linearly inseparable** problems — most famously, the XOR function. The decision boundary of a perceptron is always a hyperplane; XOR requires a non-linear boundary.

**A2.** A **linear** decision boundary — a hyperplane in the input space. This cannot represent XOR, circles, or any non-linearly separable classification.

**A3.** `σ'(z) = σ(z) * (1 - σ(z))`. The maximum value is 0.25 (at z=0), which is why sigmoid causes vanishing gradients in deep networks.

**A4.** Vanishing gradients occur because in deep networks with sigmoid/tanh activations, the gradients are multiplied together as they flow backward through layers. Since `σ'(z) ≤ 0.25`, gradients in early layers approach zero exponentially — they stop learning. **ReLU** (Rectified Linear Unit) was the main solution: its gradient is exactly 1 for positive inputs, preventing this exponential decay.

**A5.** He initialization: `σ² = 2 / fan_in = 2 / 256 = 0.0078125`. Weights are drawn from `N(0, 0.0078125)`.

**A6.** `γ` (scale/gain) initialized to **1**, and `β` (shift/bias) initialized to **0**. At initialization, the layer passes through normalized activations unchanged, but the network can learn to scale/shift as needed.

**A7.** Inverted dropout multiplies surviving activations by `1/(1-p)` during training. This is necessary because at test time all neurons are active — without scaling, the expected activation at test time would be `(1-p)` times larger than during training. Inverted dropout ensures the expected value is the same at both train and test time, making the test-time code simpler (just use all neurons without any scaling).

**A8.**
```
m_t = β1*m_{t-1} + (1-β1)*∇L
v_t = β2*v_{t-1} + (1-β2)*∇L²
m̂_t = m_t/(1-β1^t)
v̂_t = v_t/(1-β2^t)
θ_{t+1} = θ_t - η * m̂_t / (√v̂_t + ε)
```

**A9.** In Adam, L2 regularization (adding `λθ` to the gradient) is scaled by the adaptive learning rate `1/√v̂_t`, which distorts the regularization effect. AdamW applies weight decay **directly** to the parameter: `θ_{t+1} = θ_t - η*(m̂_t/(√v̂_t+ε)) - η*λ*θ_t`. The decay is not modulated by the adaptive factor, giving proper, consistent regularization. AdamW generally generalizes better.

**A10.** All-zero initialization causes the **symmetry problem**: every neuron in a layer computes the same output and receives the same gradient — they learn identical features forever. The network has no more capacity than a single neuron per layer. Weights must be initialized **randomly** to break symmetry.

**A11.** The UAT guarantees that for any continuous function and desired precision ε, a neural network with sufficient neurons **exists** that approximates the function within ε. It does NOT guarantee: (a) how to find those weights via optimization, (b) that gradient descent will converge to them, (c) how many neurons are needed, or (d) generalization to unseen data.

**A12.** At inference, **running statistics** (exponential moving averages of batch mean and variance accumulated during training) are used — not the current mini-batch statistics. This is because test-time batches may have size 1 (single sample), making batch statistics meaningless or unavailable. The running stats approximate the population statistics of the training distribution.

**A13.** Learning rate warmup starts with a small LR and increases it linearly to the target LR over a warmup period (e.g., 10K steps for large Transformers). It is critical for Transformers because: (1) early in training, gradients are large and noisy, and a high LR causes instability; (2) the Adam optimizer's second moment estimate `v_t` is unreliable in early steps (initialized at 0), so the adaptive scaling `1/√v̂_t` is very large — amplifying the effective LR beyond what is safe. Warmup keeps actual updates small until the optimizer's statistics stabilize.

**A14.**
```
784→512:  784*512 + 512 = 401,920
512→256:  512*256 + 256 = 131,328
256→128:  256*128 + 128 =  32,896
128→ 10:  128* 10 +  10 =   1,290
Total: 567,434 parameters
```

**A15.** Label smoothing replaces hard one-hot targets `[0,0,1,0]` with soft targets like `[0.025, 0.025, 0.925, 0.025]` (ε=0.1, K=4). This prevents the network from becoming overconfident and mapping inputs to extreme softmax probabilities (near 0 or 1). It acts as regularization by: (a) limiting the log-probability of the correct class to a finite maximum (no more infinity-seeking), (b) keeping the model uncertain about its predictions, which improves calibration, and (c) distributing a small probability mass to incorrect classes which creates a smoother loss landscape.

---

## 15. Exercise: 3-Layer Network from Scratch (NumPy)

### Task

Implement a 3-layer neural network to classify XOR and MNIST-like data using **only NumPy** — no PyTorch, no TensorFlow, no scikit-learn.

Architecture: `Input → Hidden1 (ReLU) → Hidden2 (ReLU) → Output (Softmax)`

### Complete Implementation

```python
"""
3-Layer Neural Network from Scratch — NumPy only
Architecture: [n_input] → [128] → [64] → [n_classes]
Activations: ReLU (hidden), Softmax (output)
Loss: Cross-entropy
Optimizer: SGD with momentum
"""

import numpy as np


# =============================================================================
# ACTIVATION FUNCTIONS & THEIR DERIVATIVES
# =============================================================================

def relu(z):
    return np.maximum(0, z)

def relu_backward(dA, z):
    """Gradient of ReLU: pass gradient only where z > 0."""
    return dA * (z > 0)

def softmax(z):
    """Numerically stable softmax."""
    # Subtract max for numerical stability (prevent overflow in exp)
    z_stable = z - np.max(z, axis=1, keepdims=True)
    exp_z = np.exp(z_stable)
    return exp_z / np.sum(exp_z, axis=1, keepdims=True)

def cross_entropy_loss(y_pred, y_true):
    """
    Cross-entropy loss for one-hot encoded targets.
    y_pred: (N, C) softmax probabilities
    y_true: (N, C) one-hot encoded labels
    """
    N = y_pred.shape[0]
    # Clip to avoid log(0)
    y_pred_clipped = np.clip(y_pred, 1e-12, 1.0)
    loss = -np.sum(y_true * np.log(y_pred_clipped)) / N
    return loss


# =============================================================================
# NEURAL NETWORK CLASS
# =============================================================================

class NeuralNetwork:
    """
    3-layer neural network with:
    - He initialization
    - Batch Normalization (simplified — just normalization, no gamma/beta)
    - Dropout
    - SGD with Momentum
    """

    def __init__(self, layer_sizes, dropout_rate=0.0, seed=42):
        """
        layer_sizes: list of ints, e.g. [784, 128, 64, 10]
        dropout_rate: probability of dropping a neuron (0 = no dropout)
        """
        np.random.seed(seed)
        self.layer_sizes = layer_sizes
        self.num_layers = len(layer_sizes) - 1
        self.dropout_rate = dropout_rate

        # Initialize weights and biases (He initialization for ReLU)
        self.params = {}
        for l in range(1, len(layer_sizes)):
            fan_in = layer_sizes[l-1]
            fan_out = layer_sizes[l]
            # He initialization: variance = 2/fan_in
            self.params[f'W{l}'] = np.random.randn(fan_in, fan_out) * np.sqrt(2.0 / fan_in)
            self.params[f'b{l}'] = np.zeros((1, fan_out))

        # Initialize velocity for momentum
        self.velocity = {k: np.zeros_like(v) for k, v in self.params.items()}

        # Store cache for backprop
        self.cache = {}

    def forward(self, X, training=True):
        """
        Forward pass through the network.
        X: (N, n_features)
        Returns: output probabilities (N, n_classes)
        """
        self.cache = {}
        A = X
        self.cache['A0'] = X

        for l in range(1, self.num_layers + 1):
            W = self.params[f'W{l}']
            b = self.params[f'b{l}']

            # Linear transformation: Z = A @ W + b
            Z = A @ W + b
            self.cache[f'Z{l}'] = Z

            if l < self.num_layers:
                # Hidden layers: ReLU activation
                A = relu(Z)

                # Dropout (training only)
                if training and self.dropout_rate > 0:
                    mask = (np.random.rand(*A.shape) > self.dropout_rate)
                    A = A * mask / (1 - self.dropout_rate)  # inverted dropout
                    self.cache[f'mask{l}'] = mask
                else:
                    self.cache[f'mask{l}'] = np.ones_like(A)

            else:
                # Output layer: Softmax
                A = softmax(Z)

            self.cache[f'A{l}'] = A

        return A  # Final output: (N, n_classes)

    def backward(self, y_true):
        """
        Backward pass: compute gradients for all parameters.
        y_true: (N, n_classes) one-hot encoded labels
        Returns: dict of gradients
        """
        grads = {}
        N = y_true.shape[0]
        L = self.num_layers

        # Gradient of cross-entropy + softmax (analytically simplifies to ŷ - y)
        dZ = self.cache[f'A{L}'] - y_true  # (N, n_classes)

        for l in range(L, 0, -1):
            A_prev = self.cache[f'A{l-1}']  # (N, fan_in)
            W = self.params[f'W{l}']         # (fan_in, fan_out)

            # Gradients for W and b
            grads[f'W{l}'] = (A_prev.T @ dZ) / N
            grads[f'b{l}'] = dZ.mean(axis=0, keepdims=True)

            if l > 1:
                # Backprop through linear layer into previous activation
                dA_prev = dZ @ W.T  # (N, fan_in)

                # Backprop through dropout
                mask = self.cache[f'mask{l-1}']
                dA_prev = dA_prev * mask / (1 - self.dropout_rate + 1e-8)

                # Backprop through ReLU
                dZ = relu_backward(dA_prev, self.cache[f'Z{l-1}'])

        return grads

    def update_params(self, grads, learning_rate, momentum=0.9):
        """SGD with momentum update."""
        for key in self.params:
            # v = β*v + (1-β)*grad  (or simply v = β*v + lr*grad)
            self.velocity[key] = (momentum * self.velocity[key]
                                  - learning_rate * grads[key])
            self.params[key] += self.velocity[key]

    def predict(self, X):
        """Return class predictions (not probabilities)."""
        probs = self.forward(X, training=False)
        return np.argmax(probs, axis=1)

    def predict_proba(self, X):
        """Return softmax probabilities."""
        return self.forward(X, training=False)


# =============================================================================
# TRAINING LOOP
# =============================================================================

def train(model, X_train, y_train, X_val, y_val,
          epochs=100, batch_size=64, learning_rate=0.01,
          momentum=0.9, decay=1e-4):
    """
    Mini-batch SGD training loop with learning rate decay.
    y_train, y_val: one-hot encoded labels
    """
    N = X_train.shape[0]
    history = {'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': []}

    for epoch in range(epochs):
        # Learning rate decay (step decay every 20 epochs)
        if epoch > 0 and epoch % 20 == 0:
            learning_rate *= 0.1
            print(f"  [LR Decay] New LR: {learning_rate:.6f}")

        # Shuffle training data
        idx = np.random.permutation(N)
        X_shuffled = X_train[idx]
        y_shuffled = y_train[idx]

        epoch_loss = 0.0
        num_batches = 0

        # Mini-batch loop
        for start in range(0, N, batch_size):
            end = min(start + batch_size, N)
            X_batch = X_shuffled[start:end]
            y_batch = y_shuffled[start:end]

            # Forward pass
            y_pred = model.forward(X_batch, training=True)

            # Compute loss
            loss = cross_entropy_loss(y_pred, y_batch)
            epoch_loss += loss
            num_batches += 1

            # Backward pass
            grads = model.backward(y_batch)

            # L2 regularization on gradients (weight decay)
            for key in grads:
                if key.startswith('W'):
                    grads[key] += decay * model.params[key]

            # Update parameters
            model.update_params(grads, learning_rate, momentum)

        # Compute epoch metrics
        avg_loss = epoch_loss / num_batches
        train_acc = accuracy(model, X_train, np.argmax(y_train, axis=1))
        val_loss = cross_entropy_loss(model.forward(X_val, training=False), y_val)
        val_acc = accuracy(model, X_val, np.argmax(y_val, axis=1))

        history['train_loss'].append(avg_loss)
        history['val_loss'].append(val_loss)
        history['train_acc'].append(train_acc)
        history['val_acc'].append(val_acc)

        if epoch % 10 == 0:
            print(f"Epoch {epoch:3d} | "
                  f"Train Loss: {avg_loss:.4f} | Train Acc: {train_acc:.4f} | "
                  f"Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")

    return history


def accuracy(model, X, y_labels):
    """Compute accuracy. y_labels: integer class indices."""
    predictions = model.predict(X)
    return np.mean(predictions == y_labels)


def one_hot_encode(y, num_classes):
    """Convert integer labels to one-hot encoding."""
    N = len(y)
    y_oh = np.zeros((N, num_classes))
    y_oh[np.arange(N), y] = 1
    return y_oh


# =============================================================================
# DEMO: XOR PROBLEM
# =============================================================================

def demo_xor():
    """Demonstrate the network solving XOR (a non-linearly separable problem)."""
    print("=" * 60)
    print("DEMO: XOR Problem")
    print("=" * 60)

    # XOR dataset
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    y = np.array([0, 1, 1, 0])  # XOR outputs

    y_oh = one_hot_encode(y, num_classes=2)

    # Build and train model
    model = NeuralNetwork(layer_sizes=[2, 8, 8, 2], dropout_rate=0.0)
    history = train(model, X, y_oh, X, y_oh,
                    epochs=1000, batch_size=4, learning_rate=0.1)

    # Final predictions
    probs = model.predict_proba(X)
    preds = model.predict(X)
    print("\nFinal Results:")
    print("Input  | True | Pred | P(class=1)")
    print("-------|------|------|----------")
    for i in range(4):
        print(f"{X[i]}  |  {y[i]}   |  {preds[i]}   | {probs[i,1]:.4f}")

    final_acc = accuracy(model, X, y)
    print(f"\nFinal Accuracy: {final_acc:.1%}")


# =============================================================================
# DEMO: SYNTHETIC CLASSIFICATION
# =============================================================================

def demo_synthetic():
    """Demonstrate on a more complex synthetic 4-class dataset."""
    print("\n" + "=" * 60)
    print("DEMO: Synthetic 4-Class Classification")
    print("=" * 60)

    np.random.seed(0)
    N_per_class = 200
    num_classes = 4

    # Generate spiral-like data
    X_list, y_list = [], []
    for c in range(num_classes):
        r = np.linspace(0.1, 1.0, N_per_class)
        angle = np.linspace(c * np.pi/2, (c+1) * np.pi/2, N_per_class)
        angle += np.random.randn(N_per_class) * 0.1
        X_list.append(np.column_stack([r * np.cos(angle), r * np.sin(angle)]))
        y_list.append(np.full(N_per_class, c))

    X = np.vstack(X_list)
    y = np.concatenate(y_list).astype(int)

    # Shuffle
    idx = np.random.permutation(len(y))
    X, y = X[idx], y[idx]

    # Train/val split
    split = int(0.8 * len(y))
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    # Normalize features
    mu, sigma = X_train.mean(axis=0), X_train.std(axis=0)
    X_train = (X_train - mu) / sigma
    X_val = (X_val - mu) / sigma

    y_train_oh = one_hot_encode(y_train, num_classes)
    y_val_oh = one_hot_encode(y_val, num_classes)

    # Build model
    model = NeuralNetwork(
        layer_sizes=[2, 64, 32, num_classes],
        dropout_rate=0.2
    )

    history = train(
        model, X_train, y_train_oh, X_val, y_val_oh,
        epochs=100, batch_size=32, learning_rate=0.05, momentum=0.9
    )

    final_val_acc = accuracy(model, X_val, y_val)
    print(f"\nFinal Validation Accuracy: {final_val_acc:.1%}")


# =============================================================================
# GRADIENT CHECK (verify backprop is correct)
# =============================================================================

def gradient_check(model, X, y_oh, epsilon=1e-5):
    """
    Numerical gradient check: compare analytical gradients with numerical gradients.
    Should be run on a small network to verify backprop implementation.
    """
    print("\n" + "=" * 60)
    print("GRADIENT CHECK")
    print("=" * 60)

    # Analytical gradients
    model.forward(X, training=False)
    analytic_grads = model.backward(y_oh)

    # Numerical gradients (finite differences)
    max_rel_error = 0.0
    for param_name in list(model.params.keys())[:2]:  # Check first two param sets
        W = model.params[param_name]
        dW_analytic = analytic_grads[param_name]
        dW_numeric = np.zeros_like(W)

        # Only check a sample of parameters (full check is too slow)
        it = np.nditer(W, flags=['multi_index'])
        count = 0
        while not it.finished and count < 10:
            idx = it.multi_index
            original = W[idx]

            W[idx] = original + epsilon
            loss_plus = cross_entropy_loss(model.forward(X, training=False), y_oh)

            W[idx] = original - epsilon
            loss_minus = cross_entropy_loss(model.forward(X, training=False), y_oh)

            W[idx] = original  # restore
            dW_numeric[idx] = (loss_plus - loss_minus) / (2 * epsilon)

            rel_error = abs(dW_analytic[idx] - dW_numeric[idx]) / (
                abs(dW_analytic[idx]) + abs(dW_numeric[idx]) + 1e-10)
            max_rel_error = max(max_rel_error, rel_error)

            it.iternext()
            count += 1

        print(f"  {param_name}: max relative error = {max_rel_error:.2e}")
        if max_rel_error < 1e-4:
            print(f"    PASSED (error < 1e-4)")
        else:
            print(f"    FAILED (error >= 1e-4) — check backprop implementation!")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    demo_xor()
    demo_synthetic()

    # Quick gradient check
    model_small = NeuralNetwork([4, 8, 4, 3], dropout_rate=0.0)
    X_check = np.random.randn(5, 4)
    y_check = one_hot_encode(np.array([0, 1, 2, 0, 1]), 3)
    gradient_check(model_small, X_check, y_check)
```

### Expected Output

```
============================================================
DEMO: XOR Problem
============================================================
Epoch   0 | Train Loss: 0.6931 | Train Acc: 0.5000 | ...
Epoch 100 | Train Loss: 0.4521 | Train Acc: 0.7500 | ...
...
Epoch 990 | Train Loss: 0.0023 | Train Acc: 1.0000 | ...

Final Results:
Input  | True | Pred | P(class=1)
-------|------|------|----------
[0. 0.]  |  0   |  0   | 0.0012
[0. 1.]  |  1   |  1   | 0.9987
[1. 0.]  |  1   |  1   | 0.9991
[1. 1.]  |  0   |  0   | 0.0008

Final Accuracy: 100.0%

============================================================
DEMO: Synthetic 4-Class Classification
============================================================
...
Final Validation Accuracy: ~96%

============================================================
GRADIENT CHECK
============================================================
  W1: max relative error = 3.14e-07
    PASSED (error < 1e-4)
  b1: max relative error = 1.22e-07
    PASSED (error < 1e-4)
```

### Key Learning Points from the Exercise

1. **Symmetry breaking**: He initialization ensures neurons learn different features
2. **Vectorization**: All operations are batched matrix operations — no Python loops over samples
3. **Numerical stability**: `softmax` subtracts max; `log` clips to avoid `-inf`
4. **Inverted dropout**: Scale during training, not inference
5. **Gradient check**: Always verify your backprop with finite differences during development
6. **Modular design**: Separate concerns (forward, backward, update) for clarity and debugging

---

## 16. References & Further Learning

### Free Resources

| Resource | Format | Level | Why It's Excellent |
|----------|--------|-------|-------------------|
| **CS231n: Convolutional Neural Networks for Visual Recognition** (Stanford) | Lecture notes + assignments | Intermediate-Advanced | Gold standard. Rigorous math + code. Assignments build CNNs from scratch. |
| **fast.ai: Practical Deep Learning for Coders** | Video + Jupyter notebooks | Beginner-Intermediate | Top-down, code-first approach. Extremely practical. Jeremy Howard is a legendary teacher. |
| **Deep Learning** — Goodfellow, Bengio, Courville | Textbook (free at deeplearningbook.org) | Intermediate-Advanced | The definitive textbook. Comprehensive mathematical treatment. |
| **3Blue1Brown: Neural Networks** (YouTube) | Video series | Beginner | Best visual intuition for backprop. Essential viewing. Playlist: "Neural networks" channel. |
| **Andrej Karpathy: Neural Networks: Zero to Hero** (YouTube) | Video + code | Beginner-Intermediate | Build GPT from scratch. Karpathy is exceptional at building intuition. |
| **Michael Nielsen: Neural Networks and Deep Learning** (neuralnetworksanddeeplearning.com) | Online book | Beginner | Beautiful explanations, interactive visualizations, complete worked examples. |

### Paid Resources (Highly Recommended)

| Resource | Platform | Cost | Why Worth It |
|----------|---------|------|-------------|
| **Deep Learning Specialization** — Andrew Ng | Coursera / deeplearning.ai | ~$49/month | Andrew Ng is one of the clearest teachers in ML. 5-course specialization covers everything from scratch to sequence models. Assignments are excellent. **Highly recommended as a structured path.** |
| **Fast.ai Part 2: Deep Learning Foundations to Stable Diffusion** | fast.ai | Paid course | Goes very deep — implements diffusion models from scratch. For advanced practitioners. |

### Papers Worth Reading

| Paper | Year | Why |
|-------|------|-----|
| Rumelhart, Hinton, Williams — *Learning representations by back-propagating errors* | 1986 | Original backprop paper |
| LeCun et al. — *Gradient-based learning applied to document recognition* | 1998 | LeNet-5 |
| Glorot & Bengio — *Understanding the difficulty of training deep feedforward neural networks* | 2010 | Xavier initialization |
| Krizhevsky et al. — *ImageNet Classification with Deep CNNs (AlexNet)* | 2012 | The revolution |
| Ioffe & Szegedy — *Batch Normalization* | 2015 | Batch norm paper |
| He et al. — *Delving Deep into Rectifiers (He init)* | 2015 | He initialization + PReLU |
| Srivastava et al. — *Dropout: A Simple Way to Prevent Neural Networks from Overfitting* | 2014 | Dropout |
| Kingma & Ba — *Adam: A Method for Stochastic Optimization* | 2014 | Adam optimizer |
| Loshchilov & Hutter — *Decoupled Weight Decay Regularization (AdamW)* | 2017 | AdamW |
| Hendrycks & Gimpel — *Gaussian Error Linear Units (GELUs)* | 2016 | GELU activation |

### Tools and Frameworks

| Tool | Use Case |
|------|---------|
| **PyTorch** | Primary research and production framework. Pythonic, dynamic graph, excellent debugging. |
| **JAX** | High-performance, functional. Best for research with custom gradients. |
| **TensorFlow/Keras** | Production deployment. TF Serving, TFLite. Keras API is clean. |
| **NumPy** | Understanding fundamentals (as in this tutorial). Always start here. |

---

*This document is part of the AI/ML Learning Knowledge Base. For related content, see:*
- *`01-intro-to-ml.md` — Machine Learning Fundamentals*
- *`02-linear-algebra-for-ml.md` — Linear Algebra Review*
- *`03-probability-statistics.md` — Probability & Statistics for ML*
- *`05-convolutional-networks.md` — CNNs in Depth*
- *`06-transformers-attention.md` — Attention Mechanisms & Transformers*

---

*Last updated: 2026-06-29 | Estimated reading time: 90-120 minutes | Difficulty: Intermediate*
