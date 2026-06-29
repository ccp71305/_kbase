# 08 — Recurrent Neural Networks, LSTMs & Sequence Models

> **Series:** AI / Deep Machine Learning  
> **Prerequisites:** Chapters 01–07 (neural networks, backprop, CNNs)  
> **Difficulty:** Intermediate–Advanced  
> **Estimated reading time:** 45–60 minutes

---

## Table of Contents

1. [Why Sequences Are Different](#1-why-sequences-are-different)
2. [Recurrent Neural Networks (RNNs)](#2-recurrent-neural-networks-rnns)
   - 2.1 Architecture & the Hidden State
   - 2.2 Unrolling Through Time
   - 2.3 Backpropagation Through Time (BPTT)
   - 2.4 The Vanishing Gradient Problem
3. [Long Short-Term Memory (LSTM)](#3-long-short-term-memory-lstm)
   - 3.1 The Cell State — A Highway for Gradients
   - 3.2 The Forget Gate
   - 3.3 The Input Gate
   - 3.4 The Output Gate
   - 3.5 Full LSTM Equations
   - 3.6 Why LSTMs Solve Vanishing Gradients
4. [Gated Recurrent Units (GRUs)](#4-gated-recurrent-units-grus)
   - 4.1 Simplified Gating
   - 4.2 LSTM vs GRU — When to Choose Which
5. [Sequence-to-Sequence Models](#5-sequence-to-sequence-models)
   - 5.1 Encoder–Decoder Architecture
   - 5.2 Teacher Forcing
   - 5.3 Attention Mechanism (Bridge to Transformers)
6. [Applications of Sequence Models](#6-applications-of-sequence-models)
   - 6.1 Time Series Forecasting
   - 6.2 Text Generation
   - 6.3 Named Entity Recognition (NER)
   - 6.4 Sentiment Analysis
7. [RNN vs Transformer — Practical Decision Guide](#7-rnn-vs-transformer--practical-decision-guide)
8. [Time Series Deep Dive](#8-time-series-deep-dive)
   - 8.1 Windowing & Strides
   - 8.2 Stationarity
   - 8.3 ARIMA vs LSTM Comparison
9. [Practical Considerations & Implementation Tips](#9-practical-considerations--implementation-tips)
10. [Quiz — 10 Questions With Solutions](#10-quiz--10-questions-with-solutions)
11. [Project: LSTM Time Series Forecasting](#11-project-lstm-time-series-forecasting)
12. [References & Further Reading](#12-references--further-reading)

---

## 1. Why Sequences Are Different

Standard feedforward networks and CNNs assume that each input is **independent and identically distributed (i.i.d.)**. Feed a network an image, get a label. Feed it another image, get another label — the two predictions share no state.

Real-world data frequently violates this assumption:

| Domain | Sequence Type | Order Matters? |
|---|---|---|
| Natural language | "dog bites man" vs "man bites dog" | Yes — completely different meaning |
| Stock prices | Daily closing price over N years | Yes — trend, seasonality, momentum |
| Audio / speech | Waveform samples at 44 kHz | Yes — phoneme context window |
| DNA / protein | Nucleotide / amino acid sequence | Yes — codon context |
| Video | Frames at 24 fps | Yes — motion between frames |
| Sensor streams | IoT readings | Yes — anomaly detection needs history |

Three properties define sequence problems:

1. **Variable-length inputs and outputs.** A sentence can be 4 words or 400 words; a feedforward network requires a fixed input size.
2. **Long-range dependencies.** The word "it" in a 50-word sentence might refer to a noun 30 tokens earlier.
3. **Parameter sharing over time.** The grammar rule "a verb follows a subject" applies at position 2 and at position 200. Learning separate weights for each time step would be intractable.

Recurrent Neural Networks were designed to handle all three of these challenges.

---

## 2. Recurrent Neural Networks (RNNs)

### 2.1 Architecture & the Hidden State

An RNN introduces a **hidden state** `h_t` that acts as a compressed memory of everything the network has seen up to time step `t`.

The core recurrence relation:

```
h_t = tanh(W_hh · h_{t-1}  +  W_xh · x_t  +  b_h)
y_t = W_hy · h_t  +  b_y
```

Where:
- `x_t`   — input vector at time t
- `h_t`   — hidden state at time t  (the "memory")
- `y_t`   — output at time t
- `W_hh`  — hidden-to-hidden weight matrix  (shared across ALL time steps)
- `W_xh`  — input-to-hidden weight matrix   (shared across ALL time steps)
- `W_hy`  — hidden-to-output weight matrix
- `b_h, b_y` — bias vectors

The critical insight: **the same weights W_hh, W_xh, W_hy are reused at every time step**. This is parameter sharing — the network learns generalizable temporal patterns rather than memorising position-specific features.

### 2.2 Unrolling Through Time

Although an RNN is defined recursively, we can "unroll" it into a feedforward-like graph for visualisation and for computing gradients.

```
INPUT SEQUENCE:   x_1      x_2      x_3      x_4      x_5
                   |        |        |        |        |
                   v        v        v        v        v
            h_0 --[RNN]--> [RNN]--> [RNN]--> [RNN]--> [RNN]--> h_5
                    |        |        |        |        |
                    v        v        v        v        v
                   y_1      y_2      y_3      y_4      y_5

  Each [RNN] block applies:   h_t = tanh(W_hh*h_{t-1} + W_xh*x_t + b_h)
  SAME weights W_hh, W_xh at every step (parameter sharing)
```

**RNN modes of operation** (different input/output topologies):

```
  Many-to-Many        Many-to-One         One-to-Many
  (seq labelling)     (classification)    (generation)

  x x x x x          x x x x x          x
  | | | | |          | | | | |          |
 [R][R][R][R][R]    [R][R][R][R][R]    [R][R][R][R][R]
  | | | | |                    |        | | | | |
  y y y y y                    y        y y y y y

  Example: NER       Example: sentiment  Example: caption
```

### 2.3 Backpropagation Through Time (BPTT)

To train an RNN we unroll it and apply standard backpropagation on the unrolled graph — this is called **Backpropagation Through Time (BPTT)**.

Given a loss `L = Σ_t L_t(y_t, ŷ_t)`, we need `∂L/∂W_hh`.

Because the same W_hh appears at every time step, the total gradient is the **sum of gradients from every time step**:

```
∂L/∂W_hh  =  Σ_{t=1}^{T}  ∂L_t/∂W_hh
```

The gradient of the loss at step `t` with respect to the hidden state at step `k < t` involves a chain of Jacobians:

```
∂h_t/∂h_k  =  Π_{j=k+1}^{t}  ∂h_j/∂h_{j-1}
            =  Π_{j=k+1}^{t}  diag(tanh'(a_j)) · W_hh
```

Where `a_j = W_hh·h_{j-1} + W_xh·x_j + b_h` is the pre-activation.

**Key observation:** this product contains `(t - k)` copies of `W_hh` multiplied together. This is the root of both the vanishing and exploding gradient problems.

**Truncated BPTT:** In practice, unrolling hundreds of steps is expensive. We often unroll for a fixed number of steps `k` (e.g. 35) and treat earlier history as fixed — this is truncated BPTT.

### 2.4 The Vanishing Gradient Problem

If the largest singular value of `W_hh` is `< 1`, the product `Π W_hh` shrinks exponentially:

```
After t steps:   ||∂h_t/∂h_0||  ≈  σ_max(W_hh)^t  →  0
```

Gradients from distant time steps effectively become zero — the network **cannot learn long-range dependencies**.

Conversely, if `σ_max(W_hh) > 1`, gradients **explode** (usually handled with gradient clipping: `g ← g · min(1, threshold / ||g||)`).

The tanh activation compounds the problem — its derivative is at most 1 and is close to 0 in saturation, so the `diag(tanh'(a_j))` term further shrinks gradients.

**Practical consequence:** vanilla RNNs struggle to remember information from more than ~10–20 time steps ago, regardless of network size or training time.

---

## 3. Long Short-Term Memory (LSTM)

Hochreiter & Schmidhuber (1997) introduced the LSTM to directly address the vanishing gradient problem. The core idea: instead of letting gradients flow only through the hidden state (which gets squashed by repeated tanh/sigmoid applications), introduce a **cell state `C_t`** that can carry information across arbitrarily many time steps with minimal transformation.

### LSTM Cell — Internal Architecture

```
                        C_{t-1} ──────(+)──────────────── C_t
                                       ^                    |
                                   f_t |  i_t * g_t        |
                                       |                   tanh
   h_{t-1} ─┐                         |                    |  * o_t
   x_t      ─┤──► [Forget σ]──f_t─────┘                    ▼
             │                                            h_t ────►
             ├──► [Input  σ]──i_t──┐
             │                     ├──►  i_t ⊙ g_t
             ├──► [Gate  tanh]─g_t─┘
             │
             └──► [Output σ]──o_t

  σ = sigmoid,  tanh = hyperbolic tangent,  ⊙ = element-wise multiply
```

### 3.1 The Cell State — A Highway for Gradients

The cell state `C_t` flows from left to right through the LSTM with only **element-wise operations** (no matrix multiplication on the main path). This means gradients can flow backward through time along `C_t` with very little attenuation — the "constant error carousel" as Hochreiter originally called it.

### 3.2 The Forget Gate

Decides what information to **discard** from the previous cell state.

```
f_t  =  σ( W_f · [h_{t-1}, x_t]  +  b_f )
```

- Output range: (0, 1) element-wise
- `f_t ≈ 0` → forget this dimension of cell state
- `f_t ≈ 1` → keep this dimension of cell state

**Example:** In language modelling, when the model sees a new subject ("The cat ... the dogs"), the forget gate fires to clear the stored gender of the old subject so the verb can agree with the new one.

### 3.3 The Input Gate

Decides what **new information** to write into the cell state. Two components:

```
i_t  =  σ( W_i · [h_{t-1}, x_t]  +  b_i )   # how much to write
g_t  =  tanh( W_g · [h_{t-1}, x_t]  +  b_g ) # what to write (candidate)
```

New information added to cell state: `i_t ⊙ g_t`

### 3.4 The Output Gate

Decides what part of the cell state to **expose** as the hidden state `h_t`.

```
o_t  =  σ( W_o · [h_{t-1}, x_t]  +  b_o )
h_t  =  o_t  ⊙  tanh(C_t)
```

### 3.5 Full LSTM Equations

Putting it together — the complete LSTM forward pass at time step `t`:

```
Forget gate:    f_t  =  σ( W_f · [h_{t-1}, x_t]  +  b_f )
Input gate:     i_t  =  σ( W_i · [h_{t-1}, x_t]  +  b_i )
Candidate:      g_t  =  tanh( W_g · [h_{t-1}, x_t]  +  b_g )
Output gate:    o_t  =  σ( W_o · [h_{t-1}, x_t]  +  b_o )

Cell state:     C_t  =  f_t  ⊙  C_{t-1}  +  i_t  ⊙  g_t
Hidden state:   h_t  =  o_t  ⊙  tanh(C_t)
```

**Parameter count for LSTM layer** (input dim `d`, hidden dim `h`):
- 4 weight matrices, each of shape `(h, d+h)` → `4h(d+h)` weights
- 4 bias vectors of size `h` → `4h` biases
- Total: `4h(d + h + 1)` parameters

Compare to vanilla RNN: `h(d + h + 1)` — LSTM has ~4x more parameters.

### 3.6 Why LSTMs Solve Vanishing Gradients

The gradient of the cell state `C_t` with respect to `C_{t-1}`:

```
∂C_t/∂C_{t-1}  =  f_t   (element-wise)
```

This is just the forget gate — no repeated matrix multiplication, no squashing nonlinearity. If the forget gate stays near 1 for many steps, gradients flow back essentially unchanged. The LSTM can learn to keep `f_t ≈ 1` when it needs long-range memory, and `f_t ≈ 0` when old information should be discarded — the gates themselves are learned from data.

---

## 4. Gated Recurrent Units (GRUs)

Cho et al. (2014) proposed the GRU as a simplification of the LSTM that achieves comparable performance with fewer parameters.

### 4.1 Simplified Gating

The GRU merges the forget and input gates into a single **update gate**, and eliminates the separate cell state:

```
Reset gate:    r_t  =  σ( W_r · [h_{t-1}, x_t]  +  b_r )
Update gate:   z_t  =  σ( W_z · [h_{t-1}, x_t]  +  b_z )
Candidate:     h̃_t  =  tanh( W_h · [r_t ⊙ h_{t-1}, x_t]  +  b_h )
New state:     h_t  =  (1 - z_t) ⊙ h_{t-1}  +  z_t ⊙  h̃_t
```

```
GRU Cell Diagram:

  h_{t-1} ──┬───────────────────────────────────(1-z)──────┐
             │                                               ▼
   x_t  ────┼──► [Reset σ]──r_t──► r⊙h                   (+)──► h_t
             │                      |                       ^
             ├──► [Update σ]──z_t───┤             z_t ──►  |
             │                      ▼                       |
             └──────────────► [Candidate tanh]────h̃_t───►──┘
```

**Reset gate `r_t`:** Controls how much of the previous hidden state is used when computing the candidate. Low reset → candidate is computed mostly from `x_t`, ignoring history — allows the model to "forget" when context switches.

**Update gate `z_t`:** Controls how much of the old hidden state to carry forward vs how much of the new candidate to adopt. When `z_t = 0`, the hidden state is copied unchanged (analogous to forget=1, input=0 in LSTM). When `z_t = 1`, the hidden state is fully replaced.

### 4.2 LSTM vs GRU — When to Choose Which

| Property | LSTM | GRU |
|---|---|---|
| Parameters | ~4x(d+h)h | ~3x(d+h)h |
| Expressiveness | Slightly higher | Slightly lower |
| Training speed | Slower (more params) | Faster |
| Short sequences | Good | Good |
| Long sequences (>200 steps) | Better (separate cell state) | Can struggle |
| Small datasets | Can overfit | Less likely to overfit |
| Empirical winner | Task-dependent | Task-dependent |

**Practical rule of thumb:** Start with GRU (faster iteration). Switch to LSTM if you have long-range dependencies > 100 steps or if performance is unsatisfactory. In practice, the difference is often within noise — hyperparameter tuning (hidden size, dropout, learning rate) has more impact than LSTM vs GRU choice.

---

## 5. Sequence-to-Sequence Models

Seq2seq (Sutskever et al., 2014) maps an **input sequence of arbitrary length** to an **output sequence of arbitrary length** — e.g. machine translation, summarisation, speech recognition.

### 5.1 Encoder–Decoder Architecture

```
INPUT:   "The cat sat"
         x_1    x_2    x_3

ENCODER (reads input):
         [LSTM]─[LSTM]─[LSTM]
                              │
                         context vector c
                         (final encoder hidden state)
                              │
DECODER (generates output):  │
         [LSTM]─[LSTM]─[LSTM]─[LSTM]
          |      |      |      |
         "Le"  "chat"  "s'est" "assis"

OUTPUT: "Le chat s'est assis"

Full Architecture:

x_1  x_2  x_3  <EOS>               y_1  y_2  y_3  y_4  <EOS>
 |    |    |    |                    |    |    |    |    |
[E1]─[E2]─[E3]─┤                   [D1]─[D2]─[D3]─[D4]─[D5]
                └──── c ────────────►
                  (context vector passed as initial decoder state)
```

**Encoder:** Processes the entire input sequence and compresses it into a fixed-size context vector `c` (typically the final hidden state).

**Decoder:** An autoregressive language model conditioned on `c`. At each step it takes the previous output token (or ground-truth token during training — see teacher forcing) and produces the next token.

**Bottleneck problem:** The entire input must be compressed into a single vector `c`. For long sequences this is lossy — the network has to "remember" a 500-word article in, say, 512 floats. This limitation motivated the attention mechanism.

### 5.2 Teacher Forcing

During training, the decoder can be fed the **ground-truth** previous token rather than its own (possibly wrong) prediction:

```
Without teacher forcing (inference mode):
  Decoder step 1: input = <BOS>        → predicts "Le"
  Decoder step 2: input = "Le"         → predicts "chat"   (if step 1 was correct)
                  input = predicted_1  → predicts "???"    (if step 1 was wrong, error cascades)

With teacher forcing (training mode):
  Decoder step 1: input = <BOS>        → target "Le"
  Decoder step 2: input = "Le" (TRUE)  → target "chat"
  Decoder step 3: input = "chat" (TRUE)→ target "s'est"
```

**Benefits:** Faster convergence, stable gradients, simpler implementation.

**Drawbacks:** **Exposure bias** — during training the decoder always sees correct history; at inference it sees its own (imperfect) predictions. Small early errors compound. Scheduled sampling (gradually mixing teacher-forced and self-generated inputs over training) is a common mitigation.

### 5.3 Attention Mechanism (Bridge to Transformers)

Bahdanau et al. (2015) solved the bottleneck by giving the decoder a **soft attention** over all encoder hidden states at each decoding step:

```
At decoder step t:
  e_{t,s}  =  score(h_t^dec, h_s^enc)    for each encoder step s
  α_{t,s}  =  softmax(e_{t,s})            attention weights
  c_t      =  Σ_s  α_{t,s} · h_s^enc    context vector (dynamic, per step)
```

Instead of a single `c`, the decoder gets a fresh context vector `c_t` at each step, weighted by which input positions are most relevant. This allows the model to "look back" at the input directly — the forerunner of Transformer self-attention.

---

## 6. Applications of Sequence Models

### 6.1 Time Series Forecasting

**Problem:** Given observations `[x_1, x_2, ..., x_T]`, predict `x_{T+1}, ..., x_{T+H}` (horizon H).

**Architecture choices:**
- Many-to-one: predict `x_{T+1}` from a window of T steps
- Many-to-many: predict entire horizon in one pass (seq2seq)
- Multi-step iterative: predict one step, feed back, repeat

**Feature engineering for time series:**
- Lag features: `x_{t-1}, x_{t-7}, x_{t-365}` (yesterday, last week, last year)
- Rolling statistics: rolling mean, rolling std
- Calendar features: hour of day, day of week, month (encode cyclically with sin/cos)
- External covariates: weather, events, promotions

### 6.2 Text Generation

Character-level or token-level language modelling: at each step, predict the probability distribution over the vocabulary for the next token.

```python
# Training objective (cross-entropy):
loss = -Σ_t  log P(x_{t+1} | x_1, ..., x_t)

# Sampling strategies at inference:
# Greedy:      argmax P(next_token)  — deterministic, repetitive
# Temperature: sample from P^{1/T}   — T<1 sharpen, T>1 flatten
# Top-k:       sample from top k tokens only
# Nucleus:     sample from smallest set with cumulative prob >= p
```

### 6.3 Named Entity Recognition (NER)

**Task:** Label each token in a sentence with an entity type (PERSON, ORG, LOC, DATE, O).

**Architecture:** Bidirectional LSTM + CRF (Conditional Random Field) output layer.

```
Sentence:    "Apple  is  buying  Beats  for  $3B"
             ───────────────────────────────────
BiLSTM:      [→][←] [→][←] [→][←] [→][←] ...
             (forward and backward hidden states concatenated)
CRF:         enforces valid label transitions (e.g. I-ORG cannot follow B-PER)
Labels:       B-ORG  O    O      B-ORG  O    O
```

The CRF layer learns transition scores between label pairs, preventing invalid sequences like I-PER appearing without a preceding B-PER.

### 6.4 Sentiment Analysis

**Document-level:** Many-to-one — encode entire review, classify positive/negative.

**Aspect-level:** Many-to-many — "The battery [BAD] life is short but the screen [GOOD] is beautiful."

**Tricks that improve accuracy:**
- Pretrained word embeddings (GloVe, FastText) as input
- Attention over the sequence — weight emotionally salient words more
- Hierarchical architecture — sentence-level LSTM over word-level LSTM

---

## 7. RNN vs Transformer — Practical Decision Guide

Transformers (2017+) have largely replaced RNNs in NLP benchmarks. But RNNs are not obsolete — they remain the better choice in specific scenarios.

```
DECISION TREE:

Is your sequence longer than ~1000 tokens?
  YES ──► Consider Transformer (attention scales better for very long contexts)
  NO  ──► RNN may be fine

Do you need to process sequences in real-time / online learning?
  YES ──► RNN (processes one step at a time; Transformer needs full context)
  NO  ──► Either

Is your dataset small (< 100K samples)?
  YES ──► RNN (fewer parameters, less compute to overfit)
  NO  ──► Either; Transformer benefits more from scale

Do you have a GPU cluster / large budget?
  YES ──► Transformer (parallelises training across sequence positions)
  NO  ──► RNN (trains sequentially but on cheaper hardware)

Is interpretability / explainability required?
  EITHER ──► Both are difficult; attention weights ≠ explanation

Is your task strictly temporal / causal (each step depends only on past)?
  YES ──► RNN is naturally causal; Transformer needs causal masking
  NO  ──► Either
```

| Criterion | RNN / LSTM | Transformer |
|---|---|---|
| Training parallelism | Sequential (slow) | Parallel (fast) |
| Inference for generation | Fast (O(1) per step) | Slow (O(n²) with KV cache) |
| Online / streaming | Native | Requires windowing |
| Long-range dependency | Struggles (>500 steps) | Excellent |
| Parameter count | Smaller | Much larger |
| Memory scaling | O(1) in state | O(n²) attention |
| Positional encoding | Implicit (recurrence) | Explicit (sinusoidal / RoPE) |
| Best domain (2025) | Time series, IoT, edge | NLP, vision, multimodal |

**Bottom line:** For most new NLP tasks at scale, use a Transformer or pre-trained LLM. For time series, on-device inference, online learning, or small datasets, LSTM/GRU remains a pragmatic and well-understood choice.

---

## 8. Time Series Deep Dive

### 8.1 Windowing & Strides

Raw time series must be converted to supervised (input, target) pairs using a sliding window:

```
Original series:  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
Window size W=4, stride S=1, horizon H=1:

  Input window    → Target
  [1, 2, 3, 4]   → 5
  [2, 3, 4, 5]   → 6
  [3, 4, 5, 6]   → 7
  ...

Multi-step (H=3):
  [1, 2, 3, 4]   → [5, 6, 7]
  [2, 3, 4, 5]   → [6, 7, 8]
```

**Implementation:**

```python
import numpy as np

def create_sequences(data, window_size, horizon=1, stride=1):
    """
    data: 1D or 2D numpy array of shape (T,) or (T, features)
    returns X of shape (N, window_size, features), y of shape (N, horizon)
    """
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    T, F = data.shape
    X, y = [], []
    for start in range(0, T - window_size - horizon + 1, stride):
        end = start + window_size
        X.append(data[start:end])
        y.append(data[end:end + horizon, 0])  # predict first feature
    return np.array(X), np.array(y)
```

**Choosing window size:** Domain knowledge first — a 7-day window for daily retail sales captures a weekly seasonal cycle. Then tune empirically.

### 8.2 Stationarity

A stationary time series has **constant mean, variance, and autocorrelation over time**. Most ML models (including LSTMs) work better on stationary inputs.

**Tests for stationarity:**
- **ADF (Augmented Dickey-Fuller):** p < 0.05 → reject unit root → stationary
- **KPSS:** p > 0.05 → fail to reject stationarity → stationary
- Visual: plot rolling mean and std over a 30-day window

**Transformations to achieve stationarity:**

```
Non-stationary (trending):    x_t  →  Δx_t = x_t - x_{t-1}    (first differencing)
Non-stationary (exponential): x_t  →  log(x_t)
Seasonal:                     x_t  →  x_t - x_{t-s}            (seasonal differencing, s = period)
Heteroskedastic (varying var): x_t  →  log(x_t)  or  Box-Cox transform
```

**Important:** all transformations applied to training data must be **consistently applied to test data and inverted when reporting results**.

### 8.3 ARIMA vs LSTM Comparison

```
ARIMA(p, d, q):
  AR(p): y_t depends on p lagged values
  I(d):  d-th order differencing to achieve stationarity
  MA(q): y_t depends on q lagged error terms

Equation:
  Δ^d y_t  =  c  +  Σ_{i=1}^{p} φ_i Δ^d y_{t-i}  +  ε_t  +  Σ_{j=1}^{q} θ_j ε_{t-j}
```

| Dimension | ARIMA | LSTM |
|---|---|---|
| Model family | Statistical / linear | Deep learning / nonlinear |
| Stationarity required | Yes (differencing d) | No (can learn trend) |
| Multivariate | VARIMA (complex) | Native (just add features) |
| Exogenous variables | ARIMAX | Native |
| Interpretability | High (explicit AR/MA terms) | Low (black box) |
| Training data needed | Small (50–200 points) | Large (1000+ recommended) |
| Computational cost | Very low | Higher |
| Non-linear patterns | Cannot capture | Captures well |
| Hyperparameter tuning | ACF/PACF plots + AIC | Grid/random search |
| Forecast uncertainty | Analytical confidence intervals | Monte Carlo / quantile regression |

**When ARIMA wins:** Short univariate series with clear linear autocorrelation structure, limited data, interpretability required, baseline model.

**When LSTM wins:** Long multivariate series, nonlinear dynamics, exogenous features, need to share a model across many related series (global model), anomaly patterns.

**Hybrid approach:** Use ARIMA to remove linear trend/seasonality; train LSTM on residuals. Often outperforms either model alone.

---

## 9. Practical Considerations & Implementation Tips

### Architecture Design

```python
import torch
import torch.nn as nn

class LSTMForecaster(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, output_size, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,          # input shape: (batch, seq_len, features)
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False        # causal — only past is known
        )
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        # x: (batch, seq_len, input_size)
        out, (h_n, c_n) = self.lstm(x)
        # out: (batch, seq_len, hidden_size)
        # Use only the last time step for many-to-one
        return self.fc(out[:, -1, :])
```

### Training Checklist

1. **Normalise inputs** — StandardScaler or MinMaxScaler fit on training set only, applied to val/test.
2. **Gradient clipping** — `torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)` to prevent exploding gradients.
3. **Stateful vs stateless LSTM** — In stateless mode (default), hidden state resets between batches. In stateful mode, pass `h_n, c_n` between batches — useful for very long sequences processed in chunks.
4. **Early stopping** — Monitor validation loss; stop after N epochs without improvement. Restore best checkpoint.
5. **Learning rate scheduling** — ReduceLROnPlateau or cosine annealing.
6. **Dropout** — Applied between LSTM layers (not within a layer's recurrence). Variational dropout (same mask at every step) is more principled.
7. **Batch size** — Larger batches stabilise gradient estimates but reduce implicit regularisation. 32–128 typical for time series.
8. **Bidirectional LSTM** — Use only when the full sequence is available at inference time (e.g. NER, classification). Never for autoregressive forecasting.

### Debugging Sequence Models

| Symptom | Likely Cause | Fix |
|---|---|---|
| Loss not decreasing | Vanishing gradients | Gradient clipping, reduce sequence length, check LSTM layer count |
| Loss oscillates wildly | Exploding gradients | Gradient clipping, reduce learning rate |
| Overfitting (train << val loss) | Too large model | Dropout, reduce hidden size, more data, regularisation |
| Predictions always near mean | Model ignoring sequence | Check input normalisation, try longer window, add positional features |
| Very slow training | Too many layers / large hidden | Profile, try GRU, reduce model size |

---

## 10. Quiz — 10 Questions With Solutions

### Questions

**Q1.** What is the fundamental difference between a feedforward neural network and an RNN in terms of how they handle input data?

**Q2.** In the BPTT gradient formula, `∂h_t/∂h_k = Π_{j=k+1}^{t} diag(tanh'(a_j)) · W_hh`, explain why this product causes the vanishing gradient problem.

**Q3.** An LSTM cell at time step `t` receives a forget gate output `f_t = [0, 0, 0, 1, 1]` and the previous cell state `C_{t-1} = [3.2, -1.5, 0.7, 2.1, -0.9]`. What is `f_t ⊙ C_{t-1}`?

**Q4.** What is the role of the output gate `o_t` in an LSTM, and why is it needed if we already have the cell state?

**Q5.** Name one key architectural difference between a GRU and an LSTM, and explain one scenario where GRU would be preferred.

**Q6.** In a seq2seq model with teacher forcing, what is "exposure bias" and why does it matter?

**Q7.** You are building a time series forecaster for electricity demand (sampled every 15 minutes). You choose a window of 96 timesteps. What time period does this window cover, and what pattern can it capture?

**Q8.** A vanilla RNN is trained on sentences of average length 8. You then evaluate it on sentences of length 200. What problem do you expect, and what architecture would mitigate it?

**Q9.** What is the key mathematical reason why the cell state `C_t` in an LSTM allows gradients to flow over long time horizons with less attenuation than the hidden state in a vanilla RNN?

**Q10.** You have a univariate time series of 200 daily observations (no exogenous features) and need a quick interpretable forecast. Should you use ARIMA or LSTM? Justify your answer.

---

### Solutions

**A1.** A feedforward network processes each input independently, with no memory between inputs. An RNN maintains a **hidden state** `h_t` that is passed forward from one time step to the next, allowing the network to incorporate context from the entire preceding sequence into each prediction. Both share parameters across positions (temporal parameter sharing in RNN).

**A2.** The product contains `(t - k)` copies of `W_hh` multiplied with `diag(tanh'(a_j))`. The derivative of tanh is bounded by [0, 1] and is near 0 when inputs are large (saturation). If the spectral radius of `W_hh` is also < 1, each multiplication shrinks the magnitude of the product exponentially. After even 10–20 steps, the product approaches zero, so `∂L_t/∂h_k ≈ 0` for small k — the loss at time t carries no signal to update weights based on events far in the past.

**A3.** Element-wise multiply: `[0×3.2, 0×(-1.5), 0×0.7, 1×2.1, 1×(-0.9)] = [0, 0, 0, 2.1, -0.9]`. The first three dimensions of the cell state are erased (forgotten); the last two are retained unchanged.

**A4.** The cell state `C_t` is an internal memory register that accumulates information over time. It is not directly useful as an output because it can grow unbounded and is not normalised. The output gate `o_t` acts as a **filter**: it selects which dimensions of `tanh(C_t)` (normalised to [-1,1]) to expose to the downstream layers and to the next time step via `h_t`. This allows the LSTM to hold information in `C_t` without necessarily "announcing" it in `h_t` at every step.

**A5.** One key difference: the GRU has **no separate cell state** — it merges `C_t` and `h_t` into a single hidden state `h_t`. It also has only two gates (reset and update) vs LSTM's three. GRU is preferred when: the dataset is small (fewer parameters → less overfitting), training time is limited, or the sequences are moderate length (< ~100 steps) where the separate cell state of LSTM is not critical.

**A6.** Exposure bias is the mismatch between training and inference conditions in a seq2seq decoder. During training with teacher forcing, the decoder always receives the **true previous token**. At inference, it receives its **own previous prediction**, which may be wrong. Errors accumulate: a wrong token at step 3 causes a different hidden state at step 4, leading to a different (possibly wrong) prediction at step 4, and so on. Mitigation: scheduled sampling (gradually replacing teacher-forced tokens with model predictions as training progresses), or reinforcement learning fine-tuning (REINFORCE / SCST).

**A7.** 96 timesteps × 15 minutes = 1440 minutes = **24 hours** (one full day). The window captures the **daily cycle** of electricity demand — morning peak, midday trough, evening peak. To also capture weekly patterns (Mon–Sun), a window of 96 × 7 = 672 steps would be needed.

**A8.** The vanilla RNN will likely exhibit poor performance on length-200 sentences. Due to the vanishing gradient problem, the hidden state after 200 steps retains very little information from the beginning of the sentence. The network cannot model dependencies that span more than ~10–20 steps. Architecture mitigations: **LSTM** (cell state provides a gradient highway), **Transformer** (direct attention over all positions), or adding explicit skip connections / highway connections to the RNN.

**A9.** In a vanilla RNN, gradients of `h_t` w.r.t. `h_k` pass through `(t-k)` matrix multiplications `W_hh` and `(t-k)` tanh derivatives — both can shrink the gradient exponentially. In an LSTM, the gradient of `C_t` w.r.t. `C_{t-1}` is simply `f_t` (element-wise). If the forget gate learns to be near 1 for certain dimensions, those gradient components pass back with multiplication factor ≈ 1 — no exponential decay. The cell state path avoids repeated tanh and matrix multiplication on the gradient highway.

**A10.** **ARIMA** is the better choice here. Reasons: (1) Only 200 data points — insufficient for an LSTM to learn meaningful patterns (LSTMs typically need 1000+ samples); (2) Univariate with no exogenous features — ARIMA is well-suited; (3) Interpretability is easier with ARIMA (explicit AR/MA terms, explicit seasonality); (4) ARIMA can be fit in seconds vs LSTM hyperparameter tuning. Use `auto_arima` from `pmdarima` for automatic order selection. Only switch to LSTM if the series shows clear nonlinear dynamics that ARIMA residuals fail to capture.

---

## 11. Project: LSTM Time Series Forecasting

### Goal

Build an LSTM model to forecast daily maximum temperature using the **Jena Climate dataset** (publicly available from the TensorFlow datasets or Kaggle). The model will use a 30-day window to predict the next 7 days.

### Dataset

**Jena Climate Dataset** — 14 weather features (temperature, pressure, humidity, wind speed, etc.) sampled every 10 minutes from 2009–2016. We aggregate to daily means.

Download: `https://storage.googleapis.com/tensorflow/tf-keras-datasets/jena_climate_2009_2016.csv.zip`

### Project Structure

```
jena_lstm/
  ├── data/
  │   └── jena_climate_2009_2016.csv
  ├── 01_eda.ipynb
  ├── 02_preprocess.py
  ├── 03_train.py
  ├── 04_evaluate.py
  └── model.py
```

### Step 1 — Data Loading & Exploratory Analysis

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller

# Load raw data (10-min intervals)
df = pd.read_csv('data/jena_climate_2009_2016.csv')
df['Date Time'] = pd.to_datetime(df['Date Time'], format='%d.%m.%Y %H:%M:%S')
df = df.set_index('Date Time')

# Resample to daily means
daily = df.resample('D').mean()

# Focus on temperature (column 'T (degC)')
temp = daily[['T (degC)']].copy()
temp.columns = ['temperature']

print(f"Date range: {temp.index.min()} to {temp.index.max()}")
print(f"Total days: {len(temp)}")
print(temp.describe())

# Plot
plt.figure(figsize=(14, 4))
plt.plot(temp)
plt.title('Daily Max Temperature — Jena, Germany')
plt.ylabel('Temperature (°C)')
plt.tight_layout()
plt.savefig('temperature_series.png', dpi=150)

# Stationarity test
result = adfuller(temp['temperature'].dropna())
print(f"ADF statistic: {result[0]:.4f}, p-value: {result[1]:.4f}")
# Expect p << 0.05 after removing trend (temperature is stationary around annual cycle)
```

### Step 2 — Preprocessing

```python
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# Add calendar features (cyclical encoding)
temp['day_sin'] = np.sin(2 * np.pi * temp.index.dayofyear / 365.25)
temp['day_cos'] = np.cos(2 * np.pi * temp.index.dayofyear / 365.25)
temp['dow_sin'] = np.sin(2 * np.pi * temp.index.dayofweek / 7)
temp['dow_cos'] = np.cos(2 * np.pi * temp.index.dayofweek / 7)

# Split: 70% train, 15% val, 15% test — preserve temporal order
n = len(temp)
train_end = int(n * 0.70)
val_end   = int(n * 0.85)

train_df = temp.iloc[:train_end]
val_df   = temp.iloc[train_end:val_end]
test_df  = temp.iloc[val_end:]

# Scale (fit on train only)
scaler = StandardScaler()
train_scaled = scaler.fit_transform(train_df)
val_scaled   = scaler.transform(val_df)
test_scaled  = scaler.transform(test_df)

# Create sequences
WINDOW = 30    # look back 30 days
HORIZON = 7    # forecast 7 days ahead

def make_sequences(data, window, horizon):
    X, y = [], []
    for i in range(len(data) - window - horizon + 1):
        X.append(data[i:i+window])
        y.append(data[i+window:i+window+horizon, 0])  # temperature only
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

X_train, y_train = make_sequences(train_scaled, WINDOW, HORIZON)
X_val,   y_val   = make_sequences(val_scaled,   WINDOW, HORIZON)
X_test,  y_test  = make_sequences(test_scaled,  WINDOW, HORIZON)

print(f"X_train shape: {X_train.shape}")   # (N, 30, 5)
print(f"y_train shape: {y_train.shape}")   # (N, 7)
```

### Step 3 — Model Definition

```python
import torch
import torch.nn as nn

class LSTMForecaster(nn.Module):
    def __init__(self, input_size=5, hidden_size=128, num_layers=2,
                 output_size=7, dropout=0.3):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers  = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )
        self.norm = nn.LayerNorm(hidden_size)
        self.fc   = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, output_size)
        )

    def forward(self, x):
        # x: (batch, seq_len, input_size)
        out, _ = self.lstm(x)
        # Take the last hidden state
        last = self.norm(out[:, -1, :])
        return self.fc(last)  # (batch, output_size)
```

### Step 4 — Training Loop

```python
from torch.utils.data import TensorDataset, DataLoader
import torch.optim as optim

device = 'cuda' if torch.cuda.is_available() else 'cpu'

# DataLoaders
def make_loader(X, y, batch_size=64, shuffle=True):
    ds = TensorDataset(torch.from_numpy(X), torch.from_numpy(y))
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle)

train_loader = make_loader(X_train, y_train)
val_loader   = make_loader(X_val,   y_val,   shuffle=False)

# Model
model = LSTMForecaster().to(device)
criterion = nn.MSELoss()
optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

EPOCHS = 100
best_val_loss = float('inf')
patience_counter = 0
PATIENCE = 15

for epoch in range(1, EPOCHS + 1):
    # --- Train ---
    model.train()
    train_loss = 0
    for X_batch, y_batch in train_loader:
        X_batch, y_batch = X_batch.to(device), y_batch.to(device)
        optimizer.zero_grad()
        pred = model(X_batch)
        loss = criterion(pred, y_batch)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        train_loss += loss.item() * len(X_batch)
    train_loss /= len(X_train)

    # --- Validate ---
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for X_batch, y_batch in val_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            pred = model(X_batch)
            val_loss += criterion(pred, y_batch).item() * len(X_batch)
    val_loss /= len(X_val)

    scheduler.step(val_loss)

    if val_loss < best_val_loss:
        best_val_loss = val_loss
        torch.save(model.state_dict(), 'best_model.pt')
        patience_counter = 0
    else:
        patience_counter += 1

    if epoch % 10 == 0:
        print(f"Epoch {epoch:3d} | Train MSE: {train_loss:.4f} | Val MSE: {val_loss:.4f}")

    if patience_counter >= PATIENCE:
        print(f"Early stopping at epoch {epoch}")
        break
```

### Step 5 — Evaluation & Visualisation

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Load best model
model.load_state_dict(torch.load('best_model.pt', map_location=device))
model.eval()

# Generate test predictions
X_test_t = torch.from_numpy(X_test).to(device)
with torch.no_grad():
    preds_scaled = model(X_test_t).cpu().numpy()

# Inverse-transform temperature (column 0)
# We need to inverse-transform only the temperature column
def inverse_temp(scaled_vals, scaler, col_idx=0):
    """Inverse transform a single feature column."""
    dummy = np.zeros((scaled_vals.shape[0], scaler.n_features_in_))
    dummy[:, col_idx] = scaled_vals
    return scaler.inverse_transform(dummy)[:, col_idx]

# For each forecast horizon day separately
preds_actual = np.zeros_like(preds_scaled)
y_actual     = np.zeros_like(y_test)
for d in range(HORIZON):
    preds_actual[:, d] = inverse_temp(preds_scaled[:, d], scaler)
    y_actual[:, d]     = inverse_temp(y_test[:, d],       scaler)

# Metrics (averaged over all horizons)
mae  = mean_absolute_error(y_actual.flatten(), preds_actual.flatten())
rmse = mean_squared_error(y_actual.flatten(),  preds_actual.flatten(), squared=False)
print(f"Test MAE:  {mae:.2f} °C")
print(f"Test RMSE: {rmse:.2f} °C")

# Plot: first 90 test days, day-1 forecast
plt.figure(figsize=(14, 5))
plt.plot(y_actual[:90, 0],    label='Actual',   color='steelblue')
plt.plot(preds_actual[:90, 0],label='Forecast', color='tomato', linestyle='--')
plt.title('LSTM 1-Day Ahead Forecast vs Actual Temperature')
plt.ylabel('Temperature (°C)')
plt.xlabel('Test day')
plt.legend()
plt.tight_layout()
plt.savefig('forecast_vs_actual.png', dpi=150)
plt.show()
```

### Expected Results

With this setup (2-layer LSTM, hidden=128, window=30) on the Jena dataset you should expect approximately:

- **1-day ahead MAE:** 1.2–1.8 °C
- **7-day ahead MAE:** 2.5–3.5 °C

### Extensions

1. **Attention mechanism:** Add a learned attention layer over the 30 LSTM outputs before the final FC layer.
2. **Quantile regression:** Replace MSE loss with pinball loss at quantiles [0.1, 0.5, 0.9] for prediction intervals.
3. **Ensemble:** Train 5 models with different seeds; average predictions.
4. **Multivariate input:** Include pressure, humidity, and wind speed as additional features.
5. **Temporal Fusion Transformer (TFT):** State-of-the-art for tabular time series — compare against your LSTM baseline.

---

## 12. References & Further Reading

### Essential — Free Online

| Resource | URL | Why Read It |
|---|---|---|
| **Colah's Blog — Understanding LSTMs** | `https://colah.github.io/posts/2015-08-Understanding-LSTMs/` | The single clearest explanation of LSTM internals ever written. Read this first. |
| **CS231n Stanford — RNN Lecture Notes** | `https://cs231n.github.io/rnn/` | Rigorous treatment of vanilla RNN, LSTM, backprop through time |
| **fast.ai NLP Course** | `https://www.fast.ai/` | Practical LSTM, ULMFiT, modern NLP with code |
| **Andrej Karpathy — Unreasonable Effectiveness of RNNs** | `https://karpathy.github.io/2015/05/21/rnn-effectiveness/` | Intuition, demos, char-level language model from scratch |
| **distill.pub — Attention and Augmented RNNs** | `https://distill.pub/2016/augmented-rnns/` | Beautiful interactive visualisations |

### Seminal Papers

| Paper | Authors | Year | Significance |
|---|---|---|---|
| Long Short-Term Memory | Hochreiter & Schmidhuber | 1997 | Original LSTM paper |
| Learning Phrase Representations using RNN Encoder–Decoder | Cho et al. | 2014 | Introduced GRU and seq2seq framework |
| Sequence to Sequence Learning with Neural Networks | Sutskever et al. | 2014 | Encoder-decoder, reversal trick |
| Neural Machine Translation by Jointly Learning to Align and Translate | Bahdanau et al. | 2015 | Attention mechanism |
| Empirical Evaluation of Gated Recurrent Neural Networks | Chung et al. | 2014 | GRU vs LSTM empirical comparison |
| Attention Is All You Need | Vaswani et al. | 2017 | Transformer — replaced RNNs in NLP |

### Books

- **Deep Learning** — Goodfellow, Bengio, Courville (2016). Chapter 10: Sequence Modelling. Free: `https://www.deeplearningbook.org/`
- **Hands-On Machine Learning** — Aurélien Géron (3rd ed., 2022). Chapters 15–16: RNNs and Attention.
- **Time Series Forecasting with Python** — Marco Peixeiro (2022). Excellent ARIMA + LSTM coverage.

### Code Libraries

```python
# PyTorch — native LSTM/GRU
torch.nn.LSTM, torch.nn.GRU

# TensorFlow / Keras
tf.keras.layers.LSTM, tf.keras.layers.GRU, tf.keras.layers.Bidirectional

# High-level time series
# Darts:   pip install darts       — LSTM, TFT, ARIMA, ensembles
# NeuralForecast: pip install neuralforecast — LSTM, NHITS, Autoformer
# statsmodels: pip install statsmodels — ARIMA, SARIMA, ETS
# pmdarima:    pip install pmdarima  — auto_arima
```

---

*End of Chapter 08 — Recurrent Neural Networks, LSTMs & Sequence Models*

*Next chapter: Chapter 09 — Attention Mechanisms & Transformers*

---

> "The key insight of the LSTM is brutally simple: instead of letting every piece of information fight its way through a gauntlet of nonlinearities to reach the past, build a highway. Put a gate on the on-ramp, a gate on the off-ramp, and let the highway itself carry gradients — and information — with barely a whisper of attenuation."
