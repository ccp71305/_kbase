# Calculus & Optimization for AI/ML/Deep Learning

> **Series:** AI/ML Mathematics Foundation  
> **Module:** 02 — Calculus & Optimization  
> **Prerequisites:** Linear Algebra (Module 01), basic Python  
> **Estimated Time:** 8–12 hours

---

## Table of Contents

1. [Why Calculus Matters in ML](#1-why-calculus-matters-in-ml)
2. [Derivatives — The Core Idea](#2-derivatives--the-core-idea)
3. [Partial Derivatives & Gradients](#3-partial-derivatives--gradients)
4. [The Chain Rule](#4-the-chain-rule)
5. [Jacobian Matrix](#5-jacobian-matrix)
6. [Hessian Matrix & Second-Order Information](#6-hessian-matrix--second-order-information)
7. [Backpropagation — Full Derivation from First Principles](#7-backpropagation--full-derivation-from-first-principles)
8. [Gradient Descent & All Its Variants](#8-gradient-descent--all-its-variants)
9. [Learning Rate Schedules](#9-learning-rate-schedules)
10. [Second-Order Optimization Methods](#10-second-order-optimization-methods)
11. [Convex vs Non-Convex Optimization](#11-convex-vs-non-convex-optimization)
12. [Loss Landscapes](#12-loss-landscapes)
13. [Python Implementation Lab](#13-python-implementation-lab)
14. [Quiz — 10 Questions with Solutions](#14-quiz--10-questions-with-solutions)
15. [Exercises — 5 Practical Problems with Solutions](#15-exercises--5-practical-problems-with-solutions)
16. [References & Further Reading](#16-references--further-reading)

---

## 1. Why Calculus Matters in ML

Every machine learning model is trained by **minimizing a loss function**. To do that, we need to know which direction to move the model parameters so the loss decreases. That direction is given by the **gradient** — a concept rooted entirely in calculus.

```
High-level ML training loop:
┌─────────────────────────────────────────────────────┐
│  1. Forward pass: compute predictions + loss        │
│  2. Backward pass: compute gradients (calculus!)    │
│  3. Update parameters: θ ← θ - η·∇L                │
│  4. Repeat until convergence                        │
└─────────────────────────────────────────────────────┘
```

Calculus is the engine under the hood of:
- **Gradient descent** (the optimizer)
- **Backpropagation** (efficient gradient computation)
- **Regularization** (gradient penalties)
- **Batch normalization** (chain rule through statistics)
- **Attention mechanisms** (softmax derivative)

---

## 2. Derivatives — The Core Idea

### Intuition

A derivative measures the **instantaneous rate of change** of a function. Imagine you are driving: your position is `f(t)`. The derivative `f'(t)` is your speedometer reading at time `t`.

In ML, if `L(w)` is the loss and `w` is a weight, then `dL/dw` tells you: "if I increase `w` slightly, how much does the loss change?"

```
f(x)
  │          *
  │        *   *
  │      *       *
  │    *           slope = f'(x) at this point
  │  *  ↗
  │ *
  └──────────────────── x
```

### Formal Definition

$$f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}$$

This is the **limit definition** of a derivative. We approximate the slope of the tangent line at `x` by taking an infinitesimally small step `h`.

### Key Differentiation Rules

| Rule | Formula | Example |
|------|---------|---------|
| Power Rule | `d/dx [xⁿ] = n·xⁿ⁻¹` | `d/dx [x³] = 3x²` |
| Product Rule | `d/dx [fg] = f'g + fg'` | `d/dx [x·sin(x)] = sin(x) + x·cos(x)` |
| Quotient Rule | `d/dx [f/g] = (f'g - fg')/g²` | `d/dx [x/eˣ] = (eˣ - xeˣ)/e²ˣ` |
| Chain Rule | `d/dx [f(g(x))] = f'(g(x))·g'(x)` | `d/dx [sin(x²)] = cos(x²)·2x` |
| Exponential | `d/dx [eˣ] = eˣ` | — |
| Logarithm | `d/dx [ln x] = 1/x` | — |

### Common ML Activation Function Derivatives

| Function | `f(x)` | `f'(x)` |
|----------|--------|---------|
| Sigmoid | `σ(x) = 1/(1+e⁻ˣ)` | `σ(x)(1 - σ(x))` |
| Tanh | `tanh(x)` | `1 - tanh²(x)` |
| ReLU | `max(0, x)` | `0 if x<0, 1 if x>0` |
| Leaky ReLU | `max(αx, x)` | `α if x<0, 1 if x>0` |
| Softplus | `ln(1 + eˣ)` | `σ(x)` |

### Worked Example

**Problem:** Find the derivative of the sigmoid cross-entropy loss.

Let `σ(z) = 1/(1+e⁻ᶻ)` and `L = -y·ln(σ(z)) - (1-y)·ln(1-σ(z))`.

**Step 1:** `dσ/dz = σ(z)(1 - σ(z))`

**Step 2:** `dL/dz = -y·(1/σ)·σ(1-σ) + (1-y)·(1/(1-σ))·σ(1-σ)`

**Step 3:** Simplify: `dL/dz = -y(1-σ) + (1-y)σ = σ - y`

This elegant result — `σ(z) - y` — is why logistic regression gradients are so clean.

### Python Code

```python
import numpy as np
import matplotlib.pyplot as plt

def numerical_derivative(f, x, h=1e-7):
    """Compute derivative using the limit definition (finite difference)."""
    return (f(x + h) - f(x - h)) / (2 * h)  # central difference is more accurate

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sigmoid_derivative(x):
    s = sigmoid(x)
    return s * (1 - s)

# Verify: numerical vs analytical
x = np.linspace(-5, 5, 200)
numerical = np.array([numerical_derivative(sigmoid, xi) for xi in x])
analytical = sigmoid_derivative(x)

plt.figure(figsize=(10, 4))
plt.subplot(1, 2, 1)
plt.plot(x, sigmoid(x), label='σ(x)')
plt.plot(x, sigmoid_derivative(x), label="σ'(x)", linestyle='--')
plt.title('Sigmoid and its Derivative')
plt.legend(); plt.grid(True)

plt.subplot(1, 2, 2)
plt.plot(x, np.abs(numerical - analytical))
plt.title('Numerical vs Analytical Error (should be ~0)')
plt.ylabel('Absolute Error'); plt.grid(True)
plt.tight_layout()
plt.savefig('sigmoid_derivative.png', dpi=150)
plt.show()
```

---

## 3. Partial Derivatives & Gradients

### Intuition

When a function has **multiple inputs** (e.g., a neural network with thousands of weights), we need to know how the output changes with respect to each input *independently*. A partial derivative holds all other variables constant.

### Formal Definition

For `f(x₁, x₂, ..., xₙ)`:

$$\frac{\partial f}{\partial x_i} = \lim_{h \to 0} \frac{f(x_1, \ldots, x_i+h, \ldots, x_n) - f(x_1, \ldots, x_i, \ldots, x_n)}{h}$$

### The Gradient

The **gradient** is a vector of all partial derivatives:

$$\nabla f(\mathbf{x}) = \left[\frac{\partial f}{\partial x_1}, \frac{\partial f}{\partial x_2}, \ldots, \frac{\partial f}{\partial x_n}\right]^T$$

Key geometric property: **the gradient points in the direction of steepest ascent**. Therefore, **negative gradient points toward steepest descent** — exactly what we want in training.

### Gradient as a Compass on a Loss Surface

```
Loss Surface (viewed from above):
       ↑ w₂
  _____|_____
 /     |     \
|   ∇L ↗     |   ← gradient arrow points UP the hill
|      *      |   ← current position
|             |
 \_____|_____/
       |_____ w₁→

To minimize: move in direction -∇L
```

### Worked Example

**Problem:** `f(x, y) = x² + 3xy + y²`

**∂f/∂x** = 2x + 3y (treat y as constant)  
**∂f/∂y** = 3x + 2y (treat x as constant)

**∇f(1, 2)** = [2(1)+3(2), 3(1)+2(2)] = [8, 7]

To descend: move in direction [-8, -7] (scaled by learning rate).

### Python Code

```python
import numpy as np

def f(x, y):
    return x**2 + 3*x*y + y**2

def gradient_f(x, y):
    """Analytical gradient of f."""
    df_dx = 2*x + 3*y
    df_dy = 3*x + 2*y
    return np.array([df_dx, df_dy])

def numerical_gradient(f_scalar, params, h=1e-5):
    """Compute gradient numerically (finite differences)."""
    grad = np.zeros_like(params, dtype=float)
    for i in range(len(params)):
        params_plus = params.copy(); params_plus[i] += h
        params_minus = params.copy(); params_minus[i] -= h
        grad[i] = (f_scalar(*params_plus) - f_scalar(*params_minus)) / (2*h)
    return grad

point = np.array([1.0, 2.0])
print("Analytical gradient:", gradient_f(*point))
print("Numerical gradient:", numerical_gradient(f, point))
```

---

## 4. The Chain Rule

### Intuition

The chain rule is the **fundamental theorem of backpropagation**. It lets us compute derivatives of composed functions — which is exactly what a neural network is: a long chain of composed transformations.

If `y = f(g(x))`, then: `dy/dx = (dy/dg) · (dg/dx)`

Think of it as: "how does a small change in x ripple through g and then through f?"

### Chain Rule Flow Diagram

```
Input x ──→ [g(x)] ──→ [f(u)] ──→ Output y
               ↑                        ↑
               u                        y

Forward:  x → u = g(x) → y = f(u)

Backward (chain rule):
  dy/dx = dy/du · du/dx
        = f'(u) · g'(x)
        = f'(g(x)) · g'(x)

Flow of gradients (BACKWARD direction):
  ∂L/∂x ←── ∂L/∂u ←── ∂L/∂y
        ×g'(x)    ×f'(u)
```

### Multivariable Chain Rule

For `L = f(u, v)` where `u = g(x)` and `v = h(x)`:

$$\frac{dL}{dx} = \frac{\partial L}{\partial u}\cdot\frac{du}{dx} + \frac{\partial L}{\partial v}\cdot\frac{dv}{dx}$$

Gradients **accumulate** when a variable influences the output through multiple paths — crucial for understanding skip connections (ResNets).

### Worked Example

**Problem:** Compute `d/dx [sin(x²)]` at `x = π`

Let `u = x²`, so `y = sin(u)`.

- `dy/du = cos(u) = cos(x²)`
- `du/dx = 2x`
- `dy/dx = cos(x²) · 2x = 2π·cos(π²) ≈ 2π·(-0.902) ≈ -5.67`

### Python Code

```python
import numpy as np

# Demonstrate chain rule through numerical computation
def chain_rule_demo(x):
    # Forward pass
    u = x**2           # u = g(x)
    y = np.sin(u)      # y = f(u)
    
    # Backward pass (chain rule)
    dy_du = np.cos(u)  # df/du
    du_dx = 2*x        # dg/dx
    dy_dx = dy_du * du_dx  # chain rule
    
    return y, dy_dx

x = np.pi
y, grad = chain_rule_demo(x)
print(f"f({x:.4f}) = {y:.6f}")
print(f"f'({x:.4f}) = {grad:.6f}")

# Verify numerically
h = 1e-7
numerical = (np.sin((x+h)**2) - np.sin((x-h)**2)) / (2*h)
print(f"Numerical verification: {numerical:.6f}")
```

---

## 5. Jacobian Matrix

### Intuition

The Jacobian generalizes the gradient to **vector-valued functions**. If `f: Rⁿ → Rᵐ`, the Jacobian is an `m×n` matrix capturing how each output changes with each input.

### Formal Definition

$$J_{ij} = \frac{\partial f_i}{\partial x_j}$$

$$\mathbf{J} = \begin{bmatrix} \frac{\partial f_1}{\partial x_1} & \cdots & \frac{\partial f_1}{\partial x_n} \\ \vdots & \ddots & \vdots \\ \frac{\partial f_m}{\partial x_1} & \cdots & \frac{\partial f_m}{\partial x_n} \end{bmatrix}$$

### Why It Matters in ML

- **Batch backprop**: the Jacobian of a layer maps output gradients to input gradients
- **BatchNorm**: requires the full Jacobian (non-trivial!)
- **Generative models**: the Jacobian determinant appears in change-of-variables formula for normalizing flows

### Worked Example

**Problem:** `f(x₁, x₂) = [x₁² + x₂, x₁·x₂]`

$$J = \begin{bmatrix} 2x_1 & 1 \\ x_2 & x_1 \end{bmatrix}$$

At `(2, 3)`:

$$J = \begin{bmatrix} 4 & 1 \\ 3 & 2 \end{bmatrix}$$

### Python Code

```python
import numpy as np

def f(x):
    return np.array([x[0]**2 + x[1], x[0]*x[1]])

def jacobian_numerical(f, x, h=1e-5):
    """Compute Jacobian numerically."""
    f0 = f(x)
    m = len(f0)
    n = len(x)
    J = np.zeros((m, n))
    for j in range(n):
        x_plus = x.copy(); x_plus[j] += h
        x_minus = x.copy(); x_minus[j] -= h
        J[:, j] = (f(x_plus) - f(x_minus)) / (2*h)
    return J

x = np.array([2.0, 3.0])
J = jacobian_numerical(f, x)
print("Jacobian at (2, 3):")
print(J)
# Expected: [[4, 1], [3, 2]]
```

---

## 6. Hessian Matrix & Second-Order Information

### Intuition

The Hessian captures **curvature** — how the gradient itself is changing. It is the second derivative generalized to multiple dimensions.

- **High curvature**: loss changes rapidly → smaller steps needed
- **Low curvature**: loss changes slowly → larger steps are safe
- **Saddle points**: some directions curve up, others down (very common in deep learning!)

### Formal Definition

$$H_{ij} = \frac{\partial^2 f}{\partial x_i \partial x_j}$$

For a scalar function `f: Rⁿ → R`, the Hessian is an `n×n` symmetric matrix.

### What the Hessian Tells Us

| Hessian Property | Meaning |
|-----------------|---------|
| All eigenvalues > 0 | Local minimum (bowl shape) |
| All eigenvalues < 0 | Local maximum (inverted bowl) |
| Mixed eigenvalues | Saddle point |
| Eigenvalue ≈ 0 | Flat direction (degenerate) |
| Large condition number | Ill-conditioned landscape |

### Python Code

```python
import numpy as np

def hessian_numerical(f_scalar, x, h=1e-5):
    """Compute Hessian numerically using finite differences."""
    n = len(x)
    H = np.zeros((n, n))
    f0 = f_scalar(x)
    for i in range(n):
        for j in range(n):
            x_pp = x.copy(); x_pp[i] += h; x_pp[j] += h
            x_pm = x.copy(); x_pm[i] += h; x_pm[j] -= h
            x_mp = x.copy(); x_mp[i] -= h; x_mp[j] += h
            x_mm = x.copy(); x_mm[i] -= h; x_mm[j] -= h
            H[i, j] = (f_scalar(x_pp) - f_scalar(x_pm) 
                      - f_scalar(x_mp) + f_scalar(x_mm)) / (4*h**2)
    return H

def rosenbrock(x):
    """Classic non-convex test function: f(x,y) = (1-x)² + 100(y-x²)²"""
    return (1 - x[0])**2 + 100*(x[1] - x[0]**2)**2

x_saddle = np.array([0.0, 0.0])
H = hessian_numerical(rosenbrock, x_saddle)
eigenvalues = np.linalg.eigvalsh(H)
print("Hessian at origin:", H)
print("Eigenvalues:", eigenvalues)
print("Point type:", "saddle" if any(eigenvalues < 0) and any(eigenvalues > 0) else "minimum/maximum")
```

---

## 7. Backpropagation — Full Derivation from First Principles

This is the most important section in this module. We will derive backpropagation **completely from scratch** for a 2-layer neural network.

### Network Architecture

```
                    LAYER 1              LAYER 2          OUTPUT
                 ┌──────────┐         ┌──────────┐
Input x ────────►  z¹=W¹x+b¹ ────────►  z²=W²a¹+b² ─────► ŷ = a²
          (n×1)  └──────────┘  (sigmoid) └──────────┘ (sigmoid)
                     z¹ (h×1)    a¹=σ(z¹)   z² (1×1)    a²=σ(z²)

Loss: L = -[y·log(a²) + (1-y)·log(1-a²)]   (binary cross-entropy)
```

### Step 1: Forward Pass (Computing Activations)

```
z¹ = W¹·x + b¹          (linear transform, layer 1)
a¹ = σ(z¹)               (activation, layer 1)
z² = W²·a¹ + b²          (linear transform, layer 2)
a² = σ(z²)               (activation, layer 2) = ŷ
L  = -y·log(a²) - (1-y)·log(1-a²)   (loss)
```

### Step 2: Backward Pass — Layer 2

**Goal:** compute `∂L/∂W²` and `∂L/∂b²`

**∂L/∂a²** (loss w.r.t. output):
```
∂L/∂a² = -y/a² + (1-y)/(1-a²)
        = (a² - y) / (a²(1 - a²))
```

**∂a²/∂z²** (sigmoid derivative):
```
∂a²/∂z² = a²(1 - a²)
```

**∂L/∂z²** (chain rule — the "delta"):
```
δ² = ∂L/∂z² = ∂L/∂a² · ∂a²/∂z²
             = [(a² - y) / (a²(1-a²))] · [a²(1-a²)]
             = a² - y
```

This beautiful simplification is why sigmoid + cross-entropy is the standard choice!

**∂L/∂W²**:
```
∂L/∂W² = δ² · (a¹)ᵀ          (outer product: shape [1×1] · [1×h] = [1×h])
```

**∂L/∂b²**:
```
∂L/∂b² = δ²                   (bias gradient = delta)
```

### Step 3: Backward Pass — Layer 1

**∂L/∂a¹** (propagate gradient backward through W²):
```
∂L/∂a¹ = (W²)ᵀ · δ²           (shape [h×1])
```

**∂a¹/∂z¹** (sigmoid derivative element-wise):
```
∂a¹/∂z¹ = a¹ ⊙ (1 - a¹)       (⊙ = element-wise multiply)
```

**∂L/∂z¹** (delta for layer 1):
```
δ¹ = ∂L/∂z¹ = ∂L/∂a¹ ⊙ ∂a¹/∂z¹
             = [(W²)ᵀ · δ²] ⊙ [a¹ ⊙ (1 - a¹)]
```

**∂L/∂W¹**:
```
∂L/∂W¹ = δ¹ · xᵀ              (outer product: shape [h×1] · [1×n] = [h×n])
```

**∂L/∂b¹**:
```
∂L/∂b¹ = δ¹
```

### Step 4: Parameter Update

```
W¹ ← W¹ - η · ∂L/∂W¹
b¹ ← b¹ - η · ∂L/∂b¹
W² ← W² - η · ∂L/∂W²
b² ← b² - η · ∂L/∂b²
```

### Complete Python Implementation

```python
import numpy as np

class TwoLayerNet:
    """Full 2-layer neural network with manual backprop."""
    
    def __init__(self, n_input, n_hidden, n_output, lr=0.01):
        # Xavier initialization
        self.W1 = np.random.randn(n_hidden, n_input) * np.sqrt(2/n_input)
        self.b1 = np.zeros((n_hidden, 1))
        self.W2 = np.random.randn(n_output, n_hidden) * np.sqrt(2/n_hidden)
        self.b2 = np.zeros((n_output, 1))
        self.lr = lr
        self.cache = {}
    
    def sigmoid(self, z):
        return 1 / (1 + np.exp(-np.clip(z, -500, 500)))
    
    def forward(self, x):
        """Forward pass — store intermediate values for backprop."""
        # Layer 1
        z1 = self.W1 @ x + self.b1
        a1 = self.sigmoid(z1)
        # Layer 2
        z2 = self.W2 @ a1 + self.b2
        a2 = self.sigmoid(z2)
        # Cache for backprop
        self.cache = {'x': x, 'z1': z1, 'a1': a1, 'z2': z2, 'a2': a2}
        return a2
    
    def binary_cross_entropy(self, a2, y):
        eps = 1e-8
        return -np.mean(y * np.log(a2 + eps) + (1 - y) * np.log(1 - a2 + eps))
    
    def backward(self, y):
        """Backward pass — compute gradients using chain rule."""
        x, z1, a1, z2, a2 = [self.cache[k] for k in ('x','z1','a1','z2','a2')]
        m = y.shape[1]  # batch size
        
        # --- Layer 2 gradients ---
        # delta2 = a2 - y  (derived above: sigmoid + cross-entropy)
        delta2 = a2 - y                          # shape: (n_out, m)
        dW2 = (delta2 @ a1.T) / m               # shape: (n_out, n_hidden)
        db2 = np.mean(delta2, axis=1, keepdims=True)  # shape: (n_out, 1)
        
        # --- Layer 1 gradients ---
        # Propagate through W2
        da1 = self.W2.T @ delta2                  # shape: (n_hidden, m)
        # Multiply by sigmoid derivative
        delta1 = da1 * a1 * (1 - a1)             # shape: (n_hidden, m)
        dW1 = (delta1 @ x.T) / m                 # shape: (n_hidden, n_input)
        db1 = np.mean(delta1, axis=1, keepdims=True)  # shape: (n_hidden, 1)
        
        return {'dW1': dW1, 'db1': db1, 'dW2': dW2, 'db2': db2}
    
    def update(self, grads):
        """Gradient descent parameter update."""
        self.W1 -= self.lr * grads['dW1']
        self.b1 -= self.lr * grads['db1']
        self.W2 -= self.lr * grads['dW2']
        self.b2 -= self.lr * grads['db2']
    
    def train(self, X, Y, epochs=1000, print_every=100):
        losses = []
        for epoch in range(epochs):
            a2 = self.forward(X)
            loss = self.binary_cross_entropy(a2, Y)
            grads = self.backward(Y)
            self.update(grads)
            losses.append(loss)
            if epoch % print_every == 0:
                preds = (a2 > 0.5).astype(int)
                acc = np.mean(preds == Y)
                print(f"Epoch {epoch:4d} | Loss: {loss:.4f} | Acc: {acc:.4f}")
        return losses

# --- Demo: XOR problem ---
np.random.seed(42)
X = np.array([[0,0,1,1],[0,1,0,1]], dtype=float)
Y = np.array([[0,1,1,0]], dtype=float)

net = TwoLayerNet(n_input=2, n_hidden=4, n_output=1, lr=1.0)
losses = net.train(X, Y, epochs=5000, print_every=1000)
print("Final predictions:", net.forward(X).round(3))
```

---

## 8. Gradient Descent & All Its Variants

### The Core Algorithm

```
θ ← θ - η · ∇L(θ)
```

where `η` (eta) is the **learning rate** and `∇L(θ)` is the gradient of the loss.

### Loss Landscape: Gradient Descent in Action

```
Loss
  │
  │\
  │ \          Full Batch GD: smooth, direct path
  │  \         SGD: noisy but faster per step
  │   \_       Adam: adaptive, robust
  │    \___
  │        \___________
  └──────────────────────── Iterations
  
  3D view (bowl-shaped convex loss):
  
        High Loss
          / | \
         /  |  \    ← gradient arrows point inward
        /   |   \
       /    ↓    \
      /   minimum \
```

### Variant 1: Batch Gradient Descent (BGD)

Uses **entire dataset** to compute gradient.

```
∇L = (1/N) Σᵢ ∇Lᵢ(θ)
θ ← θ - η · ∇L
```

| Pros | Cons |
|------|------|
| Stable convergence | Very slow for large N |
| Exact gradient | Cannot use online data |
| Guaranteed descent | Memory intensive |

### Variant 2: Stochastic Gradient Descent (SGD)

Uses **one sample** per update.

```
for each sample (xᵢ, yᵢ):
    ∇L = ∇Lᵢ(θ)
    θ ← θ - η · ∇L
```

| Pros | Cons |
|------|------|
| Fast updates | Noisy gradient |
| Escapes local minima | High variance |
| Online learning | Oscillates near minimum |

### Variant 3: Mini-Batch SGD

**Industry standard.** Uses a mini-batch of size B (typically 32–256).

```
for each mini-batch B:
    ∇L = (1/|B|) Σᵢ∈B ∇Lᵢ(θ)
    θ ← θ - η · ∇L
```

### Variant 4: SGD with Momentum

Adds a **velocity term** to smooth out oscillations. Inspired by physics — a ball rolling down a hill builds momentum.

```
v ← β·v + ∇L
θ ← θ - η·v
```

where `β` (typically 0.9) controls how much past gradients are remembered.

### Variant 5: AdaGrad

**Adaptive learning rates** — each parameter gets its own learning rate, scaled by the accumulated squared gradients.

```
G ← G + (∇L)²          (accumulate squared gradients)
θ ← θ - (η/√(G + ε)) · ∇L
```

**Problem:** `G` grows without bound → learning rate → 0 → training stops.

### Variant 6: RMSprop

**Fix for AdaGrad**: use exponential moving average of squared gradients.

```
E[g²] ← γ·E[g²] + (1-γ)·(∇L)²
θ ← θ - (η/√(E[g²] + ε)) · ∇L
```

Typical: `γ = 0.9`, `ε = 1e-8`

### Variant 7: Adam (Adaptive Moment Estimation)

The **most widely used optimizer** in deep learning. Combines momentum (first moment) with RMSprop (second moment).

```
m ← β₁·m + (1-β₁)·∇L        (first moment — momentum)
v ← β₂·v + (1-β₂)·(∇L)²     (second moment — RMSprop)

m̂ = m / (1 - β₁ᵗ)            (bias correction)
v̂ = v / (1 - β₂ᵗ)

θ ← θ - η · m̂ / (√v̂ + ε)
```

Typical defaults: `β₁=0.9`, `β₂=0.999`, `ε=1e-8`, `η=1e-3`

### Optimizer Comparison Table

| Optimizer | Adaptive LR | Momentum | Memory | Best For |
|-----------|------------|---------|--------|----------|
| SGD | No | No | Low | Simple problems, strong regularization |
| SGD+Momentum | No | Yes | Low | CNNs with tuned LR |
| AdaGrad | Yes | No | Medium | Sparse data, NLP |
| RMSprop | Yes | No | Medium | RNNs |
| Adam | Yes | Yes | Higher | General purpose (default choice) |
| AdamW | Yes | Yes | Higher | Transformers (Adam + weight decay fix) |

### Python: All Optimizers from Scratch

```python
import numpy as np
import matplotlib.pyplot as plt

class Optimizer:
    def __init__(self, lr=0.01):
        self.lr = lr
        self.state = {}

class SGD(Optimizer):
    def update(self, params, grads):
        for key in params:
            params[key] -= self.lr * grads[key]
        return params

class SGDMomentum(Optimizer):
    def __init__(self, lr=0.01, beta=0.9):
        super().__init__(lr)
        self.beta = beta
    
    def update(self, params, grads):
        if not self.state:
            self.state = {k: np.zeros_like(v) for k, v in params.items()}
        for key in params:
            self.state[key] = self.beta * self.state[key] + grads[key]
            params[key] -= self.lr * self.state[key]
        return params

class Adam(Optimizer):
    def __init__(self, lr=0.001, beta1=0.9, beta2=0.999, eps=1e-8):
        super().__init__(lr)
        self.beta1, self.beta2, self.eps = beta1, beta2, eps
        self.t = 0
    
    def update(self, params, grads):
        if not self.state:
            self.state['m'] = {k: np.zeros_like(v) for k, v in params.items()}
            self.state['v'] = {k: np.zeros_like(v) for k, v in params.items()}
        
        self.t += 1
        for key in params:
            m = self.state['m'][key]
            v = self.state['v'][key]
            g = grads[key]
            
            m = self.beta1 * m + (1 - self.beta1) * g
            v = self.beta2 * v + (1 - self.beta2) * g**2
            
            # Bias correction
            m_hat = m / (1 - self.beta1**self.t)
            v_hat = v / (1 - self.beta2**self.t)
            
            params[key] -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
            self.state['m'][key] = m
            self.state['v'][key] = v
        return params

# Test on a simple quadratic: L(w) = w²
def run_optimizer(opt, n_steps=100):
    w = np.array([5.0])
    trajectory = [w[0]]
    for _ in range(n_steps):
        grad = {'w': 2 * w}    # d(w²)/dw = 2w
        params = {'w': w.copy()}
        params = opt.update(params, grad)
        w = params['w']
        trajectory.append(w[0])
    return trajectory

optimizers = {
    'SGD (lr=0.1)': SGD(lr=0.1),
    'SGD+Momentum': SGDMomentum(lr=0.1, beta=0.9),
    'Adam': Adam(lr=0.5),
}

plt.figure(figsize=(10, 5))
for name, opt in optimizers.items():
    traj = run_optimizer(opt, n_steps=50)
    plt.plot(traj, label=name)

plt.xlabel('Steps'); plt.ylabel('Parameter value w')
plt.title('Optimizer Convergence on L(w) = w²')
plt.legend(); plt.grid(True); plt.axhline(0, color='k', linestyle='--')
plt.savefig('optimizer_comparison.png', dpi=150)
plt.show()
```

---

## 9. Learning Rate Schedules

The learning rate `η` is the most critical hyperparameter. Too large → diverge. Too small → train forever.

### Common Schedules

| Schedule | Formula | Use Case |
|---------|---------|---------|
| Constant | `η` = const | Simple baseline |
| Step decay | `η ← η · γ` every N epochs | CNNs |
| Exponential decay | `η_t = η₀ · e^(-λt)` | General purpose |
| Cosine annealing | `η_t = η_min + ½(η_max-η_min)(1+cos(πt/T))` | Transformers |
| Warm-up + decay | Linear warm-up then cosine/linear decay | BERT, GPT |
| Cyclical LR | Cycle between min and max | Fast convergence |
| 1-cycle policy | Single cosine cycle | fast.ai default |

### Learning Rate Finder

```
Loss
  │\
  │ \______________
  │                \___
  │                    \________  ← sweet spot here
  │                              \____
  │                                   \
  └──────────────────────────────────── log(LR)
  1e-6  1e-5  1e-4  1e-3  1e-2  1e-1  1
```

### Python: Cosine Annealing

```python
import numpy as np
import matplotlib.pyplot as plt

def cosine_annealing(t, T, lr_min=1e-6, lr_max=1e-2):
    return lr_min + 0.5*(lr_max - lr_min)*(1 + np.cos(np.pi * t / T))

def warmup_cosine(t, T_warmup, T_total, lr_max=1e-3, lr_min=1e-6):
    if t < T_warmup:
        return lr_max * t / T_warmup
    else:
        t_adj = t - T_warmup
        T_adj = T_total - T_warmup
        return cosine_annealing(t_adj, T_adj, lr_min, lr_max)

T = 100
t = np.arange(T)
cosine_lr = [cosine_annealing(ti, T) for ti in t]
warmup_lr = [warmup_cosine(ti, 10, T) for ti in t]

plt.figure(figsize=(10, 4))
plt.subplot(1, 2, 1)
plt.plot(t, cosine_lr); plt.title('Cosine Annealing'); plt.ylabel('LR')
plt.subplot(1, 2, 2)
plt.plot(t, warmup_lr); plt.title('Warmup + Cosine Decay'); plt.ylabel('LR')
plt.tight_layout()
plt.savefig('lr_schedules.png', dpi=150)
plt.show()
```

---

## 10. Second-Order Optimization Methods

### Newton's Method

Uses the **Hessian** to take curvature-aware steps. Instead of a fixed step size, scales by the inverse Hessian:

```
θ ← θ - H⁻¹ · ∇L
```

Intuition: in a steep valley, take smaller steps. On a gentle slope, take larger steps.

**Pros:** Quadratic convergence near minimum  
**Cons:** Computing `H⁻¹` costs `O(n³)` — infeasible for neural nets with millions of parameters.

### Quasi-Newton: L-BFGS

**Limited-memory BFGS** approximates the inverse Hessian using the history of gradients. Used in:
- Full-batch training of medium-sized networks
- PyTorch's `torch.optim.LBFGS`
- Physics-based simulations

### Natural Gradient

Uses the **Fisher information matrix** as the metric tensor for parameter space. Accounts for the geometry of the probability distribution, not just Euclidean distance. Used in:
- **K-FAC** (Kronecker-Factored Approximate Curvature)
- Proximal policy optimization (PPO) approximations
- Trust-region methods

---

## 11. Convex vs Non-Convex Optimization

### Convex Functions

A function is **convex** if the line segment between any two points lies above the graph:

```
f(λx + (1-λ)y) ≤ λf(x) + (1-λ)f(y)   for all λ ∈ [0,1]
```

```
Convex:           Non-convex (typical neural net loss):
    
   \             /       /\      /\
    \           /       /  \    /  \
     \         /       /    \  /    \
      \_______/        ____\/\/______

  One global minimum    Many local minima + saddle points
```

### Properties

| Property | Convex | Non-Convex |
|----------|--------|-----------|
| Local minimum | = Global minimum | ≠ Global minimum |
| Gradient descent | Guaranteed to converge | May get stuck |
| Saddle points | None | Abundant |
| Examples | Linear regression, SVM, logistic regression | Neural networks |

### Good News for Deep Learning

Empirically, deep neural networks are surprisingly **easy to optimize** despite being non-convex. Reasons:
1. **Most local minima are nearly as good as the global minimum** (Goodfellow et al.)
2. **Saddle points, not local minima, are the main obstacle** — but SGD's noise helps escape them
3. **Over-parameterization** creates many equivalent good solutions

---

## 12. Loss Landscapes

### Visualizing the Landscape

```
2D Loss Landscape (elevation map):
       
  ──────────────────────────────
  │  ○○○○○○○○○○○○○○○○○○○○○○○  │ HIGH
  │  ○○○○╔═══════╗○○○○○○○○○  │
  │  ○○○○║       ║○○○○○○○○○  │
  │  ○○○╔╝  ☆   ╚╗○○○○○○○  │ (☆ = minimum)
  │  ○○○║  saddle ║○○○○○○○  │
  │  ○○○╚╗       ╔╝○○○○○○○  │
  │  ○○○○║       ║○○○○○○○○○  │
  │  ○○○○╚═══════╝○○○○○○○○○  │ LOW
  ──────────────────────────────
```

### Python: Plot a 2D Loss Landscape

```python
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def loss_landscape(w1, w2):
    """Rastrigin function — classic non-convex landscape."""
    n = 2
    return 10*n + (w1**2 - 10*np.cos(2*np.pi*w1)) + \
                  (w2**2 - 10*np.cos(2*np.pi*w2))

w = np.linspace(-5, 5, 200)
W1, W2 = np.meshgrid(w, w)
L = loss_landscape(W1, W2)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Contour plot
ax1 = axes[0]
c = ax1.contourf(W1, W2, L, levels=50, cmap='viridis')
plt.colorbar(c, ax=ax1)
ax1.set_title('Loss Landscape (Contour View)')
ax1.set_xlabel('w₁'); ax1.set_ylabel('w₂')

# 3D surface
ax2 = fig.add_subplot(122, projection='3d')
surf = ax2.plot_surface(W1, W2, L, cmap='plasma', alpha=0.8)
ax2.set_title('Loss Landscape (3D View)')
ax2.set_xlabel('w₁'); ax2.set_ylabel('w₂'); ax2.set_zlabel('Loss')

plt.tight_layout()
plt.savefig('loss_landscape.png', dpi=150)
plt.show()

# --- Gradient descent on Rastrigin ---
def grad_rastrigin(w):
    w1, w2 = w
    return np.array([
        2*w1 + 20*np.pi*np.sin(2*np.pi*w1),
        2*w2 + 20*np.pi*np.sin(2*np.pi*w2)
    ])

def gradient_descent_path(start, lr=0.01, n_steps=500):
    w = np.array(start, dtype=float)
    path = [w.copy()]
    for _ in range(n_steps):
        g = grad_rastrigin(w)
        w -= lr * g
        path.append(w.copy())
    return np.array(path)

# From a good starting point
path_good = gradient_descent_path([0.5, 0.5], lr=0.01, n_steps=300)
# From a bad starting point (gets trapped)
path_bad = gradient_descent_path([3.5, 2.5], lr=0.01, n_steps=300)

plt.figure(figsize=(8, 6))
plt.contourf(W1, W2, L, levels=50, cmap='viridis', alpha=0.8)
plt.plot(path_good[:,0], path_good[:,1], 'w-', linewidth=2, label='Good init')
plt.plot(path_bad[:,0], path_bad[:,1], 'r-', linewidth=2, label='Bad init (trapped)')
plt.scatter([0], [0], c='yellow', s=200, zorder=5, label='Global min')
plt.legend(); plt.title('Gradient Descent Paths on Non-Convex Landscape')
plt.xlabel('w₁'); plt.ylabel('w₂')
plt.savefig('gd_paths.png', dpi=150)
plt.show()
```

### Flat vs Sharp Minima

Research shows that **flat minima generalize better** than sharp minima:

```
Flat minimum:           Sharp minimum:
       
  ___________              │▲│
 /           \           __|  |__
/             \         /        \
      ☆              ☆
      
Slight perturbation   Same perturbation → large loss increase
→ small loss change   Overfits to training set
```

SAM (Sharpness-Aware Minimization) explicitly seeks flat minima.

---

## 13. Python Implementation Lab

### Full Gradient Descent Lab

```python
import numpy as np
import matplotlib.pyplot as plt

# ======================================================
# LAB: Compare all optimizers on logistic regression
# ======================================================

np.random.seed(42)

# Generate linearly separable data
N = 200
X_pos = np.random.randn(N//2, 2) + np.array([2, 2])
X_neg = np.random.randn(N//2, 2) + np.array([-2, -2])
X = np.vstack([X_pos, X_neg])
y = np.hstack([np.ones(N//2), np.zeros(N//2)])

# Add bias term
X_b = np.column_stack([np.ones(N), X])  # shape (N, 3)

def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -500, 500)))

def loss(w, X, y):
    pred = sigmoid(X @ w)
    eps = 1e-8
    return -np.mean(y * np.log(pred + eps) + (1-y) * np.log(1 - pred + eps))

def gradient(w, X, y):
    pred = sigmoid(X @ w)
    return X.T @ (pred - y) / len(y)

def run_gd(optimizer_fn, X, y, n_epochs=500, batch_size=32):
    w = np.zeros(X.shape[1])
    losses = []
    for epoch in range(n_epochs):
        # Mini-batch
        idx = np.random.permutation(len(y))
        X_shuf, y_shuf = X[idx], y[idx]
        for i in range(0, len(y), batch_size):
            Xb = X_shuf[i:i+batch_size]
            yb = y_shuf[i:i+batch_size]
            g = gradient(w, Xb, yb)
            w = optimizer_fn(w, g)
        losses.append(loss(w, X, y))
    return losses, w

# Vanilla SGD
lr = 0.1
sgd_fn = lambda w, g: w - lr * g
losses_sgd, _ = run_gd(sgd_fn, X_b, y)

# SGD + Momentum
beta, v = 0.9, np.zeros(3)
def momentum_fn(w, g):
    global v
    v = beta*v + g
    return w - lr * v
losses_mom, _ = run_gd(momentum_fn, X_b, y)

# Adam
lr_adam, b1, b2, eps = 0.01, 0.9, 0.999, 1e-8
m_adam, v_adam, t_adam = np.zeros(3), np.zeros(3), 0
def adam_fn(w, g):
    global m_adam, v_adam, t_adam
    t_adam += 1
    m_adam = b1*m_adam + (1-b1)*g
    v_adam = b2*v_adam + (1-b2)*g**2
    m_hat = m_adam / (1 - b1**t_adam)
    v_hat = v_adam / (1 - b2**t_adam)
    return w - lr_adam * m_hat / (np.sqrt(v_hat) + eps)
losses_adam, _ = run_gd(adam_fn, X_b, y)

plt.figure(figsize=(8, 5))
plt.plot(losses_sgd, label='SGD')
plt.plot(losses_mom, label='SGD + Momentum')
plt.plot(losses_adam, label='Adam')
plt.xlabel('Epoch'); plt.ylabel('Loss')
plt.title('Optimizer Comparison on Logistic Regression')
plt.legend(); plt.grid(True)
plt.savefig('optimizer_convergence.png', dpi=150)
plt.show()
```

---

## 14. Quiz — 10 Questions with Solutions

### Questions

**Q1.** What is the derivative of `f(x) = ln(x²)`?

**Q2.** For `f(x, y) = e^(xy)`, compute `∂f/∂x` and `∂f/∂y`.

**Q3.** Using the chain rule, compute `d/dx [tanh(3x²)]`.

**Q4.** What does the gradient vector point toward?

**Q5.** In backpropagation for sigmoid + binary cross-entropy, what is `δ²` (the output layer delta)?

**Q6.** Why does AdaGrad's learning rate eventually go to zero?

**Q7.** Adam combines which two techniques?

**Q8.** What does the Hessian matrix capture?

**Q9.** A function with all positive Hessian eigenvalues at a point is a...?

**Q10.** Why do flat minima generalize better than sharp minima?

---

### Solutions

**A1.** `f(x) = ln(x²) = 2·ln(x)` → `f'(x) = 2/x`

**A2.** `∂f/∂x = y·e^(xy)` ; `∂f/∂y = x·e^(xy)`

**A3.** Let `u = 3x²`. `d/dx[tanh(u)] = sech²(u)·6x = 6x·sech²(3x²)` where `sech²(u) = 1-tanh²(u)`

**A4.** The gradient points in the direction of **steepest ascent** (maximum rate of increase).

**A5.** `δ² = a² - y` — the output prediction minus the true label. This elegant result arises from the cancellation when using sigmoid activation with binary cross-entropy loss.

**A6.** AdaGrad accumulates **all squared gradients** in `G`. Since `G` only grows (never shrinks), the effective learning rate `η/√G` monotonically decreases toward zero, causing training to stall. RMSprop fixes this with exponential decay.

**A7.** Adam combines **momentum** (exponential moving average of gradients, first moment) and **RMSprop** (exponential moving average of squared gradients, second moment), with bias correction for both.

**A8.** The Hessian captures **curvature** — the rate of change of the gradient. It contains second-order partial derivatives and describes whether the loss surface is bowl-shaped (convex), saddle-shaped, or inverted.

**A9.** A **local minimum** (all eigenvalues > 0 means the function curves up in all directions — a bowl shape).

**A10.** Flat minima have low **sharpness** — nearby points have similar loss values. When distributional shift occurs between training and test data, the model parameters may shift slightly, but a flat minimum absorbs this shift with little increase in loss. Sharp minima amplify perturbations, leading to worse generalization.

---

## 15. Exercises — 5 Practical Problems with Solutions

### Exercise 1: Numerical Gradient Check

**Problem:** Implement gradient checking for a neural network layer. Given an analytical gradient computation, verify it against the finite-difference estimate. Report the relative error.

**Solution:**

```python
import numpy as np

def rel_error(x, y):
    return np.max(np.abs(x - y) / (np.maximum(1e-8, np.abs(x) + np.abs(y))))

def fc_forward(x, W, b):
    return x @ W.T + b

def fc_backward(dout, x, W):
    dx = dout @ W
    dW = dout.T @ x
    db = dout.sum(axis=0)
    return dx, dW, db

# Setup
np.random.seed(0)
N, D, M = 5, 10, 7
x = np.random.randn(N, D)
W = np.random.randn(M, D)
b = np.random.randn(M)
dout = np.random.randn(N, M)

# Analytical gradients
_, dW_analytical, db_analytical = fc_backward(dout, x, W)

# Numerical gradient for W
h = 1e-5
dW_numerical = np.zeros_like(W)
for i in range(W.shape[0]):
    for j in range(W.shape[1]):
        W_plus = W.copy(); W_plus[i,j] += h
        W_minus = W.copy(); W_minus[i,j] -= h
        out_plus = fc_forward(x, W_plus, b)
        out_minus = fc_forward(x, W_minus, b)
        dW_numerical[i,j] = np.sum((out_plus - out_minus) * dout) / (2*h)

print(f"dW relative error: {rel_error(dW_analytical, dW_numerical):.2e}")
# Should be < 1e-6 for correct implementation
```

### Exercise 2: Implement RMSprop from Scratch

**Problem:** Implement RMSprop and train it on `f(w) = w₁² + 10·w₂²` (elongated bowl) starting from `(8, 1)`. Compare convergence against vanilla SGD.

**Solution:**

```python
import numpy as np
import matplotlib.pyplot as plt

def f(w): return w[0]**2 + 10*w[1]**2
def grad_f(w): return np.array([2*w[0], 20*w[1]])

def run_sgd(start, lr=0.05, steps=200):
    w = np.array(start, dtype=float)
    path = [w.copy()]
    for _ in range(steps):
        w -= lr * grad_f(w)
        path.append(w.copy())
    return np.array(path)

def run_rmsprop(start, lr=0.1, gamma=0.9, eps=1e-8, steps=200):
    w = np.array(start, dtype=float)
    E_g2 = np.zeros_like(w)
    path = [w.copy()]
    for _ in range(steps):
        g = grad_f(w)
        E_g2 = gamma * E_g2 + (1 - gamma) * g**2
        w -= lr * g / (np.sqrt(E_g2) + eps)
        path.append(w.copy())
    return np.array(path)

start = [8.0, 1.0]
path_sgd = run_sgd(start)
path_rmsprop = run_rmsprop(start)

w1_range = np.linspace(-9, 9, 200)
w2_range = np.linspace(-2, 2, 200)
W1, W2 = np.meshgrid(w1_range, w2_range)
Z = W1**2 + 10*W2**2

plt.figure(figsize=(10, 5))
plt.contourf(W1, W2, Z, levels=30, cmap='viridis', alpha=0.7)
plt.plot(path_sgd[:,0], path_sgd[:,1], 'r-o', ms=3, label=f'SGD (final: {f(path_sgd[-1]):.3f})')
plt.plot(path_rmsprop[:,0], path_rmsprop[:,1], 'w-o', ms=3, label=f'RMSprop (final: {f(path_rmsprop[-1]):.6f})')
plt.scatter([0], [0], c='yellow', s=200, zorder=10, label='Minimum')
plt.legend(); plt.title('SGD vs RMSprop on Elongated Bowl')
plt.xlabel('w₁'); plt.ylabel('w₂')
plt.savefig('rmsprop_vs_sgd.png', dpi=150)
plt.show()
```

### Exercise 3: Compute Jacobian of a Softmax Layer

**Problem:** Derive and implement the Jacobian of the softmax function `softmax(z)ᵢ = eᶻⁱ / Σⱼ eᶻʲ`, and verify numerically.

**Solution:**

```python
import numpy as np

def softmax(z):
    e = np.exp(z - np.max(z))
    return e / e.sum()

def softmax_jacobian(z):
    """
    Analytical Jacobian: J_ij = s_i(δ_ij - s_j)
    where δ_ij is the Kronecker delta.
    """
    s = softmax(z)
    return np.diag(s) - np.outer(s, s)

def numerical_jacobian(f, z, h=1e-5):
    n = len(z)
    m = len(f(z))
    J = np.zeros((m, n))
    for j in range(n):
        z_plus = z.copy(); z_plus[j] += h
        z_minus = z.copy(); z_minus[j] -= h
        J[:,j] = (f(z_plus) - f(z_minus)) / (2*h)
    return J

z = np.array([1.0, 2.0, 0.5, -0.3])
J_analytical = softmax_jacobian(z)
J_numerical = numerical_jacobian(softmax, z)

print("Max absolute error:", np.max(np.abs(J_analytical - J_numerical)))
# Should be ~1e-9
```

### Exercise 4: Implement Adam with Gradient Clipping

**Problem:** Implement Adam optimizer with gradient clipping (clip gradients to max norm 1.0). Train on a simple RNN-style problem where gradients can explode.

**Solution:**

```python
import numpy as np

def clip_gradient(grad, max_norm=1.0):
    """Clip gradient to have at most max_norm L2 norm."""
    norm = np.linalg.norm(grad)
    if norm > max_norm:
        return grad * (max_norm / norm)
    return grad

class AdamWithClipping:
    def __init__(self, lr=0.001, beta1=0.9, beta2=0.999, eps=1e-8, max_grad_norm=1.0):
        self.lr = lr
        self.beta1, self.beta2 = beta1, beta2
        self.eps = eps
        self.max_grad_norm = max_grad_norm
        self.m = None
        self.v = None
        self.t = 0
    
    def step(self, w, grad):
        if self.m is None:
            self.m = np.zeros_like(w)
            self.v = np.zeros_like(w)
        
        # Clip gradient
        grad_clipped = clip_gradient(grad, self.max_grad_norm)
        
        self.t += 1
        self.m = self.beta1 * self.m + (1 - self.beta1) * grad_clipped
        self.v = self.beta2 * self.v + (1 - self.beta2) * grad_clipped**2
        
        m_hat = self.m / (1 - self.beta1**self.t)
        v_hat = self.v / (1 - self.beta2**self.t)
        
        return w - self.lr * m_hat / (np.sqrt(v_hat) + self.eps)

# Test with exploding-gradient scenario
np.random.seed(42)
w = np.random.randn(5)
optimizer = AdamWithClipping(lr=0.01, max_grad_norm=1.0)
losses = []
for step in range(200):
    # Simulate large gradient spikes
    grad = np.random.randn(5) * (100 if step % 20 == 0 else 1)
    w = optimizer.step(w, grad)
    losses.append(np.sum(w**2))

print(f"Final w norm: {np.linalg.norm(w):.4f}")
print(f"Training stable: {not np.any(np.isnan(w))}")
```

### Exercise 5: Visualize Saddle Points and Escape with Noise

**Problem:** Create a saddle-point function `f(x,y) = x² - y²`. Show that gradient descent gets stuck at the origin, but adding noise (SGD) can escape.

**Solution:**

```python
import numpy as np
import matplotlib.pyplot as plt

def f_saddle(w): return w[0]**2 - w[1]**2
def grad_saddle(w): return np.array([2*w[0], -2*w[1]])

def gd_with_noise(start, lr=0.01, noise_std=0.0, steps=500):
    w = np.array(start, dtype=float)
    path = [w.copy()]
    for _ in range(steps):
        g = grad_saddle(w) + noise_std * np.random.randn(2)
        w -= lr * g
        path.append(w.copy())
        if abs(w[1]) > 5:  # escaped
            break
    return np.array(path)

path_gd = gd_with_noise([0.001, 0.001], lr=0.05, noise_std=0.0, steps=200)
path_sgd = gd_with_noise([0.001, 0.001], lr=0.05, noise_std=0.1, steps=200)

x = np.linspace(-3, 3, 100)
y = np.linspace(-3, 3, 100)
X, Y = np.meshgrid(x, y)
Z = X**2 - Y**2

plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.contourf(X, Y, Z, levels=30, cmap='RdBu_r')
plt.colorbar()
plt.plot(path_gd[:,0], path_gd[:,1], 'k-', linewidth=2, label='GD (stuck!)')
plt.scatter([0],[0], c='yellow', s=200, label='Saddle point')
plt.legend(); plt.title('Pure GD — Stuck at Saddle'); plt.xlim(-3,3); plt.ylim(-3,3)

plt.subplot(1, 2, 2)
plt.contourf(X, Y, Z, levels=30, cmap='RdBu_r')
plt.colorbar()
plt.plot(path_sgd[:,0], path_sgd[:,1], 'w-', linewidth=2, label='SGD (escapes!)')
plt.scatter([0],[0], c='yellow', s=200, label='Saddle point')
plt.legend(); plt.title('SGD with Noise — Escapes Saddle'); plt.xlim(-3,3); plt.ylim(-3,3)

plt.tight_layout()
plt.savefig('saddle_point_escape.png', dpi=150)
plt.show()
```

---

## 16. References & Further Reading

### Free Resources

| Resource | URL | Best For |
|---------|-----|---------|
| **3Blue1Brown: Neural Networks** (YouTube series) | youtube.com/3blue1brown | Visual intuition for backprop |
| **3Blue1Brown: Essence of Calculus** (YouTube) | youtube.com/3blue1brown | Chain rule, derivatives visually |
| **Khan Academy Calculus** | khanacademy.org/math/calculus-1 | Fundamentals from scratch |
| **MIT 18.01 Single Variable Calculus** (OCW) | ocw.mit.edu/18-01SC | Rigorous single-variable calculus |
| **MIT 18.02 Multivariable Calculus** (OCW) | ocw.mit.edu/18-02SC | Gradients, partial derivatives |
| **fast.ai: Calculus for ML** | explained.ai/matrix-calculus | Matrix calculus, directly applied to ML |
| **CS231n Notes: Backprop** | cs231n.github.io/optimization-2 | Backprop from Stanford |
| **Distill.pub: Why Momentum Works** | distill.pub/2017/momentum | Interactive momentum visualization |
| **Andrej Karpathy: micrograd** | github.com/karpathy/micrograd | Build autograd engine from scratch |

### Paid Resources

| Resource | Platform | Best For |
|---------|---------|---------|
| **Mathematics for Machine Learning** | Coursera (Imperial College) | Formal coverage: calculus, linear algebra, probability |
| **Deep Learning Specialization** | Coursera (Andrew Ng) | Backprop, optimization in context |
| **Practical Deep Learning for Coders** | fast.ai | Applied optimization |

### Books

| Book | Authors | Notes |
|------|---------|-------|
| *Deep Learning* | Goodfellow, Bengio, Courville | Chapter 4 (Numerical Computation) and Chapter 8 (Optimization) |
| *Mathematics for Machine Learning* | Deisenroth, Faisal, Ong | Free PDF at mml-book.com |
| *Numerical Optimization* | Nocedal & Wright | Graduate-level reference for optimizers |

### Key Papers

| Paper | Year | Contribution |
|-------|------|-------------|
| Rumelhart, Hinton & Williams | 1986 | Original backpropagation paper |
| Duchi et al. | 2011 | AdaGrad |
| Tieleman & Hinton | 2012 | RMSprop (Coursera lecture!) |
| Kingma & Ba | 2014 | Adam optimizer |
| Loshchilov & Hutter | 2019 | AdamW (decoupled weight decay) |
| Foret et al. | 2021 | SAM: Sharpness-Aware Minimization |

---

## Summary Cheat Sheet

```
DERIVATIVES
  f'(x) = lim_{h→0} [f(x+h) - f(x-h)] / 2h    (central difference)
  Chain rule: d/dx[f(g(x))] = f'(g(x)) · g'(x)

GRADIENT
  ∇f(x) = [∂f/∂x₁, ∂f/∂x₂, ..., ∂f/∂xₙ]ᵀ
  Points in direction of steepest ascent.

BACKPROP (2-layer net)
  δ² = a² - y                              (output delta)
  dW² = δ² · (a¹)ᵀ
  δ¹ = (W²)ᵀ·δ² ⊙ a¹·(1-a¹)             (layer 1 delta)
  dW¹ = δ¹ · xᵀ

OPTIMIZERS
  SGD:       θ ← θ - η·g
  Momentum:  v ← βv + g;  θ ← θ - η·v
  Adam:      m ← β₁m+(1-β₁)g; v ← β₂v+(1-β₂)g²
             θ ← θ - η·m̂/√(v̂+ε)

KEY NUMBERS (Adam defaults)
  η=1e-3, β₁=0.9, β₂=0.999, ε=1e-8
```

---

*End of Module 02 — Calculus & Optimization*  
*Next: Module 03 — Probability & Statistics for ML*
