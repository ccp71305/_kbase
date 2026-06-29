# Chapter 6: Transformers, Attention & Large Language Models

> "Attention is all you need." — Vaswani et al., 2017

---

## Table of Contents

1. [The Sequence Problem](#1-the-sequence-problem)
2. [Why RNNs and LSTMs Fall Short](#2-why-rnns-and-lstms-fall-short)
3. [The Attention Mechanism from Scratch](#3-the-attention-mechanism-from-scratch)
4. [Self-Attention and Scaled Dot-Product Attention](#4-self-attention-and-scaled-dot-product-attention)
5. [Multi-Head Attention](#5-multi-head-attention)
6. [Positional Encoding](#6-positional-encoding)
7. [The Original Transformer Architecture (Vaswani 2017)](#7-the-original-transformer-architecture-vaswani-2017)
8. [BERT: Bidirectional Encoder Representations from Transformers](#8-bert-bidirectional-encoder-representations-from-transformers)
9. [GPT Family: Autoregressive Decoder-Only Models](#9-gpt-family-autoregressive-decoder-only-models)
10. [Modern LLM Innovations](#10-modern-llm-innovations)
11. [Fine-Tuning Strategies](#11-fine-tuning-strategies)
12. [Evaluation Metrics](#12-evaluation-metrics)
13. [Hallucination: Causes and Mitigations](#13-hallucination-causes-and-mitigations)
14. [Context Windows and Long-Context Models](#14-context-windows-and-long-context-models)
15. [Quiz (15 Questions with Solutions)](#15-quiz-15-questions-with-solutions)
16. [Exercise: Implement Scaled Dot-Product Attention in PyTorch](#16-exercise-implement-scaled-dot-product-attention-in-pytorch)
17. [References and Further Learning](#17-references-and-further-learning)

---

## 1. The Sequence Problem

Language is fundamentally sequential. A sentence like *"The bank by the river had steep banks"* requires understanding that the two uses of "bank" mean entirely different things, and that the second word is informed by the context of the entire preceding sequence. This is the **sequence modeling problem**: given a series of tokens (words, characters, subwords), predict or transform the sequence in a meaningful way.

### Core Tasks Requiring Sequence Understanding

| Task | Input | Output | Example |
|---|---|---|---|
| Machine Translation | Source sentence | Target sentence | EN → FR |
| Text Summarization | Long document | Short summary | Article → Headline |
| Question Answering | Question + context | Answer span | "Who wrote Hamlet?" |
| Sentiment Analysis | Review text | Sentiment label | "Great product!" → Positive |
| Text Generation | Prompt | Continuation | Story completion |
| Named Entity Recognition | Sentence | Entity labels per token | "Paris [LOC] is beautiful" |

### The Challenge: Long-Range Dependencies

Consider: *"The trophy did not fit in the suitcase because **it** was too big."*

What does "it" refer to — the trophy or the suitcase? Humans resolve this instantly, but a model must capture a dependency spanning multiple tokens. This is the **long-range dependency problem**, and it is the core challenge in sequence modeling.

---

## 2. Why RNNs and LSTMs Fall Short

Before Transformers, the dominant approach was **Recurrent Neural Networks (RNNs)** and their gated variants like **LSTMs** and **GRUs**.

### How RNNs Work

An RNN processes tokens one at a time, maintaining a **hidden state** `h_t` that acts as a "memory" of everything seen so far:

```
h_t = tanh(W_h * h_{t-1} + W_x * x_t + b)
```

```
       x_1    x_2    x_3    x_4
        |      |      |      |
       [RNN]->[RNN]->[RNN]->[RNN]
        |      |      |      |
       h_1    h_2    h_3    h_4
```

The problem: to get from `x_1` to `h_4`, information must pass through **every intermediate state**. Each step applies a weight matrix, and multiplying many values together either **explodes** or **vanishes**.

### Problem 1: Vanishing Gradients

During backpropagation through time (BPTT), gradients are multiplied by the weight matrix at every timestep. If the spectral norm of the weight matrix is < 1, gradients **shrink exponentially** toward the beginning of the sequence:

```
∂L/∂h_1 = (∂L/∂h_T) * ∏(t=1 to T) ∂h_t/∂h_{t-1}
         ≈ (∂L/∂h_T) * W^T    →    0 as T grows large
```

**Consequence:** The model forgets information from early in the sequence. For a 500-token document, the model essentially cannot learn from tokens seen more than ~50 tokens ago.

### Problem 2: LSTMs Help but Don't Solve It

LSTMs introduced **gates** (forget, input, output) and a **cell state** to allow gradients to flow more directly. This helped significantly, but:

- The gradient path from output to early inputs is still multiplicative and long.
- LSTMs require 4x the parameters of vanilla RNNs.
- They still struggle with very long sequences (>500 tokens).

### Problem 3: No Parallelization

The fundamental bottleneck of RNNs/LSTMs: **step t cannot begin until step t−1 is complete**. This is sequential by design. Training on modern GPUs/TPUs is essentially wasted — you cannot parallelize across the sequence dimension. A 1000-token sequence requires 1000 sequential matrix multiplications.

### Problem 4: Fixed-Size Bottleneck (Encoder-Decoder RNNs)

Early sequence-to-sequence models compressed the entire input into a **single fixed-size context vector** before decoding. This is an information bottleneck — a 500-word document cannot be faithfully represented as a single 512-dimensional vector.

```
"The cat sat on the mat"  →  [Encoder RNN]  →  [c]  →  [Decoder RNN]  →  "Le chat..."
                                                 ↑
                                          Information bottleneck!
                                     Everything must fit in this vector.
```

### Summary of RNN/LSTM Limitations

| Limitation | Impact |
|---|---|
| Vanishing gradients | Cannot learn long-range dependencies |
| Sequential computation | Cannot parallelize; slow training |
| Fixed context vector | Information bottleneck in seq2seq |
| Memory scales with T | Cannot attend to arbitrary past tokens |

The solution to all four problems: **Attention**.

---

## 3. The Attention Mechanism from Scratch

### The Core Intuition

Attention asks: *"When processing token i, which other tokens should I pay attention to, and how much?"*

Instead of compressing the entire sequence into a single vector, attention allows each output token to look directly at **every input token** and compute a weighted sum. The weights are learned dynamically based on the content.

### Query, Key, Value — The Database Analogy

The most powerful way to understand attention is through a **soft database lookup**:

- **Query (Q):** What am I looking for? (the current token's "question")
- **Key (K):** What do I have to offer? (each token's "label" or "index")
- **Value (V):** What is my actual content? (each token's "information")

In a hard database: if query exactly matches a key, return that key's value.
In **soft attention**: compute similarity between query and all keys, normalize to probabilities, and return a **weighted sum** of all values.

```
Query: "What animal is being described?"
Keys:  ["The", "fluffy", "cat", "sat", "down"]
       [0.05,   0.15,   0.70,  0.07,  0.03]   ← attention weights
Values: ["The", "fluffy", "cat", "sat", "down"]

Output = 0.05*V("The") + 0.15*V("fluffy") + 0.70*V("cat") + ...
       ≈ mostly the representation of "cat"
```

### Original Bahdanau Attention (2015)

Bahdanau et al. introduced the first attention mechanism for seq2seq translation. For each decoder step t:

1. Compute alignment score: `e_{t,i} = score(h_t, s_i)` where `s_i` is encoder hidden state for input token i
2. Normalize: `α_{t,i} = softmax(e_{t,i})`
3. Context vector: `c_t = Σ_i α_{t,i} * s_i`

The score function was a small MLP: `score(h, s) = v^T * tanh(W_h * h + W_s * s)`

This immediately improved translation quality for long sentences and gave birth to the modern attention era.

---

## 4. Self-Attention and Scaled Dot-Product Attention

### Self-Attention: Attending to Yourself

In the Transformer, the key innovation is **self-attention**: tokens in a sequence attend to **other tokens in the same sequence** (not a separate encoder). This allows every token to directly influence every other token in a single operation.

### Computing Q, K, V Projections

For an input sequence `X` of shape `[seq_len, d_model]`, we project into Q, K, V spaces using learned weight matrices:

```
Q = X * W_Q    # shape: [seq_len, d_k]
K = X * W_K    # shape: [seq_len, d_k]
V = X * W_V    # shape: [seq_len, d_v]
```

Where `W_Q, W_K ∈ ℝ^{d_model × d_k}` and `W_V ∈ ℝ^{d_model × d_v}`.

### Scaled Dot-Product Attention

The full formula:

```
Attention(Q, K, V) = softmax( Q * K^T / sqrt(d_k) ) * V
```

**Step by step:**

**Step 1: Compute raw attention scores**
```
scores = Q * K^T       # shape: [seq_len, seq_len]
```
Each `scores[i, j]` is the dot product between query i and key j — a measure of compatibility.

**Step 2: Scale by sqrt(d_k)**
```
scores = scores / sqrt(d_k)
```
Why? When `d_k` is large, dot products grow large in magnitude, pushing softmax into regions with extremely small gradients. Dividing by `sqrt(d_k)` keeps the variance of the scores at ~1, regardless of dimensionality.

**Step 3: Apply softmax**
```
weights = softmax(scores)    # shape: [seq_len, seq_len]
```
Each row sums to 1. `weights[i, j]` is "how much token i attends to token j".

**Step 4: Weighted sum of values**
```
output = weights * V         # shape: [seq_len, d_v]
```

### Attention Weights Visualization

For the sentence "The cat sat on the mat", the attention weight matrix might look like:

```
         The  cat  sat  on  the  mat
The    [ 0.4  0.1  0.1  0.1  0.1  0.1 ]
cat    [ 0.1  0.5  0.2  0.0  0.1  0.1 ]
sat    [ 0.0  0.3  0.3  0.1  0.1  0.2 ]
on     [ 0.1  0.0  0.3  0.4  0.1  0.1 ]
the    [ 0.3  0.1  0.1  0.1  0.3  0.1 ]   ← "the" attends to first "The" (coreference)
mat    [ 0.0  0.1  0.2  0.2  0.1  0.4 ]
```

Brighter cells = stronger attention. Notice:
- "cat" strongly attends to itself and "sat" (subject-verb agreement)
- "the" (second) attends to "The" (first) — detecting that they refer to the same context
- "mat" attends to itself and "sat" (verb-object relationship)

### Masking in the Decoder

In autoregressive generation, the decoder must not attend to future tokens (it would "cheat"). We apply a **causal mask** before softmax:

```
mask[i, j] = -inf  if j > i   (future tokens)
           = 0     otherwise

scores_masked = scores + mask
weights = softmax(scores_masked)   # future positions become 0 after softmax
```

---

## 5. Multi-Head Attention

### Why Multiple Heads?

A single attention head computes one alignment pattern. But language has multiple simultaneous relationships:
- Token i syntactically depends on token j
- Token i semantically relates to token k
- Token i co-references token l

**Multi-head attention** runs `h` attention heads in parallel, each in a lower-dimensional subspace. Each head can specialize in a different type of relationship.

### The Math

For `h` heads, each with dimension `d_k = d_model / h`:

```
head_i = Attention(Q * W_Q_i, K * W_K_i, V * W_V_i)

MultiHead(Q, K, V) = Concat(head_1, ..., head_h) * W_O
```

Where `W_Q_i, W_K_i ∈ ℝ^{d_model × d_k}`, `W_V_i ∈ ℝ^{d_model × d_v}`, and `W_O ∈ ℝ^{h*d_v × d_model}`.

### What Each Head Learns

Research has shown different heads in BERT/GPT specialize in:

| Head Type | What It Learns |
|---|---|
| Syntactic heads | Subject-verb dependencies, prepositional phrases |
| Positional heads | Attending to adjacent tokens (local context) |
| Coreference heads | Resolving "it", "they", "he" to their antecedents |
| Rare token heads | Attending to rare or important words |
| Delimiter heads | Attending to [SEP] or [CLS] tokens |

### Multi-Head Attention ASCII Diagram

```
        Input X
           |
    ┌──────┼──────┐
    |      |      |
   W_Q    W_K    W_V
    |      |      |
    Q      K      V
    |      |      |
    └──────┼──────┘
           |
  ┌────────┴────────┐
  │   Split into h  │
  │      heads      │
  └────────┬────────┘
           |
  ┌─────────────────────────────────┐
  | head_1   head_2  ...   head_h   |
  | Attn()   Attn()       Attn()   |
  └──────────────┬──────────────────┘
                 |
            Concatenate
                 |
               W_O
                 |
           Output (d_model)
```

### Computational Complexity

Self-attention is `O(n^2 * d)` where n is sequence length — quadratic in sequence length. This is the key bottleneck for long sequences and motivates later innovations like Flash Attention and sparse attention.

---

## 6. Positional Encoding

### Why Position Information Is Needed

Self-attention is **permutation invariant** — if you shuffle the tokens, the attention scores change but the mechanism itself has no built-in notion of order. The sentence "dog bites man" and "man bites dog" would produce the same set of attention values if positions are ignored.

We must inject position information explicitly.

### Sinusoidal Positional Encoding (Vaswani 2017)

The original Transformer adds a fixed, hand-crafted positional encoding to the token embeddings:

```
PE(pos, 2i)   = sin(pos / 10000^(2i / d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i / d_model))
```

Where:
- `pos` is the position in the sequence (0, 1, 2, ...)
- `i` is the dimension index (0 to d_model/2)
- Different frequencies encode different positional scales

```
Dimension:  0    1    2    3    4    5   ...
pos=0:    [ 0.0  1.0  0.0  1.0  0.0  1.0 ... ]
pos=1:    [ 0.84 0.54 0.48 0.88 0.10 1.0 ... ]
pos=2:    [ 0.91 -0.4 0.84 0.54 0.20 1.0 ... ]
```

**Properties:**
- Each position has a unique encoding
- Nearby positions have similar encodings
- The model can generalize to positions not seen during training
- `PE(pos + k)` can be expressed as a linear function of `PE(pos)`, allowing the model to learn relative positions

### Learned Positional Embeddings

Instead of hand-crafted sinusoids, most modern models (BERT, GPT-2+) use **learned position embeddings**: a simple lookup table `E_pos ∈ ℝ^{max_len × d_model}`, trained alongside the model. These often outperform sinusoidal encodings in practice but cannot generalize to sequences longer than `max_len`.

### Rotary Positional Embeddings (RoPE)

RoPE (Su et al., 2021), used in LLaMA, GPT-NeoX, and PaLM, encodes position by **rotating** the query and key vectors in 2D planes:

```
For each pair (q_{2i}, q_{2i+1}) at position m:
[q'_{2i}  ]   [cos(m*θ_i)  -sin(m*θ_i)] [q_{2i}  ]
[q'_{2i+1}] = [sin(m*θ_i)   cos(m*θ_i)] [q_{2i+1}]
```

Where `θ_i = 1 / 10000^(2i / d)`.

**Key property:** The dot product `<q_m, k_n>` depends only on `q`, `k`, and the **relative position** `m - n`. This gives the model a natural sensitivity to relative distances and generalizes better to longer sequences. RoPE is now the dominant positional encoding scheme.

### ALiBi (Attention with Linear Biases)

ALiBi (Press et al., 2022) adds a linear bias to attention scores based on distance:

```
score(i, j) = q_i * k_j^T - m * |i - j|
```

Where `m` is a per-head slope. This penalizes attending to distant tokens linearly, empirically showing very strong extrapolation beyond training length.

---

## 7. The Original Transformer Architecture (Vaswani 2017)

### Overview

The original Transformer ("Attention Is All You Need") is an **encoder-decoder** architecture designed for sequence-to-sequence tasks like machine translation. It completely replaces recurrence with self-attention.

### Full Architecture ASCII Diagram

```
         OUTPUT TOKENS (shifted right)
                    |
           [Output Embedding]
                    |
           [+ Positional Enc]
                    |
            ┌───────────────┐
            │   DECODER     │   × N layers
            │               │
            │  ┌─────────┐  │
            │  │ Masked  │  │   ← Causal self-attention
            │  │ Self-   │  │     (cannot see future)
            │  │ Attn    │  │
            │  └────┬────┘  │
            │       │       │
            │  ┌────┴────┐  │
            │  │Add&Norm │  │
            │  └────┬────┘  │
            │       │       │
            │  ┌────┴────┐  │   ← Cross-attention
            │  │Cross-   │  │     Q from decoder
            │  │Attn     │◄─┼─── K,V from encoder
            │  └────┬────┘  │
            │       │       │
            │  ┌────┴────┐  │
            │  │Add&Norm │  │
            │  └────┬────┘  │
            │       │       │
            │  ┌────┴────┐  │
            │  │  FFN    │  │   ← Position-wise FFN
            │  └────┬────┘  │     (2 linear layers + ReLU)
            │       │       │
            │  ┌────┴────┐  │
            │  │Add&Norm │  │
            │  └────────┘  │
            └───────────────┘
                    ↑
             Encoder output
                    |
            ┌───────────────┐
            │   ENCODER     │   × N layers
            │               │
            │  ┌─────────┐  │
            │  │  Self-  │  │   ← Bidirectional self-attention
            │  │  Attn   │  │     (sees all tokens)
            │  └────┬────┘  │
            │       │       │
            │  ┌────┴────┐  │
            │  │Add&Norm │  │
            │  └────┬────┘  │
            │       │       │
            │  ┌────┴────┐  │
            │  │  FFN    │  │
            │  └────┬────┘  │
            │       │       │
            │  ┌────┴────┐  │
            │  │Add&Norm │  │
            │  └────────┘  │
            └───────────────┘
                    ↑
           [Input Embedding]
                    |
           [+ Positional Enc]
                    |
          INPUT TOKENS (source)
```

### Layer-by-Layer Walkthrough

#### 1. Token Embedding + Positional Encoding

Input tokens are embedded as dense vectors `E ∈ ℝ^{d_model}` (d_model = 512 in the original). Positional encodings of the same dimension are added:

```
x_i = Embedding(token_i) + PositionalEncoding(i)
```

The Transformer paper scales embeddings by `sqrt(d_model)` to prevent positional encodings from dominating.

#### 2. Encoder: Multi-Head Self-Attention

Each encoder token attends to all other encoder tokens (bidirectional). The output of multi-head attention is:

```
MultiHead(X, X, X)   # Q = K = V = X  (self-attention)
```

#### 3. Add & LayerNorm (Residual Connection)

```
x = LayerNorm(x + SubLayer(x))
```

Residual connections allow gradients to flow directly to earlier layers, preventing vanishing gradients in deep networks. LayerNorm stabilizes training by normalizing activations within each layer.

#### 4. Position-wise Feed-Forward Network (FFN)

Applied independently to each position:

```
FFN(x) = max(0, x * W_1 + b_1) * W_2 + b_2
```

In the original paper: `d_model = 512`, inner dimension = 2048. This is where most of the model's "memory" lives — the FFN layers store factual knowledge.

#### 5. Decoder: Masked Self-Attention

The decoder's first sub-layer applies a causal mask so position i cannot attend to positions > i. This enforces autoregressive generation: each output token is conditioned only on previously generated tokens.

#### 6. Decoder: Cross-Attention (Encoder-Decoder Attention)

```
MultiHead(Q=decoder_states, K=encoder_output, V=encoder_output)
```

This is the bridge between encoder and decoder. The decoder "queries" the encoder output to retrieve relevant source information for each output token being generated.

#### 7. Final Linear + Softmax

The decoder output is projected to vocabulary size and normalized:

```
P(next_token) = softmax(decoder_output * W_vocab)
```

Training uses **cross-entropy loss** comparing the predicted distribution to the true next token.

### Key Hyperparameters (Original Paper)

| Hyperparameter | Base Model | Large Model |
|---|---|---|
| d_model | 512 | 1024 |
| N (layers) | 6 | 6 |
| h (heads) | 8 | 16 |
| d_ff (FFN inner) | 2048 | 4096 |
| Dropout | 0.1 | 0.3 |
| Parameters | ~65M | ~213M |

---

## 8. BERT: Bidirectional Encoder Representations from Transformers

### Architecture

BERT (Devlin et al., 2018) uses **only the encoder** stack from the Transformer. This makes it bidirectional — every token can attend to every other token in both directions.

```
[CLS] The cat sat on [MASK] [SEP]
  ↓    ↓   ↓   ↓   ↓    ↓    ↓
 [Transformer Encoder × 12 layers]
  ↓    ↓   ↓   ↓   ↓    ↓    ↓
[v_CLS] ...       [v_mat]    ...
   |                  |
Classification    Masked LM
  (fine-tune)      (pre-train)
```

### Pre-Training Objectives

BERT is pretrained on two tasks simultaneously:

#### Masked Language Modeling (MLM)

Randomly mask 15% of tokens. The model must predict the original token from context:

```
Input:  "The [MASK] sat on the [MASK]"
Target: "cat"                   "mat"
```

Of the 15% masked:
- 80% are replaced with `[MASK]`
- 10% are replaced with a random token
- 10% are left unchanged (to teach the model that any token could be a "correct" prediction)

This forces the model to build deep bidirectional representations.

#### Next Sentence Prediction (NSP)

Given two sentences A and B, predict whether B follows A in the original document:

```
Input: [CLS] Sentence A [SEP] Sentence B [SEP]
Label: IsNextSentence / NotNextSentence
```

Note: Later work (RoBERTa, 2019) showed NSP is actually harmful — removing it consistently improves performance.

### Special Tokens

| Token | Meaning | Use |
|---|---|---|
| `[CLS]` | Classification token | Its final embedding is used for classification tasks |
| `[SEP]` | Separator token | Marks sentence boundaries |
| `[MASK]` | Mask token | Replaces masked tokens during MLM pretraining |
| `[PAD]` | Padding token | Pads shorter sequences in a batch |
| `[UNK]` | Unknown token | Represents out-of-vocabulary tokens |

### The [CLS] Token

The `[CLS]` token is prepended to every input. Because it attends to all other tokens via self-attention and all other tokens attend to it, its final-layer representation aggregates information from the entire sequence. It is used as a **sentence-level embedding** for classification tasks.

### Fine-Tuning BERT

BERT's power comes from **transfer learning**: pretrain once on large unlabeled text, then fine-tune with a small task-specific head on labeled data:

```
Task: Sentiment Classification
Input: [CLS] "This movie was amazing" [SEP]
Model: BERT base → CLS embedding → Linear(768 → 2) → softmax
Training: Fine-tune all BERT weights + linear layer on labeled sentiment data
```

Fine-tuning typically uses:
- Learning rate: 2e-5 to 5e-5
- Epochs: 3-5
- Batch size: 16-32

### BERT Variants

| Model | Key Change | Improvement |
|---|---|---|
| RoBERTa | Remove NSP, train longer, larger batches | +2-3 GLUE points |
| DistilBERT | Knowledge distillation, 40% smaller | 97% performance, 60% faster |
| ALBERT | Parameter sharing across layers, factorized embeddings | Much smaller, competitive |
| DeBERTa | Disentangled attention (separate pos/content) | State-of-art GLUE 2020 |
| SciBERT | Pretrained on scientific papers | Better for scientific NLP |

---

## 9. GPT Family: Autoregressive Decoder-Only Models

### Architecture

GPT (Generative Pretrained Transformer) uses **only the decoder** stack, with causal (left-to-right) masking. There is no encoder and no cross-attention.

```
    Token_n (predicted)
         ↑
   [Linear + Softmax]
         ↑
   [Decoder Layer × N]    ← Masked self-attention only
         ↑
   Token_1, Token_2, ..., Token_{n-1}
```

### Pre-Training: Next Token Prediction

GPT is trained with a single, simple objective: predict the next token:

```
P(token_t | token_1, ..., token_{t-1})
Loss = -Σ log P(token_t | token_{1:t-1})
```

This is pure **language modeling**. The model learns grammar, facts, reasoning, and world knowledge purely from predicting next tokens across trillions of tokens.

### The GPT Progression

#### GPT-1 (2018) — Proof of Concept
- 117M parameters
- 12 transformer layers, d_model = 768
- Pretrained on BooksCorpus (800M words)
- Key insight: a single pretrained model can be fine-tuned for diverse NLP tasks
- Showed that decoder-only Transformers can do surprisingly well with just language modeling

#### GPT-2 (2019) — Scaling Surprises
- 1.5B parameters (largest version)
- 48 layers, d_model = 1600
- Pretrained on WebText (40GB of Reddit-curated web pages)
- **Zero-shot generalization**: GPT-2 could summarize, translate, and answer questions without any fine-tuning — just by prompting
- OpenAI initially withheld the full model citing "misuse concerns"

#### GPT-3 (2020) — Few-Shot Giant
- **175B parameters** — 100x larger than GPT-2
- 96 layers, d_model = 12288, 96 attention heads
- Trained on 300B tokens (Common Crawl, WebText, books, Wikipedia)
- **In-context learning**: provide a few examples in the prompt, model adapts without gradient updates
- Demonstrated emergent capabilities not seen at smaller scales

#### GPT-4 (2023) — Multimodal & RLHF
- Architecture undisclosed (estimated 1-8 trillion parameters in MoE configuration)
- Multimodal: accepts both text and images
- Heavily fine-tuned with RLHF
- Significant improvements in reasoning, coding, and instruction following
- Introduced concept of "system prompts" for behavior specification

### Scaling Laws (Kaplan et al., 2020)

A landmark paper from OpenAI showed that language model performance follows **smooth power laws** with compute, data, and model size:

```
Loss ∝ (1/N)^0.076    (model parameters N)
Loss ∝ (1/D)^0.095    (dataset tokens D)
Loss ∝ (1/C)^0.050    (compute FLOP C)
```

**Key finding:** Model size, dataset size, and compute must be **scaled together** for efficiency. The compute-optimal frontier (Chinchilla, 2022) showed that GPT-3 was significantly undertrained — you should train a smaller model on much more data.

**Chinchilla scaling law:** For a compute budget C, the optimal model has N = C^0.5 parameters trained on D = C^0.5 tokens. For 1 compute unit, split it 50/50 between model size and data.

### Emergent Capabilities

Large language models exhibit **emergent abilities** — capabilities that appear suddenly at scale and are absent in smaller models:

| Capability | Approximate Scale |
|---|---|
| Few-shot in-context learning | ~1B parameters |
| Chain-of-thought reasoning | ~100B parameters |
| Instruction following | After RLHF fine-tuning |
| Multi-step mathematical reasoning | ~100B+ parameters |
| Code generation (functional) | ~12B+ parameters |

---

## 10. Modern LLM Innovations

### Flash Attention

**Problem:** Standard attention requires materializing the full `[n × n]` attention matrix in GPU HBM (high-bandwidth memory). For n=4096, this is 4096² × 4 bytes = 64 MB per layer per batch element — memory bandwidth bound, not compute bound.

**Solution:** Flash Attention (Dao et al., 2022) computes attention in **tiles** that fit in SRAM (on-chip memory, much faster):

```
Standard:  Q, K, V → HBM → Compute scores → HBM → Softmax → HBM → Output
Flash:     Q, K, V → SRAM blocks → Compute+Softmax+Output in SRAM → write output to HBM
```

- **Memory**: O(n) instead of O(n²)
- **Speed**: 2-4x faster on A100 GPUs
- **Exact**: mathematically identical to standard attention (not approximate)
- Flash Attention 2 (2023): 2x further speedup through better parallelism

### KV Cache

**Problem:** In autoregressive generation, at each step we recompute K and V for all previous tokens — redundant work.

**Solution:** Cache K and V for all previously generated tokens:

```
Step 1: Generate token_1
  - Compute Q, K, V for [prompt]
  - Store K, V → KV cache
  - Produce output

Step 2: Generate token_2
  - Compute Q, K, V for [token_1]      ← only new token
  - Append K, V to KV cache
  - Attend over full KV cache (prompt + token_1)
  - Produce output

...
```

**ASCII: KV Cache Diagram**

```
Generation Step t:
                    New token
                        |
                       [Q]
                        |
                        ├── Attend to ──►  [K_1 | K_2 | ... | K_{t-1} | K_t]  (KV cache)
                        └──              [V_1 | V_2 | ... | V_{t-1} | V_t]
                                          ←─────── cached ──────────►  new
```

KV cache memory scales as `2 × n_layers × n_heads × d_head × seq_len` per batch element. For LLaMA-65B with 4096 context: ~16 GB just for cache. This motivates GQA.

### Grouped Query Attention (GQA)

**Problem:** Multi-head attention has `h` sets of Q, K, V heads — KV cache scales with h.

**Solution (GQA, Ainslie et al., 2023):** Group h query heads to share G key-value heads (G < h):

```
MHA (h=8):
Q: [h1  h2  h3  h4  h5  h6  h7  h8]
K: [k1  k2  k3  k4  k5  k6  k7  k8]
V: [v1  v2  v3  v4  v5  v6  v7  v8]

GQA (h=8, G=2):
Q: [h1  h2  h3  h4 | h5  h6  h7  h8]
K:     [k1         |     k2        ]     ← only 2 K heads
V:     [v1         |     v2        ]     ← only 2 V heads

MQA (G=1): all queries share a single K, V head
```

GQA achieves near-MHA quality with MQA-level memory efficiency. Used in LLaMA 2/3, Gemma, Mistral.

### Mixture of Experts (MoE)

**Problem:** Scaling a dense model requires all parameters for every token — computationally expensive.

**Solution:** Replace the FFN with a set of "expert" networks, and route each token to only a subset:

```
Standard FFN:
token → FFN → output

MoE FFN:
                  ┌→ Expert 1 ─┐
token → Router ──┼→ Expert 2 ─┼→ weighted sum → output
                  └→ Expert k ─┘
         (selects top-2 of N experts)
```

**Key metrics:**
- Total parameters: `N_experts × FFN_size` (large)
- Active parameters per token: `top_k × FFN_size` (small — e.g., 2 of 8 experts)

**Sparse MoE** (Shazeer et al., 2017, Fedus et al., 2022 "Switch Transformer") shows that a model with 10x more total parameters but the same active parameters per token dramatically improves quality with similar compute cost.

Used in: Mixtral (8x7B), GPT-4 (speculated), Gemini (speculated).

### Rotary Positional Embeddings (RoPE) — Revisited

As covered in Section 6, RoPE is now the dominant position encoding in modern LLMs. Its relative position sensitivity and generalization properties make it superior to learned absolute embeddings for models targeting long contexts.

### Grouped Layer Normalization and RMSNorm

Modern LLMs (LLaMA, Mistral) replace LayerNorm with **RMSNorm** (Root Mean Square Normalization):

```
LayerNorm: x̂_i = (x_i - μ) / (σ + ε) * γ + β    (mean and variance)
RMSNorm:   x̂_i = x_i / RMS(x) * γ                (RMS only, no mean subtraction)

RMS(x) = sqrt(1/n * Σ x_i²)
```

RMSNorm is ~10% faster, uses fewer parameters (no β), and empirically matches or exceeds LayerNorm quality. Most modern architectures use **pre-norm** (normalize before the sublayer) rather than **post-norm** (original Transformer) for training stability.

---

## 11. Fine-Tuning Strategies

### Full Fine-Tuning

Update **all model parameters** on a task-specific dataset:

```
Loss = CrossEntropy(model(input), labels)
Optimizer: AdamW
Update: ALL weights W
```

**Pros:** Best possible task performance, model fully adapts.
**Cons:** Requires storing a full model copy per task (175B × fp16 = 350 GB for GPT-3), catastrophic forgetting of other capabilities, very expensive.

### LoRA: Low-Rank Adaptation

**Key insight:** Weight updates during fine-tuning have low intrinsic rank. Instead of updating the full weight matrix `W ∈ ℝ^{d × k}`, decompose the update into two low-rank matrices:

```
W' = W + ΔW = W + A * B

Where:
A ∈ ℝ^{d × r}    (rank r << min(d, k))
B ∈ ℝ^{r × k}
ΔW ∈ ℝ^{d × k}   but has rank r

Trainable parameters: A, B   (r*(d+k) instead of d*k)
Typical r = 4, 8, 16, 64
```

**Example:** For GPT-3's attention matrices (d=12288, k=12288), r=8:
- Full: 12288 × 12288 = 150M params per matrix
- LoRA: 8 × (12288 + 12288) = 196K params — **750x fewer trainable params**

During inference, merge: `W_merged = W + A * B` — no additional latency.

**LoRA application points:** Typically applied to Q, K, V, and output projection matrices in each attention layer. Some implementations also apply to FFN layers.

### QLoRA: Quantized LoRA

**QLoRA (Dettmers et al., 2023)** enables fine-tuning of 65B models on a single 48GB GPU by combining:

1. **4-bit NormalFloat (NF4) quantization** of the frozen base model weights
2. **Double quantization** of the quantization constants (saves ~0.4 bits per parameter)
3. **Paged optimizers** (NVIDIA unified memory) to handle optimizer state memory spikes
4. **LoRA adapters** in fp16 on top of the quantized base

```
Model in 4-bit (frozen):     65B * 0.5 bytes = 32.5 GB
LoRA adapters (fp16):        ~500MB
Optimizer states (paged):    managed via paged memory
Total VRAM:                  ~48 GB (fits on single A6000!)
```

Quality is near-identical to full 16-bit fine-tuning despite the extreme compression.

### Prefix Tuning

Instead of modifying model weights, **prepend learnable "virtual tokens"** to the input:

```
Input: [P_1, P_2, ..., P_k, x_1, x_2, ..., x_n]
         ↑─── learned soft prompts ───↑   real tokens
```

The prefix tokens act as task-specific context. Only the prefix embeddings are trained; the model weights are frozen. Very parameter-efficient but generally underperforms LoRA.

### Prompt Tuning

A simpler variant of prefix tuning: learn a soft prompt added only at the input embedding layer (not at every layer). Works surprisingly well for large models (>10B parameters) but poorly for smaller ones.

### RLHF: Reinforcement Learning from Human Feedback

RLHF is the alignment technique behind ChatGPT, Claude, and Gemini. It consists of three stages:

```
Stage 1: Supervised Fine-Tuning (SFT)
  - Collect human-written demonstrations of desired behavior
  - Fine-tune the pretrained LLM on these demonstrations
  - Result: SFT model (follows instructions but not yet optimal)

Stage 2: Reward Model Training
  - Show humans pairs of model outputs, ask which is better
  - Train a "reward model" (separate LM + scalar head) to predict human preference scores
  - The RM learns what humans consider helpful, harmless, and honest

Stage 3: RL Fine-Tuning (PPO)
  - Use the RM as the reward signal
  - Fine-tune the SFT model with PPO to maximize expected reward
  - KL divergence penalty prevents the model from deviating too far from SFT model
    Loss = -E[R(response)] + β * KL(π_RL || π_SFT)
```

**Challenges with RLHF:**
- Reward hacking: model learns to exploit RM without actually being better
- Human label noise and inconsistency
- Expensive: requires thousands of human comparisons

**DPO (Direct Preference Optimization, 2023):** A simpler alternative that skips the RM entirely, directly optimizing the LLM to prefer good responses over bad ones using a closed-form solution derived from the RLHF objective.

---

## 12. Evaluation Metrics

### Perplexity

Perplexity measures how "surprised" a language model is by a test set. Lower is better.

```
Perplexity = exp(-1/N * Σ log P(token_i | context_i))
           = exp(average negative log-likelihood)
```

A perplexity of 10 means the model is as uncertain as choosing uniformly among 10 options.

**Limitation:** Perplexity is only comparable between models with the same tokenization and vocabulary.

### BLEU (Bilingual Evaluation Understudy)

BLEU measures n-gram overlap between generated and reference text. Used for machine translation.

```
BLEU = BP * exp(Σ_n w_n * log p_n)

Where:
p_n = precision of n-gram matches
BP  = brevity penalty (penalizes short outputs)
w_n = weight for each n-gram order (usually 0.25 each for 1-4)
```

**Limitations:** No semantic understanding, rewards repetition of common n-grams, correlates poorly with human judgment at sentence level.

### ROUGE (Recall-Oriented Understudy for Gisting Evaluation)

ROUGE measures recall of n-gram overlap. Used for summarization.

| Variant | Measures |
|---|---|
| ROUGE-1 | Unigram recall |
| ROUGE-2 | Bigram recall |
| ROUGE-L | Longest Common Subsequence |

### BERTScore

BERTScore (Zhang et al., 2019) uses contextual BERT embeddings to measure semantic similarity:

```
For each generated token g_i, find most similar reference token r_j:
  Precision = 1/|G| * Σ_i max_j cos(g_i, r_j)
  Recall    = 1/|R| * Σ_j max_i cos(r_j, g_i)
  F1        = 2 * P * R / (P + R)
```

BERTScore captures paraphrases and semantic similarity that n-gram metrics miss.

### LLM-as-Judge

Use a capable LLM (e.g., GPT-4) to evaluate the output of another LLM. The judge scores outputs on dimensions like helpfulness, accuracy, coherence, and harmlessness.

**Prompt format:**
```
[System: You are an impartial evaluator...]
[Human: Score this response on a 1-5 scale for accuracy:
Question: {question}
Response: {response}
Reference: {reference}]
```

**Advantages:** Captures nuanced quality, handles open-ended generation, scalable.
**Disadvantages:** Expensive, positional bias (favors first response), self-enhancement bias (GPT-4 favors GPT-4 style), can be manipulated.

### Benchmark Suites

| Benchmark | What It Tests |
|---|---|
| MMLU | Massive Multitask Language Understanding (57 subjects) |
| HellaSwag | Commonsense reasoning (sentence completion) |
| HumanEval | Python code generation (unit test pass rate) |
| GSM8K | Grade school math word problems |
| TruthfulQA | Truthfulness (resisting common misconceptions) |
| GLUE/SuperGLUE | Collection of NLU tasks |
| MT-Bench | Multi-turn instruction following |

---

## 13. Hallucination: Causes and Mitigation Strategies

### What Is Hallucination?

LLMs generate **fluent, confident-sounding text that is factually incorrect**. This is called hallucination.

Types:
- **Factual hallucination:** Incorrect facts ("The Eiffel Tower was built in 1923")
- **Faithfulness hallucination:** Summary contradicts the source document
- **Open-domain hallucination:** Invented citations, people, events, or statistics

### Root Causes

| Cause | Explanation |
|---|---|
| Training data noise | Models learn from web text containing errors, opinions, and misinformation |
| Exposure bias | Teacher-forcing during training differs from autoregressive inference |
| Overconfident generation | The model doesn't model uncertainty explicitly |
| Knowledge cutoff | Model has no information after training cutoff date |
| Rare entity problem | Low-frequency entities have sparse training signal |
| Decoding artifacts | Temperature and sampling methods can push toward fluency over accuracy |
| Conflicting training signals | RLHF may reward confident-sounding answers even when wrong |

### Mitigation Strategies

#### 1. Retrieval-Augmented Generation (RAG)

Ground responses in retrieved, up-to-date documents:

```
Query → Vector Search → Top-k Documents → LLM + Documents → Grounded Answer
```

The model is instructed to answer based only on the provided context, reducing invented facts.

#### 2. Chain-of-Thought (CoT) Prompting

Encourage the model to reason step-by-step before answering:

```
"Let's think step by step: 
1. The question asks about X.
2. From the context, I can see Y.
3. Therefore, the answer is Z."
```

CoT forces the model to externalize reasoning, catching errors before committing to an answer.

#### 3. Self-Consistency

Sample multiple independent reasoning chains (via temperature > 0), then take the majority vote:

```
5 independent CoT chains → 4 say "42", 1 says "41" → answer: "42"
```

#### 4. Constitutional AI and RLHF

Train the model to be truthful via human feedback that explicitly penalizes confident-but-wrong statements.

#### 5. Calibration and Uncertainty Quantification

Teach models to express uncertainty: "I'm not certain, but..." or "You should verify this." Some fine-tuning datasets explicitly include hedging language for uncertain facts.

#### 6. Factual Consistency Checking

Post-generation: use a separate model (NLI classifier or LLM) to check whether the generated text is entailed by the source documents.

---

## 14. Context Windows and Long-Context Models

### What Is a Context Window?

The **context window** is the maximum number of tokens a model can process in a single forward pass — the "working memory" of the model. Everything outside the context window is inaccessible.

| Model | Context Window |
|---|---|
| GPT-2 | 1,024 tokens |
| GPT-3 | 2,048 tokens |
| GPT-3.5 Turbo | 16,384 tokens |
| GPT-4 Turbo | 128,000 tokens |
| Claude 3.5 | 200,000 tokens |
| Gemini 1.5 Pro | 1,000,000 tokens |

### How Context Windows Work

At each generation step, the model attends to all tokens within the window:

```
[System Prompt | Conversation History | Latest Message | ←── model generates here]
└─────────────────── context window ─────────────────────┘
```

When the context is full, older tokens must be dropped (truncation) or a sliding window must be used.

**Memory scaling:** KV cache for all tokens in the window. For LLaMA-3 8B with 128K context: ~32 GB just for the KV cache.

### Challenges at Long Contexts

1. **Quadratic attention complexity:** O(n²) makes 1M-token context very expensive
2. **Lost in the middle:** Research (Liu et al., 2023) shows LLMs perform worse for information in the middle of long contexts vs. at the beginning/end
3. **KV cache memory:** See Section 10
4. **Position generalization:** Models trained on short contexts struggle with longer ones

### Solutions for Long Contexts

#### Sparse Attention

Only attend to a subset of tokens (local window + global tokens):
```
Longformer: sliding window + global tokens for [CLS]
BigBird: random + window + global
```

#### Position Interpolation and RoPE Extension

Extend RoPE to longer positions by interpolating frequencies. LLaMA 2 was extended from 4K to 32K context this way.

#### Sliding Window / Recurrent Approaches

Mamba (2023) and RWKV use selective state spaces or linear recurrence to achieve O(n) complexity while maintaining good long-context performance.

#### Memory-Augmented Approaches

External memory (like a database or vector store) allows effectively infinite context, but requires retrieval rather than direct attention.

---

## 15. Quiz (15 Questions with Solutions)

**Instructions:** Try each question before reading the solution.

---

**Q1.** Why does standard RNN training fail for very long sequences?

**Solution:** Vanishing gradients. During backpropagation through time, gradients are multiplied by the weight matrix at every timestep. If the spectral norm of the weight matrix is < 1, gradients shrink exponentially toward earlier timesteps, making it impossible to learn long-range dependencies.

---

**Q2.** In scaled dot-product attention, why do we divide by `sqrt(d_k)`?

**Solution:** When d_k is large, the dot products Q·K^T grow large in magnitude (variance grows linearly with d_k). This pushes softmax into regions where gradients are very small. Dividing by sqrt(d_k) normalizes the variance back to ~1, keeping gradients healthy.

---

**Q3.** What is the difference between Q, K, and V in attention?

**Solution:** Q (Query) represents what the current token is "looking for." K (Key) represents what each token has to "offer" as a label/index. V (Value) contains the actual content to be retrieved. Attention computes similarity between Q and all K's, normalizes to weights, then returns a weighted sum of V's.

---

**Q4.** If d_model = 512 and h = 8 attention heads, what is d_k (the dimension per head)?

**Solution:** d_k = d_model / h = 512 / 8 = **64**. Each head projects into a 64-dimensional subspace.

---

**Q5.** What is the computational complexity of self-attention with respect to sequence length n?

**Solution:** O(n² × d). The attention score matrix is n×n (quadratic), and each entry involves a d-dimensional dot product. This quadratic scaling with sequence length is the primary bottleneck for long-context models.

---

**Q6.** Why does the Transformer need positional encodings?

**Solution:** Self-attention is permutation invariant — shuffling input tokens produces the same attention values. Without positional information, the model cannot distinguish "dog bites man" from "man bites dog." Positional encodings inject explicit position information into the token representations.

---

**Q7.** What are the two pre-training objectives of BERT?

**Solution:** (1) **Masked Language Modeling (MLM):** 15% of tokens are masked; model predicts original tokens from context. (2) **Next Sentence Prediction (NSP):** Given two sentences, predict if B follows A. Note: NSP was later shown to be harmful and was removed in RoBERTa.

---

**Q8.** Why is BERT unsuitable for text generation?

**Solution:** BERT is a bidirectional encoder. It uses full self-attention (every token attends to all others). This means BERT cannot generate text autoregressively — to generate token t, you'd need all subsequent tokens, which you don't have. GPT's causal (left-to-right) masking makes it suitable for generation.

---

**Q9.** What is in-context learning, and which model demonstrated it?

**Solution:** In-context learning means providing a few input-output examples in the prompt itself (without any gradient updates), and the model generalizes to new examples. GPT-3 demonstrated this at scale — with 175B parameters, it could perform few-shot classification, translation, and reasoning purely from prompt examples.

---

**Q10.** What is the key difference between LoRA and full fine-tuning?

**Solution:** In full fine-tuning, ALL model parameters are updated. In LoRA, the base model is **frozen**; only two small low-rank matrices A and B are trained per weight matrix, with the update ΔW = A×B. This reduces trainable parameters by 100-1000x while achieving near-equivalent performance.

---

**Q11.** Describe the KV cache and why it speeds up autoregressive generation.

**Solution:** During generation, K and V for all previously generated tokens are cached. At each new step, only the new token's Q, K, V need to be computed; K and V are appended to the cache, and attention is computed over the full cache. This avoids recomputing K and V for all previous tokens at every step, turning O(n²) work per step into O(n) work.

---

**Q12.** What is the difference between MHA, GQA, and MQA?

**Solution:** In MHA (Multi-Head Attention), each head has its own Q, K, V. In MQA (Multi-Query Attention), all query heads share a single K and V. In GQA (Grouped Query Attention), query heads are grouped, and each group shares K, V heads (G groups with G < h). GQA reduces KV cache size while maintaining near-MHA quality.

---

**Q13.** What is hallucination in LLMs, and name two mitigation strategies.

**Solution:** Hallucination is when an LLM generates fluent but factually incorrect content (invented facts, citations, events). Mitigations include: (1) **RAG** — retrieve real documents and ground answers in them; (2) **Chain-of-Thought prompting** — forces the model to reason step-by-step, catching errors before answering; (3) **RLHF** — penalize confident but wrong answers via human feedback; (4) **Self-consistency** — majority vote over multiple sampled reasoning chains.

---

**Q14.** What problem does Flash Attention solve, and how?

**Solution:** Standard attention materializes the full n×n attention matrix in GPU HBM, which is memory-bandwidth bound. Flash Attention tiles the computation to fit in fast on-chip SRAM: it processes blocks of Q, K, V at a time, computes partial softmax/attention in SRAM, and writes only the final output to HBM. This reduces HBM accesses, achieving 2-4x speedup with O(n) memory instead of O(n²), while being mathematically exact.

---

**Q15.** Explain the three stages of RLHF.

**Solution:**
1. **Supervised Fine-Tuning (SFT):** Fine-tune the pretrained LLM on human-written demonstrations of desired behavior.
2. **Reward Model Training:** Collect human preference comparisons (A vs B), train a reward model to predict human preference scores.
3. **RL Fine-Tuning (PPO):** Use PPO to fine-tune the SFT model to maximize reward, with a KL divergence penalty to prevent the model from deviating too far from SFT behavior.

---

## 16. Exercise: Implement Scaled Dot-Product Attention in PyTorch

### Part 1: Basic Scaled Dot-Product Attention

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import math


def scaled_dot_product_attention(
    Q: torch.Tensor,
    K: torch.Tensor,
    V: torch.Tensor,
    mask: torch.Tensor = None,
    dropout_p: float = 0.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Scaled dot-product attention.

    Args:
        Q: Query tensor of shape (..., seq_len_q, d_k)
        K: Key tensor of shape (..., seq_len_k, d_k)
        V: Value tensor of shape (..., seq_len_k, d_v)
        mask: Optional mask tensor. -inf for positions to ignore.
        dropout_p: Dropout probability (applied to attention weights)

    Returns:
        output: Weighted sum of values, shape (..., seq_len_q, d_v)
        attn_weights: Attention weights, shape (..., seq_len_q, seq_len_k)
    """
    d_k = Q.size(-1)

    # Step 1: Compute raw attention scores
    # Q: (..., seq_q, d_k), K^T: (..., d_k, seq_k) -> scores: (..., seq_q, seq_k)
    scores = torch.matmul(Q, K.transpose(-2, -1))

    # Step 2: Scale by sqrt(d_k)
    scores = scores / math.sqrt(d_k)

    # Step 3: Apply mask (set masked positions to -inf so softmax gives ~0)
    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))

    # Step 4: Softmax over key dimension
    attn_weights = F.softmax(scores, dim=-1)

    # Replace NaNs from all-masked rows with 0
    attn_weights = torch.nan_to_num(attn_weights, nan=0.0)

    # Optional dropout on attention weights
    if dropout_p > 0.0:
        attn_weights = F.dropout(attn_weights, p=dropout_p)

    # Step 5: Weighted sum of values
    output = torch.matmul(attn_weights, V)

    return output, attn_weights
```

### Part 2: Multi-Head Attention Module

```python
class MultiHeadAttention(nn.Module):
    """
    Multi-Head Attention as described in "Attention Is All You Need".
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads  # dimension per head

        # Learned projection matrices for Q, K, V, and output
        self.W_Q = nn.Linear(d_model, d_model, bias=False)
        self.W_K = nn.Linear(d_model, d_model, bias=False)
        self.W_V = nn.Linear(d_model, d_model, bias=False)
        self.W_O = nn.Linear(d_model, d_model, bias=False)

        self.dropout = dropout
        self._init_weights()

    def _init_weights(self):
        # Xavier uniform initialization
        for module in [self.W_Q, self.W_K, self.W_V, self.W_O]:
            nn.init.xavier_uniform_(module.weight)

    def split_heads(self, x: torch.Tensor) -> torch.Tensor:
        """
        Split the last dimension into (num_heads, d_k).
        Then transpose to (batch, heads, seq_len, d_k).
        """
        batch_size, seq_len, d_model = x.size()
        x = x.view(batch_size, seq_len, self.num_heads, self.d_k)
        return x.transpose(1, 2)  # (batch, heads, seq_len, d_k)

    def combine_heads(self, x: torch.Tensor) -> torch.Tensor:
        """
        Inverse of split_heads.
        x: (batch, heads, seq_len, d_k) -> (batch, seq_len, d_model)
        """
        batch_size, num_heads, seq_len, d_k = x.size()
        x = x.transpose(1, 2).contiguous()  # (batch, seq_len, heads, d_k)
        return x.view(batch_size, seq_len, self.d_model)

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: torch.Tensor = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            query: (batch_size, seq_len_q, d_model)
            key:   (batch_size, seq_len_k, d_model)
            value: (batch_size, seq_len_k, d_model)
            mask:  (batch_size, 1, seq_len_q, seq_len_k) or broadcastable

        Returns:
            output:       (batch_size, seq_len_q, d_model)
            attn_weights: (batch_size, num_heads, seq_len_q, seq_len_k)
        """
        batch_size = query.size(0)

        # Project Q, K, V
        Q = self.W_Q(query)   # (batch, seq_q, d_model)
        K = self.W_K(key)     # (batch, seq_k, d_model)
        V = self.W_V(value)   # (batch, seq_k, d_model)

        # Split into heads: (batch, heads, seq, d_k)
        Q = self.split_heads(Q)
        K = self.split_heads(K)
        V = self.split_heads(V)

        # Scaled dot-product attention for all heads simultaneously
        dropout_p = self.dropout if self.training else 0.0
        attn_output, attn_weights = scaled_dot_product_attention(
            Q, K, V, mask=mask, dropout_p=dropout_p
        )
        # attn_output: (batch, heads, seq_q, d_k)
        # attn_weights: (batch, heads, seq_q, seq_k)

        # Combine heads and project to d_model
        output = self.combine_heads(attn_output)   # (batch, seq_q, d_model)
        output = self.W_O(output)                  # (batch, seq_q, d_model)

        return output, attn_weights
```

### Part 3: Causal Mask for Autoregressive Generation

```python
def make_causal_mask(seq_len: int, device: torch.device = None) -> torch.Tensor:
    """
    Create a causal (lower triangular) mask.
    mask[i, j] = 1 if j <= i (token i can attend to token j)
               = 0 if j >  i (token i cannot attend to future token j)

    Returns: (1, 1, seq_len, seq_len) for broadcasting over batch and heads
    """
    mask = torch.tril(torch.ones(seq_len, seq_len, device=device))
    return mask.unsqueeze(0).unsqueeze(0)  # (1, 1, seq_len, seq_len)


def make_padding_mask(lengths: torch.Tensor, max_len: int) -> torch.Tensor:
    """
    Create a padding mask from sequence lengths.

    Args:
        lengths: (batch_size,) tensor of actual sequence lengths
        max_len: maximum sequence length

    Returns: (batch_size, 1, 1, max_len) mask (1=attend, 0=ignore)
    """
    batch_size = lengths.size(0)
    mask = torch.arange(max_len, device=lengths.device).unsqueeze(0)  # (1, max_len)
    mask = (mask < lengths.unsqueeze(1)).float()                       # (batch, max_len)
    return mask.unsqueeze(1).unsqueeze(2)                              # (batch, 1, 1, max_len)
```

### Part 4: Verification and Visualization

```python
def test_attention():
    """Verify the implementation with known properties."""
    torch.manual_seed(42)

    batch_size, seq_len, d_model, num_heads = 2, 6, 64, 8

    # Create dummy input
    x = torch.randn(batch_size, seq_len, d_model)

    # Test 1: Self-attention (Q = K = V = x)
    mha = MultiHeadAttention(d_model=d_model, num_heads=num_heads, dropout=0.0)
    output, attn_weights = mha(x, x, x)

    assert output.shape == (batch_size, seq_len, d_model), f"Output shape mismatch: {output.shape}"
    assert attn_weights.shape == (batch_size, num_heads, seq_len, seq_len), \
        f"Attention weight shape mismatch: {attn_weights.shape}"

    # Test 2: Attention weights sum to 1 along key dimension
    weight_sum = attn_weights.sum(dim=-1)
    assert torch.allclose(weight_sum, torch.ones_like(weight_sum), atol=1e-5), \
        "Attention weights don't sum to 1!"

    # Test 3: Causal mask — future positions should have weight ~0
    causal_mask = make_causal_mask(seq_len)
    output_causal, attn_causal = mha(x, x, x, mask=causal_mask)

    # Check upper triangle of attention weights is ~0
    upper_triangle = attn_causal[:, :, :, :].triu(diagonal=1)
    assert upper_triangle.abs().max() < 1e-5, \
        "Causal mask not working — future tokens have nonzero attention!"

    print("All tests passed!")
    print(f"Output shape: {output.shape}")
    print(f"Attention weights shape: {attn_weights.shape}")
    print(f"Average attention weight: {attn_weights.mean().item():.4f} (expected ~{1/seq_len:.4f})")

    # Visualize attention weights for first head, first batch element
    import matplotlib.pyplot as plt
    import matplotlib

    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    tokens = [f"t{i}" for i in range(seq_len)]

    for head_idx, ax in enumerate(axes.flat):
        weights = attn_weights[0, head_idx].detach().numpy()  # (seq_len, seq_len)
        im = ax.imshow(weights, cmap='Blues', vmin=0, vmax=weights.max())
        ax.set_title(f'Head {head_idx + 1}')
        ax.set_xticks(range(seq_len))
        ax.set_yticks(range(seq_len))
        ax.set_xticklabels(tokens, fontsize=8)
        ax.set_yticklabels(tokens, fontsize=8)
        ax.set_xlabel('Keys (attended to)')
        ax.set_ylabel('Queries (attending)')

    plt.suptitle('Multi-Head Self-Attention Weights', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('attention_weights.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("Attention visualization saved to attention_weights.png")


if __name__ == "__main__":
    test_attention()
```

### Part 5: Parameter Count Analysis

```python
def count_parameters(model: nn.Module) -> dict:
    """Count parameters in the model."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {
        'total': total,
        'trainable': trainable,
        'non_trainable': total - trainable,
    }


# Analysis: How do parameter counts scale with model size?
print("=== Parameter Count Analysis ===")
configs = [
    ("BERT-small",  256, 4),
    ("BERT-base",   768, 12),
    ("BERT-large",  1024, 16),
    ("GPT-3-scale", 12288, 96),
]

for name, d_model, num_heads in configs:
    mha = MultiHeadAttention(d_model=d_model, num_heads=num_heads)
    params = count_parameters(mha)
    print(f"{name:20s} (d={d_model:5d}, h={num_heads:3d}): "
          f"{params['total']:>12,} params in MHA layer")
```

### Expected Output

```
All tests passed!
Output shape: torch.Size([2, 6, 64])
Attention weights shape: torch.Size([2, 8, 6, 6])
Average attention weight: 0.1667 (expected ~0.1667)

=== Parameter Count Analysis ===
BERT-small           (d=  256, h=  4):       262,144 params in MHA layer
BERT-base            (d=  768, h= 12):     2,359,296 params in MHA layer
BERT-large           (d= 1024, h= 16):     4,194,304 params in MHA layer
GPT-3-scale          (d=12288, h= 96):   603,979,776 params in MHA layer
```

---

## 17. References and Further Learning

### Free Resources (Highly Recommended)

#### Papers (Free on arXiv)

| Paper | Authors | Year | Link |
|---|---|---|---|
| Attention Is All You Need | Vaswani et al. | 2017 | arxiv.org/abs/1706.03762 |
| BERT: Pre-training of Deep Bidirectional Transformers | Devlin et al. | 2018 | arxiv.org/abs/1810.04805 |
| Language Models are Few-Shot Learners (GPT-3) | Brown et al. | 2020 | arxiv.org/abs/2005.14165 |
| Scaling Laws for Neural Language Models | Kaplan et al. | 2020 | arxiv.org/abs/2001.08361 |
| LoRA: Low-Rank Adaptation of Large Language Models | Hu et al. | 2021 | arxiv.org/abs/2106.09685 |
| FlashAttention | Dao et al. | 2022 | arxiv.org/abs/2205.14135 |
| QLoRA: Efficient Finetuning of Quantized LLMs | Dettmers et al. | 2023 | arxiv.org/abs/2305.14314 |
| RoFormer: Enhanced Transformer with Rotary Position Embedding | Su et al. | 2021 | arxiv.org/abs/2104.09864 |
| Mixtral of Experts | Mistral AI | 2024 | arxiv.org/abs/2401.04088 |

#### Free Courses and Videos

| Resource | Format | URL |
|---|---|---|
| **Andrej Karpathy: "Let's build GPT from scratch"** | YouTube (2h) | youtube.com — search "Karpathy Let's build GPT" |
| **Hugging Face NLP Course** | Interactive web course | huggingface.co/learn/nlp-course |
| **Jay Alammar's blog** | Visual blog posts (ESSENTIAL) | jalammar.github.io |
| Stanford CS224N: NLP with Deep Learning | Lecture videos | web.stanford.edu/class/cs224n |
| MIT 6.S191: Introduction to Deep Learning | Lecture videos | introtodeeplearning.com |

#### Jay Alammar's Essential Posts (jalammar.github.io)

- "The Illustrated Transformer" — the single best visual explanation of the Transformer
- "The Illustrated BERT, ELMo, and co." — how BERT works with beautiful diagrams
- "The Illustrated GPT-2" — autoregressive generation visualized
- "Visualizing A Neural Machine Translation Model" — attention visualized for translation
- "How GPT3 Works" — in-context learning explained visually

### Paid Resources (High Quality)

| Resource | Platform | Notes |
|---|---|---|
| **deeplearning.ai NLP Specialization** | Coursera | 4-course series: attention, transformers, BERT, GPT in depth |
| **fast.ai Part 2: Deep Learning from the Foundations** | fast.ai | Implementation-first, builds transformers from scratch |
| **Hugging Face Pro** | huggingface.co | Access to more model compute and fine-tuning |

### Key GitHub Repositories

| Repo | What It Contains |
|---|---|
| huggingface/transformers | Production implementations of 200+ models |
| karpathy/nanoGPT | Minimal, readable GPT implementation (224 lines) |
| karpathy/minGPT | Educational GPT implementation with clean code |
| facebookresearch/llama | LLaMA 2/3 reference implementation |
| microsoft/LoRA | Original LoRA implementation |
| Dao-AILab/flash-attention | Flash Attention official implementation |

### Recommended Reading Path

```
Week 1: Foundations
  → Jay Alammar: "The Illustrated Transformer"
  → Karpathy: "Let's build GPT" (watch fully, code along)
  → Read "Attention Is All You Need" abstract + Sections 3-4

Week 2: BERT & Pre-training
  → Jay Alammar: "The Illustrated BERT"
  → HuggingFace NLP Course Chapters 1-3
  → Fine-tune BERT on a sentiment dataset (IMDB or SST-2)

Week 3: GPT & Scaling
  → Jay Alammar: "The Illustrated GPT-2"
  → Read GPT-3 paper (skim, focus on few-shot results)
  → karpathy/nanoGPT: read and run the code

Week 4: Modern LLMs
  → Flash Attention paper (Section 1-3)
  → LoRA paper
  → QLoRA paper
  → Fine-tune LLaMA 2 with QLoRA on a custom dataset

Ongoing:
  → Follow: Andrej Karpathy, Yann LeCun, Lilian Weng (lilianweng.github.io) on Twitter/X
  → Read: Lilian Weng's blog posts on attention and LLMs (lilianweng.github.io)
  → Papers: Subscribe to Hugging Face daily paper digest
```

---

## Summary

This chapter covered the complete evolution from sequence modeling challenges to modern large language models:

```
Sequential bottleneck              →  Attention mechanism
(RNN/LSTM vanishing gradients)        (direct token-to-token connections)

Single attention pattern           →  Multi-head attention
(one relationship type)               (multiple relationship types in parallel)

No positional awareness            →  Positional encoding
(permutation invariant attention)     (sinusoidal, learned, RoPE, ALiBi)

Full encoder-decoder              →  Encoder-only (BERT) / Decoder-only (GPT)
(translation-focused)                 (understanding / generation)

Supervised learning only          →  Pretraining + fine-tuning
(task-specific from scratch)          (transfer learning)

Full fine-tuning                  →  LoRA, QLoRA, RLHF
(expensive, one model per task)       (efficient, aligned)

Quadratic attention               →  Flash Attention, GQA, MoE
(memory/compute bottleneck)           (engineering innovations for scale)
```

The field is moving rapidly. The architectural innovations covered here — attention, residual connections, layer normalization, positional encoding, and the encoder/decoder split — remain the foundation of every state-of-the-art model in 2024. The engineering innovations (Flash Attention, GQA, KV caching, MoE) are what make 70-billion-parameter models run on a single GPU. And the alignment techniques (RLHF, DPO) are what make these models useful and safe.

Master these foundations, and you will be equipped to read, implement, and extend any modern language model.

---

*Last updated: June 2026 | Chapter 6 of the AI/ML Deep Learning Knowledge Base*
