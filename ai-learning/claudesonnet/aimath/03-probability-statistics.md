# Probability, Statistics & Information Theory for AI/ML/Deep Learning

> **Series:** AI/ML Mathematics Foundations | **Module:** 03  
> **Prerequisites:** Linear Algebra (01), Calculus & Optimization (02)  
> **Estimated study time:** 12-16 hours

---

## Table of Contents

1. [Why Probability Matters in ML](#1-why-probability-matters-in-ml)
2. [Probability Foundations](#2-probability-foundations)
3. [Conditional Probability & Bayes Theorem](#3-conditional-probability--bayes-theorem)
4. [Random Variables](#4-random-variables)
5. [Probability Distributions](#5-probability-distributions)
6. [Expectation, Variance & Covariance](#6-expectation-variance--covariance)
7. [Parameter Estimation: MLE & MAP](#7-parameter-estimation-mle--map)
8. [Information Theory](#8-information-theory)
9. [Central Limit Theorem](#9-central-limit-theorem)
10. [Hypothesis Testing & Confidence Intervals](#10-hypothesis-testing--confidence-intervals)
11. [A/B Testing in ML Systems](#11-ab-testing-in-ml-systems)
12. [Quiz (10 Questions)](#12-quiz)
13. [Practical Exercises](#13-practical-exercises)
14. [References](#14-references)

---

## 1. Why Probability Matters in ML

Every machine learning model is fundamentally a **probabilistic statement about the world**. Even a deterministic-looking model like a decision tree implicitly answers: "What is the most probable class given these features?"

| ML Concept | Probabilistic Interpretation |
|---|---|
| Linear regression | Maximum likelihood under Gaussian noise assumption |
| Logistic regression | Modeling P(y=1 \| x) directly |
| Neural network softmax | Categorical probability distribution over classes |
| Bayesian neural net | Posterior distribution over weights |
| GAN discriminator | Estimating data density ratio |
| Variational Autoencoder | Maximizing ELBO (Evidence Lower BOund) |
| RLHF reward model | Modeling human preference probability |

Understanding probability is not optional — it is the language in which modern AI is written.

---

## 2. Probability Foundations

### 2.1 Sample Space and Events

**Intuition:** Flip a coin. Before it lands, all possible outcomes form the *sample space*. Any subset of outcomes you care about is an *event*.

**Formal definition:**

- **Sample space** Omega: the set of all possible outcomes
- **Event** A: a subset A subset-of Omega
- **Probability measure** P: a function assigning a number in [0,1] to each event

### 2.2 Kolmogorov Axioms

These three axioms are the entire foundation of probability theory:

```
Axiom 1 (Non-negativity):   P(A) >= 0  for all events A
Axiom 2 (Normalization):    P(Omega) = 1
Axiom 3 (Additivity):       If A and B are mutually exclusive,
                             P(A union B) = P(A) + P(B)
```

Everything else in probability theory is derived from these three axioms.

**Derived rules:**

```
Complement rule:        P(A^c) = 1 - P(A)
Inclusion-exclusion:    P(A union B) = P(A) + P(B) - P(A intersect B)
Monotonicity:           If A subset-of B, then P(A) <= P(B)
```

**Worked Example:**

A fair six-sided die. Sample space = {1, 2, 3, 4, 5, 6}.

```
P(rolling a 3) = 1/6
P(rolling even) = P({2,4,6}) = 3/6 = 1/2
P(rolling > 4) = P({5,6}) = 2/6 = 1/3
P(rolling <= 6) = 1   (normalization)
P(rolling 7) = 0
```

---

## 3. Conditional Probability & Bayes Theorem

### 3.1 Conditional Probability

**Intuition:** You see someone holding an umbrella. What is the probability it is raining? Your belief updates based on the evidence.

**Definition:**

```
P(A | B) = P(A intersect B) / P(B),   provided P(B) > 0
```

**Chain rule (product rule):**

```
P(A, B) = P(A | B) * P(B) = P(B | A) * P(A)
```

**Independence:** A and B are independent iff:

```
P(A, B) = P(A) * P(B)   equivalently: P(A | B) = P(A)
```

### 3.2 Law of Total Probability

If B_1, B_2, ..., B_n partition Omega:

```
P(A) = sum over i of P(A | B_i) * P(B_i)
```

### 3.3 Bayes Theorem

**The most important formula in machine learning:**

```
P(H | E) = P(E | H) * P(H)
            -------------------
                  P(E)

where:
  H = Hypothesis (e.g., "patient has disease", "email is spam")
  E = Evidence   (e.g., "test result positive", "email contains 'FREE MONEY'")

  P(H)     = Prior:     your belief BEFORE seeing evidence
  P(E | H) = Likelihood: how probable is the evidence IF H is true
  P(H | E) = Posterior: your belief AFTER seeing evidence
  P(E)     = Marginal:  normalizing constant (total probability of evidence)
```

**Bayes Theorem Flow:**

```
                    ┌─────────────────────────────────┐
                    │        BAYES THEOREM FLOW        │
                    └─────────────────────────────────┘

  Prior Knowledge          Evidence              Posterior Belief
  ┌──────────────┐        ┌───────────┐         ┌──────────────┐
  │   P(H) = ?   │        │  Data /   │         │  P(H | E)    │
  │              │  +     │ Observation│  ──►   │              │
  │ (what we     │        │  E        │         │ (updated     │
  │  believed    │        └───────────┘         │  belief)     │
  │  before)     │              │               └──────────────┘
  └──────────────┘              │                      ▲
           │                    ▼                      │
           │           ┌──────────────┐                │
           └──────────►│ P(E | H)     │────────────────┘
                        │ Likelihood   │    multiply & normalize
                        └──────────────┘

  Repeat: today's posterior becomes tomorrow's prior  (Bayesian updating)
```

**Worked Example: Medical Test**

- Disease prevalence (prior): P(D) = 0.001 (1 in 1000)
- Test sensitivity: P(pos | D) = 0.99
- Test specificity: P(neg | no D) = 0.99, so P(pos | no D) = 0.01

```
P(D | pos) = P(pos | D) * P(D) / P(pos)

P(pos) = P(pos | D)*P(D) + P(pos | no D)*P(no D)
       = 0.99 * 0.001 + 0.01 * 0.999
       = 0.000990 + 0.009990
       = 0.010980

P(D | pos) = 0.99 * 0.001 / 0.010980
           ≈ 0.0902   (only ~9% chance of disease!)
```

This counterintuitive result (99% accurate test, but positive test means only 9% chance) is why base rates matter enormously.

```python
# Bayes theorem: medical test example
prior_disease = 0.001
sensitivity = 0.99     # P(pos | disease)
false_positive_rate = 0.01  # P(pos | no disease)

p_pos = sensitivity * prior_disease + false_positive_rate * (1 - prior_disease)
posterior = (sensitivity * prior_disease) / p_pos

print(f"P(disease | positive test) = {posterior:.4f} = {posterior*100:.2f}%")
# Output: P(disease | positive test) = 0.0902 = 9.02%
```

---

## 4. Random Variables

### 4.1 Definition

A **random variable** X is a function from the sample space to real numbers: X: Omega -> R.

It assigns a numerical value to each outcome.

| Type | Description | Example |
|---|---|---|
| **Discrete** | Takes countable values | Number of heads in 10 flips |
| **Continuous** | Takes uncountable values | Height of a person |
| **Mixed** | Mixture of both | Insurance payout (0 or continuous positive) |

### 4.2 Probability Mass Function (PMF) — Discrete

For discrete X:

```
p(x) = P(X = x)   satisfying:
  p(x) >= 0  for all x
  sum over all x of p(x) = 1
```

### 4.3 Probability Density Function (PDF) — Continuous

For continuous X:

```
f(x) >= 0  for all x
integral from -inf to +inf of f(x) dx = 1
P(a <= X <= b) = integral from a to b of f(x) dx
```

Note: P(X = x) = 0 for any single point x. Only intervals have non-zero probability.

### 4.4 Cumulative Distribution Function (CDF)

```
F(x) = P(X <= x)

Properties:
  F(-inf) = 0,  F(+inf) = 1
  F is non-decreasing
  For continuous X: f(x) = dF(x)/dx
```

---

## 5. Probability Distributions

### 5.1 Bernoulli Distribution

**Intuition:** Single coin flip. Binary outcome.

```
X ~ Bernoulli(p)

P(X = 1) = p       (success)
P(X = 0) = 1 - p   (failure)

PMF: p(x) = p^x * (1-p)^(1-x)   for x in {0, 1}

Mean: E[X] = p
Variance: Var(X) = p(1-p)
```

**ML usage:** Binary classification output, each pixel in a binary image model.

### 5.2 Categorical Distribution

**Intuition:** Generalization of Bernoulli to K outcomes (rolling a K-sided die).

```
X ~ Categorical(p_1, p_2, ..., p_K)

P(X = k) = p_k   where sum of p_k = 1

This is exactly what softmax outputs in a classifier!
```

### 5.3 Gaussian (Normal) Distribution

**The most important distribution in statistics and ML.**

```
X ~ N(mu, sigma^2)

PDF: f(x) = 1/(sigma * sqrt(2*pi)) * exp(-(x - mu)^2 / (2*sigma^2))

Parameters:
  mu    = mean (location)
  sigma = standard deviation (spread)
  sigma^2 = variance

Standard normal: Z ~ N(0, 1)
```

**Bell Curve (ASCII):**

```
     N(0,1) Gaussian Bell Curve
  
  0.40 |         *
       |        * *
  0.30 |       *   *
       |      *     *
  0.20 |     *       *
       |    *         *
  0.10 |   *           *
       |  *               *
  0.00 | *                   *  *
       +--+--+--+--+--+--+--+--+--
        -3 -2 -1  0  1  2  3

  68% of data falls within 1 sigma of mean
  95% of data falls within 2 sigma of mean
  99.7% of data falls within 3 sigma of mean
         (the "68-95-99.7 rule")
```

**Why Gaussian appears everywhere:**
1. Central Limit Theorem (Section 9)
2. Maximum entropy distribution given known mean and variance
3. Analytical tractability (closed-form integrals)

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# Plot multiple Gaussians
x = np.linspace(-6, 6, 300)
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Different means, same variance
for mu in [-2, 0, 2]:
    axes[0].plot(x, stats.norm.pdf(x, mu, 1), label=f'mu={mu}, sigma=1')
axes[0].set_title('Gaussian: Varying Mean')
axes[0].legend()
axes[0].set_xlabel('x')
axes[0].set_ylabel('f(x)')

# Same mean, different variances
for sigma in [0.5, 1, 2]:
    axes[1].plot(x, stats.norm.pdf(x, 0, sigma), label=f'mu=0, sigma={sigma}')
axes[1].set_title('Gaussian: Varying Std Dev')
axes[1].legend()
axes[1].set_xlabel('x')
axes[1].set_ylabel('f(x)')

plt.tight_layout()
plt.savefig('gaussians.png', dpi=150)
plt.show()

# Key statistics
rv = stats.norm(loc=0, scale=1)
print(f"P(-1 <= Z <= 1) = {rv.cdf(1) - rv.cdf(-1):.4f}")  # 0.6827
print(f"P(-2 <= Z <= 2) = {rv.cdf(2) - rv.cdf(-2):.4f}")  # 0.9545
print(f"P(-3 <= Z <= 3) = {rv.cdf(3) - rv.cdf(-3):.4f}")  # 0.9973
```

### 5.4 Beta Distribution

**Intuition:** Models a probability value (a number between 0 and 1). Perfect prior for Bernoulli/Binomial parameters.

```
X ~ Beta(alpha, beta),   X in [0, 1]

PDF: f(x) = x^(alpha-1) * (1-x)^(beta-1) / B(alpha, beta)

where B(alpha, beta) = Gamma(alpha)*Gamma(beta) / Gamma(alpha+beta)

Mean:     E[X] = alpha / (alpha + beta)
Variance: Var(X) = alpha*beta / ((alpha+beta)^2 * (alpha+beta+1))

Special cases:
  Beta(1,1) = Uniform(0,1)   (no preference)
  alpha >> beta: concentrated near 1 (biased coin favoring heads)
  alpha = beta: symmetric around 0.5
```

**ML Usage:** Conjugate prior for Bernoulli likelihood. Used in Thompson Sampling, Bayesian A/B testing.

```
Beta distribution shapes:
alpha=beta=1:   ___________  (flat, uniform)
alpha=beta=2:   _____/\_____ (bell, symmetric at 0.5)
alpha=5,beta=2:  ________/\  (skewed right, biased toward 1)
alpha=0.5,beta=0.5: U-shaped (bimodal, concentrates at edges)
```

### 5.5 Dirichlet Distribution

**Intuition:** Generalization of Beta to K categories. A distribution over probability simplex. The natural prior for Categorical/Multinomial distributions.

```
theta ~ Dirichlet(alpha_1, ..., alpha_K)

theta is a K-dimensional probability vector: sum of theta_k = 1

PDF: f(theta) proportional to product of theta_k^(alpha_k - 1)

Mean: E[theta_k] = alpha_k / (sum of alpha_i)

Symmetric Dirichlet(alpha, alpha, ..., alpha):
  alpha < 1: sparse distributions (most weight on few categories)
  alpha = 1: uniform over simplex
  alpha >> 1: concentrated near uniform distribution
```

**ML Usage:** Topic models (LDA), Bayesian multinomial classifiers, language model smoothing.

### 5.6 Poisson Distribution

**Intuition:** Number of events in a fixed interval when events occur at constant average rate independently.

```
X ~ Poisson(lambda)

PMF: P(X = k) = lambda^k * e^(-lambda) / k!    k = 0, 1, 2, ...

Mean:     E[X] = lambda
Variance: Var(X) = lambda   (mean equals variance -- a diagnostic!)
```

**ML Usage:** Count data modeling (word frequencies, click counts, network packets), Poisson regression.

```python
from scipy import stats
import numpy as np

# Distribution summary table
distributions = {
    'Bernoulli(0.3)':    stats.bernoulli(0.3),
    'Normal(0,1)':       stats.norm(0, 1),
    'Beta(2,5)':         stats.beta(2, 5),
    'Poisson(3)':        stats.poisson(3),
}

print(f"{'Distribution':<20} {'Mean':>8} {'Variance':>10}")
print("-" * 42)
for name, rv in distributions.items():
    mean = rv.mean()
    var  = rv.var()
    print(f"{name:<20} {mean:>8.4f} {var:>10.4f}")
```

---

## 6. Expectation, Variance & Covariance

### 6.1 Expectation (Expected Value)

**Intuition:** The average value you would get if you ran the random experiment infinitely many times.

```
Discrete:   E[X] = sum over x of x * p(x)
Continuous: E[X] = integral of x * f(x) dx

E[g(X)] = sum over x of g(x) * p(x)       (Law of the Unconscious Statistician)
```

**Properties (all linear):**

```
E[aX + b] = a*E[X] + b
E[X + Y]  = E[X] + E[Y]          (always, no independence needed)
E[XY]     = E[X]*E[Y]            (ONLY if X, Y independent)
```

### 6.2 Variance

**Intuition:** How spread out is the distribution around its mean?

```
Var(X) = E[(X - E[X])^2]
       = E[X^2] - (E[X])^2

Std Dev: sigma = sqrt(Var(X))

Properties:
  Var(aX + b) = a^2 * Var(X)    (constant shift doesn't affect spread)
  Var(X + Y)  = Var(X) + Var(Y) + 2*Cov(X,Y)
  Var(X + Y)  = Var(X) + Var(Y)  (if X, Y independent)
```

### 6.3 Covariance and Correlation

```
Cov(X, Y) = E[(X - E[X])(Y - E[Y])]
           = E[XY] - E[X]*E[Y]

Interpretation:
  Cov > 0: X and Y tend to increase together
  Cov < 0: when X increases, Y tends to decrease
  Cov = 0: no LINEAR relationship (but could have nonlinear dependence)

Correlation (normalized covariance):
  rho(X,Y) = Cov(X,Y) / (sigma_X * sigma_Y)     in [-1, 1]

Covariance matrix for random vector x = [x_1, ..., x_n]:
  Sigma_ij = Cov(x_i, x_j)
  Diagonal entries: Var(x_i)
  Symmetric positive semi-definite
```

```python
import numpy as np

# Simulate and compute statistics
np.random.seed(42)
n = 10000

# Correlated bivariate normal
rho = 0.7
X = np.random.randn(n)
Y = rho * X + np.sqrt(1 - rho**2) * np.random.randn(n)

print(f"Sample mean X:    {X.mean():.4f}  (expected 0)")
print(f"Sample mean Y:    {Y.mean():.4f}  (expected 0)")
print(f"Sample var X:     {X.var():.4f}   (expected 1)")
print(f"Sample var Y:     {Y.var():.4f}   (expected 1)")
print(f"Sample cov(X,Y):  {np.cov(X,Y)[0,1]:.4f}  (expected {rho})")
print(f"Sample corr(X,Y): {np.corrcoef(X,Y)[0,1]:.4f}  (expected {rho})")

# Covariance matrix
cov_matrix = np.cov(np.stack([X, Y]))
print(f"\nCovariance matrix:\n{cov_matrix}")
```

### 6.4 Jensen's Inequality

For a **convex** function f:

```
f(E[X]) <= E[f(X)]

For a concave function f:
f(E[X]) >= E[f(X)]

Key applications:
  log is concave: log(E[X]) >= E[log(X)]  (used in EM algorithm derivation)
  x^2 is convex:  E[X]^2 <= E[X^2]        (equivalent to Var(X) >= 0)
```

---

## 7. Parameter Estimation: MLE & MAP

### 7.1 The Estimation Problem

**Setup:** We observe data D = {x_1, x_2, ..., x_n} drawn i.i.d. from some distribution p(x | theta). We want to estimate theta.

### 7.2 Maximum Likelihood Estimation (MLE)

**Intuition:** Find the parameters that make the observed data most probable.

```
Likelihood:      L(theta) = P(D | theta) = product over i of p(x_i | theta)
Log-likelihood:  l(theta) = log L(theta) = sum over i of log p(x_i | theta)

MLE:  theta_MLE = argmax over theta of l(theta)
```

We use log-likelihood because:
1. Products become sums (numerically stable)
2. log is monotonically increasing, so argmax is preserved
3. Leads to cleaner derivatives

**Worked Example: Gaussian MLE**

Given n samples from N(mu, sigma^2), derive MLE estimates.

```
l(mu, sigma^2) = sum_{i=1}^{n} log [1/(sigma*sqrt(2pi)) * exp(-(x_i-mu)^2/(2sigma^2))]

= -n/2 * log(2*pi) - n/2 * log(sigma^2) - 1/(2*sigma^2) * sum(x_i - mu)^2

Taking partial derivatives and setting to zero:

d l/d mu = 0  =>  mu_MLE = (1/n) * sum(x_i)   = sample mean

d l/d sigma^2 = 0  =>  sigma^2_MLE = (1/n) * sum(x_i - mu_MLE)^2  = biased sample variance
```

Note: MLE variance is biased (divides by n, not n-1). This is because MLE is a frequentist estimator.

```python
import numpy as np
from scipy import stats
from scipy.optimize import minimize

# --- MLE for Gaussian (analytical) ---
np.random.seed(0)
true_mu, true_sigma = 3.0, 1.5
data = np.random.normal(true_mu, true_sigma, size=500)

mu_mle     = data.mean()
sigma_mle  = data.std()          # divides by n (MLE)
sigma_unbiased = data.std(ddof=1)  # divides by n-1 (unbiased)

print("=== Gaussian MLE ===")
print(f"True mu={true_mu},  MLE mu={mu_mle:.4f}")
print(f"True sigma={true_sigma},  MLE sigma={sigma_mle:.4f},  Unbiased={sigma_unbiased:.4f}")

# --- MLE from scratch using optimization ---
def neg_log_likelihood_gaussian(params, data):
    mu, log_sigma = params
    sigma = np.exp(log_sigma)   # ensure positivity
    n = len(data)
    return (n/2)*np.log(2*np.pi) + n*log_sigma + np.sum((data - mu)**2) / (2*sigma**2)

result = minimize(
    neg_log_likelihood_gaussian,
    x0=[0.0, 0.0],
    args=(data,),
    method='L-BFGS-B'
)
mu_opt, sigma_opt = result.x[0], np.exp(result.x[1])
print(f"\n=== MLE via optimization ===")
print(f"mu={mu_opt:.4f}, sigma={sigma_opt:.4f}")

# --- MLE for Bernoulli ---
coin_flips = np.random.binomial(1, 0.6, size=1000)  # true p=0.6
p_mle = coin_flips.mean()
print(f"\n=== Bernoulli MLE ===")
print(f"True p=0.6,  MLE p={p_mle:.4f}")
```

### 7.3 Maximum A Posteriori (MAP) Estimation

**Intuition:** Like MLE, but incorporate prior beliefs about parameters.

```
Posterior:  P(theta | D) proportional to P(D | theta) * P(theta)
                                         (likelihood)   (prior)

MAP:  theta_MAP = argmax over theta of [log P(D | theta) + log P(theta)]
               =     MLE term          +   regularization term

MAP with Gaussian prior N(0, tau^2) on theta:
  = argmax  [log-likelihood  -  (1/(2*tau^2)) * ||theta||^2]
  = argmin  [-log-likelihood +  lambda * ||theta||^2]       (L2 regularization!)

MAP with Laplace prior:
  = argmin  [-log-likelihood +  lambda * ||theta||_1]       (L1 regularization!)
```

**Key insight:** Regularization in ML is Bayesian MAP estimation in disguise.

| Regularization | Equivalent MAP Prior | Effect |
|---|---|---|
| L2 (Ridge) | Gaussian prior | Shrinks weights toward 0 |
| L1 (Lasso) | Laplace prior | Sparse weights (exact zeros) |
| Dropout | Approximate Bayesian inference | Weight uncertainty |
| Early stopping | Implicit prior against large weights | Regularization |

---

## 8. Information Theory

Information theory, developed by Claude Shannon in 1948, quantifies information, uncertainty, and communication. It is foundational to understanding why cross-entropy loss works.

### 8.1 Shannon Entropy

**Intuition:** How much surprise (information) is in a random variable on average? A fair coin has maximum entropy; a biased coin toward heads is more predictable, so less uncertain.

```
H(X) = -sum over x of p(x) * log_2 p(x)     (bits, using log base 2)
     = -sum over x of p(x) * ln p(x)         (nats, using natural log)
     = E[-log p(X)]

Convention: 0 * log(0) = 0 (by L'Hopital's rule)
```

**Properties:**

```
H(X) >= 0                          (entropy is non-negative)
H(X) = 0  iff X is deterministic   (no uncertainty = no entropy)
H(X) <= log |X|                    (uniform distribution maximizes entropy)
```

**Worked Example:**

```
Fair coin:  p(H) = p(T) = 0.5
H = -(0.5*log2(0.5) + 0.5*log2(0.5)) = -(0.5*(-1) + 0.5*(-1)) = 1 bit

Biased coin: p(H) = 0.9, p(T) = 0.1
H = -(0.9*log2(0.9) + 0.1*log2(0.1))
  = -(0.9*(-0.152) + 0.1*(-3.322))
  = -(-.137 - .332) = 0.469 bits   (less uncertain)

Deterministic: p(H) = 1.0
H = -(1.0 * log2(1.0)) = 0 bits   (completely certain)
```

### 8.2 Cross-Entropy

**Intuition:** How many bits do you need on average to encode samples from distribution p, if you use a code optimized for distribution q?

```
H(p, q) = -sum over x of p(x) * log q(x)
         = E_p[-log q(X)]

Note: H(p, q) >= H(p)   (cross-entropy is always >= true entropy)
      H(p, p) = H(p)    (equality when using the true distribution)
```

**Why cross-entropy is the standard loss for classification:**

In classification, p is the true label distribution (one-hot), and q is our model's predicted probabilities.

```
For a single example with true class y and predicted probs q:
  p(y) = 1,   p(k) = 0 for k != y

Cross-entropy loss = -sum_k p(k) * log q(k) = -log q(y)

Training with cross-entropy loss = maximizing log-likelihood of the true labels
under the predicted distribution. This is exactly MLE!
```

### 8.3 KL Divergence

**Intuition:** How different is distribution q from distribution p? The "extra bits" needed when using q instead of p.

```
KL(p || q) = sum over x of p(x) * log(p(x) / q(x))
           = E_p[log(p(X)/q(X))]
           = H(p, q) - H(p)    (cross-entropy minus true entropy)

Properties:
  KL(p || q) >= 0                   (Gibbs inequality)
  KL(p || q) = 0  iff p = q
  KL(p || q) != KL(q || p)          (NOT symmetric -- not a true distance)

Relationship triangle:
  Cross-entropy = Entropy + KL divergence
  H(p, q)      = H(p)   + KL(p || q)
```

**Forward vs Reverse KL:**

```
Forward KL:  KL(p || q)  -- "mean-seeking" -- q spreads to cover all modes of p
Reverse KL:  KL(q || p)  -- "mode-seeking" -- q collapses to one mode of p

This is crucial in variational inference:
  Variational Autoencoder minimizes KL(q_phi(z|x) || p(z))  (reverse KL)
  leads to mode-seeking behavior
```

**Connection diagram:**

```
  ┌─────────────────────────────────────────────────────────────┐
  │               Information Theory Connections                  │
  │                                                               │
  │   True labels p ──────────────── Model output q              │
  │                  \                 /                          │
  │                   \               /                           │
  │            Entropy  \           /  Cross-Entropy              │
  │              H(p)    \         /   H(p,q)                     │
  │                       \       /                               │
  │                        \     /                                │
  │                         \   /                                 │
  │                    KL Divergence                              │
  │                    KL(p || q) = H(p,q) - H(p)                │
  │                                                               │
  │   Minimizing cross-entropy loss                               │
  │   = Minimizing KL divergence (since H(p) is constant)        │
  │   = Maximum Likelihood Estimation                             │
  └─────────────────────────────────────────────────────────────┘
```

### 8.4 Mutual Information

**Intuition:** How much does knowing X tell you about Y?

```
I(X; Y) = KL(P(X,Y) || P(X)*P(Y))
         = H(X) + H(Y) - H(X, Y)
         = H(X) - H(X | Y)
         = H(Y) - H(Y | X)

I(X; Y) = 0  iff X and Y are independent
I(X; Y) >= 0 always
I(X; Y) = I(Y; X)   (symmetric!)
```

**ML Applications:**
- Feature selection: select features with highest mutual information with label
- Information Bottleneck: compress X to minimize I(X; Z) while maximizing I(Z; Y)
- MINE (Mutual Information Neural Estimation): estimate MI using neural networks

```python
import numpy as np
from scipy import stats

def entropy(p):
    """Shannon entropy in nats."""
    p = p[p > 0]  # remove zeros
    return -np.sum(p * np.log(p))

def cross_entropy(p, q):
    """Cross-entropy H(p, q)."""
    mask = p > 0
    return -np.sum(p[mask] * np.log(q[mask]))

def kl_divergence(p, q):
    """KL(p || q) in nats."""
    mask = p > 0
    return np.sum(p[mask] * np.log(p[mask] / q[mask]))

# Example: two distributions over 4 classes
p = np.array([0.4, 0.3, 0.2, 0.1])  # true distribution
q = np.array([0.25, 0.25, 0.25, 0.25])  # uniform prediction

print("=== Information Theory ===")
print(f"H(p)      = {entropy(p):.4f} nats")
print(f"H(q)      = {entropy(q):.4f} nats  (uniform = max entropy)")
print(f"H(p,q)    = {cross_entropy(p, q):.4f} nats")
print(f"KL(p||q)  = {kl_divergence(p, q):.4f} nats")
print(f"KL(q||p)  = {kl_divergence(q, p):.4f} nats  (asymmetric!)")
print(f"Verify: H(p,q) = H(p) + KL(p||q): {entropy(p):.4f} + {kl_divergence(p,q):.4f} = {entropy(p)+kl_divergence(p,q):.4f}")

# Classification cross-entropy loss
def cross_entropy_loss(y_true_onehot, y_pred_probs):
    """Cross-entropy loss for a batch."""
    eps = 1e-12  # numerical stability
    return -np.mean(np.sum(y_true_onehot * np.log(y_pred_probs + eps), axis=1))

# Simulate 5-class classification
np.random.seed(42)
y_true = np.eye(5)[[0, 2, 1, 4, 3]]   # one-hot encoded ground truth
# Good model predictions
y_pred_good = np.array([
    [0.8, 0.05, 0.05, 0.05, 0.05],
    [0.05, 0.05, 0.8, 0.05, 0.05],
    [0.05, 0.8, 0.05, 0.05, 0.05],
    [0.05, 0.05, 0.05, 0.05, 0.8],
    [0.05, 0.05, 0.05, 0.8, 0.05],
])
# Bad model predictions (near-uniform)
y_pred_bad = np.full((5, 5), 0.2)

print(f"\n=== Cross-Entropy Loss ===")
print(f"Good model loss: {cross_entropy_loss(y_true, y_pred_good):.4f}")
print(f"Bad model loss:  {cross_entropy_loss(y_true, y_pred_bad):.4f}")
```

---

## 9. Central Limit Theorem

### 9.1 Statement

**The Central Limit Theorem (CLT) is arguably the most important theorem in statistics.**

Let X_1, X_2, ..., X_n be i.i.d. random variables with mean mu and finite variance sigma^2. Define the sample mean:

```
X_bar_n = (1/n) * sum_{i=1}^n X_i

Then as n -> infinity:

sqrt(n) * (X_bar_n - mu) / sigma  -->  N(0, 1)   in distribution

Equivalently:

X_bar_n  ~  approximately  N(mu, sigma^2/n)   for large n
```

**The miracle:** This holds regardless of the original distribution of X_i (as long as variance is finite).

### 9.2 Why CLT Matters in ML

```
1. Error bars and confidence intervals for model metrics
2. Justifies treating mini-batch gradient estimates as Gaussian noise
3. Hypothesis testing (t-tests, z-tests) for comparing models
4. Central to understanding the geometry of high-dimensional spaces
5. Explains why SGD with many mini-batches converges to good solutions
```

### 9.3 Demonstration

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

def demonstrate_clt(distribution, n_samples, n_experiments=5000, dist_name=""):
    """Show CLT for any distribution."""
    sample_means = [distribution(size=n_samples).mean() for _ in range(n_experiments)]
    return np.array(sample_means)

np.random.seed(42)
fig, axes = plt.subplots(2, 3, figsize=(15, 8))

distributions = [
    (lambda size: np.random.uniform(0, 1, size), "Uniform(0,1)"),
    (lambda size: np.random.exponential(1, size), "Exponential(1)"),
    (lambda size: np.random.binomial(1, 0.3, size), "Bernoulli(0.3)"),
]

for col, (dist, name) in enumerate(distributions):
    for row, n in enumerate([5, 100]):
        means = demonstrate_clt(dist, n)
        ax = axes[row][col]
        ax.hist(means, bins=50, density=True, alpha=0.7, color='steelblue')

        # Overlay fitted Gaussian
        mu, sigma = means.mean(), means.std()
        x = np.linspace(mu - 4*sigma, mu + 4*sigma, 200)
        ax.plot(x, stats.norm.pdf(x, mu, sigma), 'r-', lw=2)
        ax.set_title(f'{name}\nn={n}: mean={mu:.3f}, std={sigma:.3f}')

plt.suptitle('Central Limit Theorem: Sample Means Converge to Gaussian', fontsize=14)
plt.tight_layout()
plt.savefig('clt_demo.png', dpi=150)
plt.show()
```

---

## 10. Hypothesis Testing & Confidence Intervals

### 10.1 The Framework

**Hypothesis testing** lets us decide, based on data, whether to reject a null hypothesis H_0 in favor of an alternative H_1.

```
H_0: null hypothesis    (default assumption, e.g., "drug has no effect")
H_1: alternative        (what we want to show, e.g., "drug reduces BP")

Test statistic: a function of the data that summarizes evidence against H_0
p-value: P(observing data as extreme as ours | H_0 is true)

Decision rule:
  p-value < alpha (significance level, typically 0.05) => reject H_0
  p-value >= alpha => fail to reject H_0

Error types:
  Type I error  (false positive): reject H_0 when it is true.  Rate = alpha
  Type II error (false negative): fail to reject H_0 when H_1 is true. Rate = beta
  Power = 1 - beta = P(reject H_0 | H_1 is true)
```

### 10.2 Common Tests

| Test | When to use | Test statistic |
|---|---|---|
| z-test | Known sigma, large n | z = (x_bar - mu_0) / (sigma / sqrt(n)) |
| t-test (one-sample) | Unknown sigma | t = (x_bar - mu_0) / (s / sqrt(n)) |
| t-test (two-sample) | Compare two means | Welch's t-statistic |
| Chi-squared test | Categorical data, goodness-of-fit | sum (O-E)^2/E |
| F-test | Compare variances, ANOVA | F = s_1^2 / s_2^2 |

### 10.3 Confidence Intervals

**A 95% confidence interval (CI) means:** if we repeated the experiment many times, 95% of the constructed CIs would contain the true parameter. (NOT "95% probability the true value is in this interval".)

```
For mean with known sigma (z-interval):
  CI = [x_bar - z_{alpha/2} * sigma/sqrt(n),
        x_bar + z_{alpha/2} * sigma/sqrt(n)]

For 95% CI: z_{0.025} = 1.96

For mean with unknown sigma (t-interval):
  CI = [x_bar - t_{alpha/2, n-1} * s/sqrt(n),
        x_bar + t_{alpha/2, n-1} * s/sqrt(n)]
```

```python
import numpy as np
from scipy import stats

np.random.seed(42)
# Simulate click-through rates for a web feature
control_data = np.random.binomial(1, 0.05, size=1000)  # 5% true CTR

# One-sample t-test: is CTR significantly different from 4%?
t_stat, p_value = stats.ttest_1samp(control_data, popmean=0.04)
print(f"=== One-sample t-test ===")
print(f"Sample mean: {control_data.mean():.4f}")
print(f"t-statistic: {t_stat:.4f}")
print(f"p-value: {p_value:.4f}")
print(f"Reject H0 (CTR=4%) at alpha=0.05: {p_value < 0.05}")

# Confidence interval for mean
ci = stats.t.interval(0.95, df=len(control_data)-1,
                      loc=control_data.mean(),
                      scale=stats.sem(control_data))
print(f"\n95% Confidence Interval: ({ci[0]:.4f}, {ci[1]:.4f})")

# Two-sample t-test: compare control vs treatment
treatment_data = np.random.binomial(1, 0.07, size=1000)  # 7% true CTR (lift!)
t_stat2, p_value2 = stats.ttest_ind(control_data, treatment_data)
print(f"\n=== Two-sample t-test (A/B test) ===")
print(f"Control mean:   {control_data.mean():.4f}")
print(f"Treatment mean: {treatment_data.mean():.4f}")
print(f"p-value: {p_value2:.4f}")
print(f"Significant at alpha=0.05: {p_value2 < 0.05}")
```

---

## 11. A/B Testing in ML Systems

### 11.1 What is A/B Testing?

A/B testing is the gold standard for evaluating ML model changes in production. You split users into two groups: **control** (A, old model) and **treatment** (B, new model).

```
┌─────────────────────────────────────────────────────┐
│                A/B TEST PIPELINE                     │
│                                                       │
│  User Traffic                                         │
│      │                                               │
│      ├──── 50% ────► Group A (Control: old model)    │
│      │                   │                           │
│      └──── 50% ────► Group B (Treatment: new model)  │
│                           │                          │
│  Collect metrics (CTR, revenue, engagement, etc.)    │
│      │                                               │
│  Statistical significance test                       │
│      │                                               │
│  Decision: ship B, revert, or run longer?            │
└─────────────────────────────────────────────────────┘
```

### 11.2 Sample Size Calculation

Before running a test, determine required sample size:

```
n = (z_{alpha/2} + z_beta)^2 * (sigma_A^2 + sigma_B^2) / delta^2

where:
  delta = minimum detectable effect (MDE)
  alpha = significance level (0.05)
  beta  = desired Type II error (0.2 for 80% power)
  z_{0.025} = 1.96,  z_{0.2} = 0.84
```

### 11.3 Common Pitfalls

| Pitfall | Description | Fix |
|---|---|---|
| Peeking | Stopping test early when p < 0.05 | Pre-register stopping criteria |
| Multiple comparisons | Testing many metrics inflates Type I error | Bonferroni correction |
| Sample ratio mismatch | Groups not 50/50 due to bugs | Check traffic split first |
| Network effects | Users in A and B interact | Use cluster randomization |
| Novelty effect | Users explore new UI but revert | Run test long enough |

```python
from scipy import stats
import numpy as np

def ab_test_analysis(control_successes, control_n, treatment_successes, treatment_n, alpha=0.05):
    """Complete A/B test analysis for conversion rate."""
    p_control   = control_successes / control_n
    p_treatment = treatment_successes / treatment_n
    lift        = (p_treatment - p_control) / p_control * 100

    # Z-test for proportions
    p_pool  = (control_successes + treatment_successes) / (control_n + treatment_n)
    se_pool = np.sqrt(p_pool * (1-p_pool) * (1/control_n + 1/treatment_n))
    z_stat  = (p_treatment - p_control) / se_pool
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))  # two-tailed

    # Confidence interval for the difference
    se_diff = np.sqrt(p_control*(1-p_control)/control_n + p_treatment*(1-p_treatment)/treatment_n)
    ci_diff = (p_treatment - p_control) + np.array([-1, 1]) * 1.96 * se_diff

    print(f"Control:   {p_control:.4f} ({control_successes}/{control_n})")
    print(f"Treatment: {p_treatment:.4f} ({treatment_successes}/{treatment_n})")
    print(f"Lift:      {lift:.2f}%")
    print(f"z-statistic: {z_stat:.4f}")
    print(f"p-value:     {p_value:.4f}")
    print(f"95% CI for difference: ({ci_diff[0]:.4f}, {ci_diff[1]:.4f})")
    print(f"Significant at alpha={alpha}: {p_value < alpha}")
    return p_value < alpha

print("=== A/B Test: Homepage CTA button color ===")
significant = ab_test_analysis(
    control_successes=450, control_n=10000,
    treatment_successes=510, treatment_n=10000
)
```

---

## 12. Quiz

Test your understanding with these 10 questions. Answers follow.

---

**Q1.** You flip a fair coin 3 times. What is the probability of getting exactly 2 heads?

**Q2.** Given P(A) = 0.4, P(B) = 0.3, P(A intersect B) = 0.12. Are A and B independent? Compute P(A | B).

**Q3.** A spam filter has: P(spam) = 0.2, P(word "FREE" | spam) = 0.6, P(word "FREE" | not spam) = 0.05. If an email contains "FREE", what is P(spam | "FREE")?

**Q4.** For X ~ N(3, 4) (mean=3, variance=4), what is P(1 < X < 5)? (Use the 68-95-99.7 rule.)

**Q5.** What is the entropy H(p) in bits when p = [0.5, 0.25, 0.25]? Show work.

**Q6.** Why is cross-entropy loss (and not mean squared error) the standard for classification? Give an information-theoretic justification.

**Q7.** Is KL(p||q) = KL(q||p)? Give a concrete numerical counterexample showing they differ.

**Q8.** A dataset has 1000 i.i.d. samples from a Bernoulli(p) distribution with 650 ones. What is p_MLE?

**Q9.** L2 regularization in a neural network is equivalent to MAP estimation with what prior on the weights?

**Q10.** You run an A/B test for 2 weeks. Each day you check if p < 0.05. If you stop the test whenever p < 0.05, what problem does this create and what is the actual Type I error rate?

---

### Quiz Solutions

**A1.** C(3,2) * (0.5)^2 * (0.5)^1 = 3 * 0.25 * 0.5 = **3/8 = 0.375**

**A2.** P(A)*P(B) = 0.4*0.3 = 0.12 = P(A intersect B), so **yes, independent**. P(A|B) = P(A intersect B)/P(B) = 0.12/0.3 = **0.4 = P(A)** (consistent with independence).

**A3.** Apply Bayes:
```
P(F) = P(F|spam)*P(spam) + P(F|not spam)*P(not spam)
     = 0.6*0.2 + 0.05*0.8 = 0.12 + 0.04 = 0.16
P(spam | F) = 0.12/0.16 = 0.75
```
**P(spam | "FREE") = 0.75**

**A4.** X ~ N(3, 4), so sigma = 2. Interval [1, 5] = [mu - sigma, mu + sigma]. By the 68-95-99.7 rule, **P(1 < X < 5) ≈ 0.6827**

**A5.**
```
H = -(0.5*log2(0.5) + 0.25*log2(0.25) + 0.25*log2(0.25))
  = -(0.5*(-1) + 0.25*(-2) + 0.25*(-2))
  = -(-0.5 - 0.5 - 0.5)
  = 1.5 bits
```

**A6.** Cross-entropy H(p, q) = E_p[-log q(X)] measures the expected log-probability assigned by model q to true distribution p. Minimizing cross-entropy is equivalent to minimizing KL(p||q) (since H(p) is fixed) and equivalent to MLE. MSE, by contrast, implies a Gaussian noise model which is wrong for discrete labels.

**A7.** Let p=[0.9, 0.1], q=[0.5, 0.5]:
```
KL(p||q) = 0.9*log(0.9/0.5) + 0.1*log(0.1/0.5) = 0.9*0.588 + 0.1*(-1.609) ≈ 0.368
KL(q||p) = 0.5*log(0.5/0.9) + 0.5*log(0.5/0.1) = 0.5*(-0.588) + 0.5*(1.609) ≈ 0.511
```
**KL(p||q) ≈ 0.368 != 0.511 ≈ KL(q||p)**

**A8.** For Bernoulli MLE: p_MLE = (number of successes) / n = **650/1000 = 0.65**

**A9.** **Gaussian prior** N(0, tau^2) on each weight. The MAP objective becomes: argmin [-log-likelihood + (1/(2*tau^2))*||w||^2], where lambda = 1/(2*tau^2).

**A10.** This is **"peeking"** or optional stopping. Each daily check is a new hypothesis test. With 14 daily checks at alpha=0.05, the actual Type I error rate is approximately 1 - (1-0.05)^14 ≈ **51%** -- far above the nominal 5%. Fix with pre-registered stopping rules, sequential testing methods (e.g., alpha-spending functions), or Bayesian approaches.

---

## 13. Practical Exercises

### Exercise 1: MLE for Exponential Distribution

**Problem:** You observe waiting times (in minutes): [2.1, 0.8, 3.5, 1.2, 4.7, 0.3, 2.8, 1.5]. Derive and compute the MLE for the rate parameter lambda of an Exponential distribution.

**Solution:**

```
Exponential PDF: f(x | lambda) = lambda * exp(-lambda * x),  x >= 0

Log-likelihood: l(lambda) = n*log(lambda) - lambda * sum(x_i)

d l / d lambda = n/lambda - sum(x_i) = 0

lambda_MLE = n / sum(x_i) = 1 / x_bar
```

```python
import numpy as np
from scipy import stats

data = np.array([2.1, 0.8, 3.5, 1.2, 4.7, 0.3, 2.8, 1.5])

# Analytical MLE
lambda_mle = 1 / data.mean()
print(f"lambda_MLE = 1/mean = 1/{data.mean():.4f} = {lambda_mle:.4f}")

# Verify: scipy fits scale = 1/lambda
loc, scale = stats.expon.fit(data, floc=0)
print(f"scipy MLE:  lambda = {1/scale:.4f}")

# Confidence interval via bootstrap
n_boot = 10000
bootstrap_lambdas = [1/np.random.choice(data, len(data), replace=True).mean()
                     for _ in range(n_boot)]
ci = np.percentile(bootstrap_lambdas, [2.5, 97.5])
print(f"Bootstrap 95% CI: ({ci[0]:.4f}, {ci[1]:.4f})")
```

---

### Exercise 2: Implement Naive Bayes Classifier from Scratch

**Problem:** Build a Gaussian Naive Bayes classifier. Demonstrate on a synthetic 2-class dataset.

**Solution:**

```python
import numpy as np
from scipy import stats
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

class GaussianNaiveBayes:
    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.priors_ = {}
        self.means_  = {}
        self.stds_   = {}
        for c in self.classes_:
            X_c = X[y == c]
            self.priors_[c] = len(X_c) / len(X)  # P(class)
            self.means_[c]  = X_c.mean(axis=0)    # mu per feature per class
            self.stds_[c]   = X_c.std(axis=0) + 1e-9  # sigma (avoid /0)
        return self

    def predict_log_proba(self, X):
        log_probs = []
        for c in self.classes_:
            log_prior = np.log(self.priors_[c])
            # Gaussian log-likelihood for each feature (Naive: assume independence)
            log_likelihood = np.sum(
                stats.norm.logpdf(X, self.means_[c], self.stds_[c]), axis=1
            )
            log_probs.append(log_prior + log_likelihood)
        return np.column_stack(log_probs)

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_log_proba(X), axis=1)]

# Test
X, y = make_classification(n_samples=1000, n_features=4, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

gnb = GaussianNaiveBayes().fit(X_train, y_train)
accuracy = (gnb.predict(X_test) == y_test).mean()
print(f"Gaussian Naive Bayes accuracy: {accuracy:.4f}")
```

---

### Exercise 3: Entropy and Information Gain for Decision Trees

**Problem:** Compute information gain for a binary split. Dataset has 10 positives and 10 negatives (root). After split on feature F: left child has 8 pos, 2 neg; right child has 2 pos, 8 neg.

**Solution:**

```python
def entropy_binary(p):
    """Binary entropy in bits."""
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * np.log2(p) + (1-p) * np.log2(1-p))

# Root node: 10 pos, 10 neg
n_root = 20
p_root = 10/20
H_root = entropy_binary(p_root)

# Left child: 8 pos, 2 neg (n=10)
n_left, p_left = 10, 8/10
H_left = entropy_binary(p_left)

# Right child: 2 pos, 8 neg (n=10)
n_right, p_right = 10, 2/10
H_right = entropy_binary(p_right)

# Weighted entropy after split
H_after = (n_left/n_root)*H_left + (n_right/n_root)*H_right

information_gain = H_root - H_after

print(f"H(root)  = {H_root:.4f} bits  (maximum, balanced)")
print(f"H(left)  = {H_left:.4f} bits")
print(f"H(right) = {H_right:.4f} bits")
print(f"H(after) = {H_after:.4f} bits")
print(f"Information Gain = {information_gain:.4f} bits")
```

---

### Exercise 4: Visualize KL Divergence Between Two Gaussians

**Problem:** Plot KL(N(0,1) || N(mu, 1)) as mu varies from -3 to 3.

**Solution:**

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

def kl_gaussian(mu1, sigma1, mu2, sigma2):
    """Analytical KL divergence between two Gaussians."""
    # KL(N(mu1,s1^2) || N(mu2,s2^2)) = log(s2/s1) + (s1^2+(mu1-mu2)^2)/(2*s2^2) - 1/2
    return (np.log(sigma2/sigma1)
            + (sigma1**2 + (mu1-mu2)**2) / (2*sigma2**2)
            - 0.5)

mus = np.linspace(-4, 4, 200)
kl_forward  = [kl_gaussian(0, 1, mu, 1) for mu in mus]  # KL(p || q)
kl_backward = [kl_gaussian(mu, 1, 0, 1) for mu in mus]  # KL(q || p)

plt.figure(figsize=(10, 5))
plt.plot(mus, kl_forward,  'b-', lw=2, label='KL(N(0,1) || N(mu,1))')
plt.plot(mus, kl_backward, 'r--', lw=2, label='KL(N(mu,1) || N(0,1))')
plt.axvline(0, color='gray', linestyle=':')
plt.axhline(0, color='gray', linestyle=':')
plt.xlabel('mu')
plt.ylabel('KL Divergence (nats)')
plt.title('KL Divergence Between Two Gaussians')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('kl_gaussians.png', dpi=150)
plt.show()

# At mu=0: both should be 0
print(f"KL at mu=0: {kl_gaussian(0,1,0,1):.6f}  (should be 0)")
# At mu=1: show asymmetry
print(f"KL(N(0,1)||N(1,1)) = {kl_gaussian(0,1,1,1):.4f}")
print(f"KL(N(1,1)||N(0,1)) = {kl_gaussian(1,1,0,1):.4f}  (equal for Gaussians with same sigma!)")
```

---

### Exercise 5: Bootstrap Confidence Intervals for Model Accuracy

**Problem:** You have a classifier with 87/100 correct predictions. Compute a 95% bootstrap CI for accuracy.

**Solution:**

```python
import numpy as np

np.random.seed(42)
# Simulate 100 predictions: 1=correct, 0=incorrect
predictions = np.array([1]*87 + [0]*13)  # 87% accuracy

# Bootstrap
n_bootstrap = 10000
bootstrap_accuracies = []
for _ in range(n_bootstrap):
    sample = np.random.choice(predictions, size=len(predictions), replace=True)
    bootstrap_accuracies.append(sample.mean())

ci_lower, ci_upper = np.percentile(bootstrap_accuracies, [2.5, 97.5])
print(f"Observed accuracy:    {predictions.mean():.4f}")
print(f"Bootstrap mean:       {np.mean(bootstrap_accuracies):.4f}")
print(f"Bootstrap std:        {np.std(bootstrap_accuracies):.4f}")
print(f"95% CI: ({ci_lower:.4f}, {ci_upper:.4f})")

# Compare to exact Clopper-Pearson interval (from scipy)
from scipy.stats import binom
ci_exact = binom.interval(0.95, n=100, p=0.87)
print(f"Exact Clopper-Pearson CI: ({ci_exact[0]/100:.4f}, {ci_exact[1]/100:.4f})")
```

---

## 14. References

### Core Textbooks

| Resource | Description | Access |
|---|---|---|
| **Pattern Recognition and ML** (Bishop) | The definitive Bayesian ML textbook | [Free PDF from Microsoft](https://www.microsoft.com/en-us/research/uploads/prod/2006/01/Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf) |
| **The Elements of Statistical Learning** (Hastie et al.) | Comprehensive statistical ML | [Free PDF from Stanford](https://hastie.su.domains/ElemStatLearn/) |
| **Information Theory, Inference, and Learning Algorithms** (MacKay) | Deep info-theory connection to ML | [Free online](http://www.inference.org.uk/mackay/itila/) |
| **Probabilistic Graphical Models** (Koller & Friedman) | Bayesian networks, MRFs | Graduate level |

### Online Courses

| Resource | Platform | Focus |
|---|---|---|
| **MIT 6.041: Probabilistic Systems Analysis** | [MIT OCW](https://ocw.mit.edu/courses/6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/) | Rigorous probability theory |
| **Khan Academy Statistics** | [Khan Academy](https://www.khanacademy.org/math/statistics-probability) | Accessible intro, free |
| **StatQuest with Josh Starmer** | [YouTube](https://www.youtube.com/@statquest) | Intuitive ML statistics |
| **CS229 Machine Learning** (Andrew Ng) | [Stanford/YouTube](https://cs229.stanford.edu/) | MLE, MAP, distributions in ML |

### Python Libraries

```python
# The essential stack for this module
import numpy as np          # numerical computing, random number generation
import scipy.stats          # probability distributions, hypothesis tests
import matplotlib.pyplot as plt  # visualization
import seaborn as sns       # statistical visualization
from sklearn.preprocessing import LabelBinarizer  # one-hot encoding
```

### Key Formulas Cheat Sheet

```
PROBABILITY
  P(A|B) = P(A,B)/P(B)                    conditional probability
  P(H|E) = P(E|H)*P(H)/P(E)              Bayes theorem

DISTRIBUTIONS
  N(x; mu, sigma^2) = exp(-(x-mu)^2/2sigma^2) / (sigma*sqrt(2pi))
  Bernoulli(x; p)   = p^x * (1-p)^(1-x)
  Poisson(k; lam)   = lam^k * e^(-lam) / k!

ESTIMATION
  MLE: theta* = argmax sum log p(x_i | theta)
  MAP: theta* = argmax [sum log p(x_i | theta) + log p(theta)]

INFORMATION THEORY
  H(p)     = -E[log p(X)]                 entropy
  H(p,q)   = -E_p[log q(X)]              cross-entropy
  KL(p||q) = E_p[log p(X)/q(X)]          KL divergence
  I(X;Y)   = H(X) - H(X|Y)               mutual information
  H(p,q)   = H(p) + KL(p||q)             fundamental identity
```

---

*Next module: **04 - Deep Learning Foundations** (neural network architectures, backpropagation, optimizers)*

*Previous module: **02 - Calculus & Optimization for ML** (gradients, automatic differentiation, convex optimization)*
