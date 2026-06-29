# Python Foundations for AI Engineering

> **Level:** Intermediate to Advanced | **Prerequisites:** Basic Python syntax, functions, loops
> **Goal:** Master the Python patterns, idioms, and tools that appear constantly in production AI/ML codebases

---

## Table of Contents

1. [Advanced Python Patterns](#1-advanced-python-patterns)
2. [Functional Programming in Python](#2-functional-programming-in-python)
3. [OOP for Machine Learning](#3-oop-for-machine-learning)
4. [Async / Await for LLM API Calls](#4-async--await-for-llm-api-calls)
5. [Memory Management for Large Datasets](#5-memory-management-for-large-datasets)
6. [Python Performance Tips](#6-python-performance-tips)
7. [Environment Management](#7-environment-management)
8. [Jupyter Notebook Best Practices](#8-jupyter-notebook-best-practices)
9. [Python Anti-patterns in AI Code](#9-python-anti-patterns-in-ai-code)
10. [Quiz — 10 Questions with Solutions](#10-quiz--10-questions-with-solutions)
11. [Exercises — 5 Practical Problems](#11-exercises--5-practical-problems)
12. [References and Resources](#12-references-and-resources)

---

## 1. Advanced Python Patterns

### 1.1 List and Dict Comprehensions

Comprehensions are the idiomatic Python replacement for `for`-loop accumulation. In AI code they appear everywhere: building feature vectors, filtering samples, normalizing batches.

```python
# ---- List comprehension ----
# Normalize pixel values from [0,255] to [0,1]
pixels = [23, 128, 255, 0, 64]
normalized = [p / 255.0 for p in pixels]

# With condition — keep only confident predictions
predictions = [("cat", 0.92), ("dog", 0.43), ("bird", 0.81)]
confident = [label for label, score in predictions if score >= 0.80]
# ['cat', 'bird']

# ---- Dict comprehension ----
# Map class index to class name
class_names = ["cat", "dog", "bird"]
idx_to_class = {i: name for i, name in enumerate(class_names)}
# {0: 'cat', 1: 'dog', 2: 'bird'}

# ---- Set comprehension ----
# Unique tokens in a corpus
corpus = ["the cat sat", "the dog ran", "a cat ran"]
unique_tokens = {token for sentence in corpus for token in sentence.split()}

# ---- Nested comprehension — flatten a batch of token lists ----
batches = [["hello", "world"], ["foo", "bar"], ["baz"]]
flat = [token for batch in batches for token in batch]
```

> **Rule of thumb:** If the comprehension spans more than two lines, a regular `for` loop is clearer. Readability beats cleverness.

### 1.2 Generators and Lazy Evaluation

A generator produces values on demand instead of materializing the entire sequence in memory. This is critical when training data does not fit in RAM.

```python
from pathlib import Path
import json

# Generator that streams JSONL training data line by line
def stream_jsonl(filepath: str):
    """Yield one dict per line from a JSONL file without loading it all."""
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

# Consumer — iterate without ever holding the full dataset
for record in stream_jsonl("train.jsonl"):
    process(record)  # only one dict in memory at a time


# Generator expression (like a list comp but lazy)
embeddings_path = Path("embeddings/")
file_sizes = (p.stat().st_size for p in embeddings_path.glob("*.npy"))
total_bytes = sum(file_sizes)  # evaluated lazily


# send() and two-way generators (advanced — useful for coroutines)
def running_average():
    total, count = 0.0, 0
    while True:
        value = yield total / count if count else 0.0
        total += value
        count += 1

avg = running_average()
next(avg)          # prime the generator
avg.send(10.0)     # 10.0
avg.send(20.0)     # 15.0
avg.send(30.0)     # 20.0
```

### 1.3 Decorators

Decorators wrap functions to add cross-cutting behaviour — timing, caching, retry logic, and input validation all appear in ML pipelines.

```python
import time
import functools
from typing import Callable, TypeVar, Any

F = TypeVar("F", bound=Callable[..., Any])

# ----- Timer decorator -----
def timeit(func: F) -> F:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper  # type: ignore[return-value]

@timeit
def embed_batch(texts: list[str]) -> list[list[float]]:
    ...  # call embedding API


# ----- Retry decorator (useful for flaky LLM API calls) -----
def retry(max_attempts: int = 3, delay: float = 1.0, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    print(f"Attempt {attempt} failed: {exc}. Retrying in {delay}s…")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry(max_attempts=5, delay=2.0, exceptions=(ConnectionError, TimeoutError))
def call_llm_api(prompt: str) -> str:
    ...


# ----- Class-based decorator for stateful logic -----
class RateLimiter:
    """Allows at most `calls` invocations per `period` seconds."""
    def __init__(self, calls: int, period: float):
        self.calls = calls
        self.period = period
        self._timestamps: list[float] = []

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < self.period]
            if len(self._timestamps) >= self.calls:
                sleep_time = self.period - (now - self._timestamps[0])
                time.sleep(max(sleep_time, 0))
            self._timestamps.append(time.monotonic())
            return func(*args, **kwargs)
        return wrapper

@RateLimiter(calls=10, period=60.0)
def fetch_completion(prompt: str) -> str:
    ...
```

### 1.4 Context Managers

Context managers guarantee resource cleanup regardless of exceptions. In AI work they manage GPU memory, database connections, temporary model weights, and timing scopes.

```python
from contextlib import contextmanager, suppress
import tempfile, os

# ----- Simple context manager via decorator -----
@contextmanager
def temporary_seed(seed: int):
    """Temporarily set random seeds, restore originals on exit."""
    import random, numpy as np
    old_py = random.getstate()
    old_np = np.random.get_state()
    try:
        random.seed(seed)
        np.random.seed(seed)
        yield
    finally:
        random.setstate(old_py)
        np.random.set_state(old_np)

with temporary_seed(42):
    sample = np.random.choice(dataset, size=1000)  # reproducible


# ----- Class-based context manager -----
class ModelCheckpoint:
    """Save model state on entry, restore on exception."""
    def __init__(self, model):
        self.model = model
        self._state = None

    def __enter__(self):
        import copy
        self._state = copy.deepcopy(self.model.state_dict())
        return self.model

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            print("Exception caught — rolling back model weights.")
            self.model.load_state_dict(self._state)
        return False  # do not suppress the exception

with ModelCheckpoint(my_model) as model:
    train_one_epoch(model, data_loader)   # if this raises, weights revert


# ----- suppress() for expected errors -----
with suppress(FileNotFoundError):
    os.remove("stale_cache.pkl")
```

### 1.5 Dataclasses and Type Hints

Dataclasses replace verbose `__init__` boilerplate. Combined with type hints they form the backbone of clean, IDE-friendly ML configuration objects.

```python
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal

@dataclass
class TrainingConfig:
    model_name: str
    learning_rate: float = 3e-4
    batch_size: int = 32
    max_epochs: int = 10
    device: Literal["cpu", "cuda", "mps"] = "cuda"
    optimizer: str = "adamw"
    warmup_steps: int = 500
    grad_clip: float = 1.0
    mixed_precision: bool = True
    output_dir: str = "checkpoints/"
    tags: list[str] = field(default_factory=list)   # mutable default MUST use field()
    extra: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")

cfg = TrainingConfig(model_name="bert-base-uncased", batch_size=64)
print(asdict(cfg))   # convert to plain dict for logging / serialization


# ----- Frozen dataclass (immutable config snapshot) -----
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelCard:
    model_id: str
    version: str
    created_at: str
    license: str

card = ModelCard("my-org/gpt2-finetuned", "1.0.0", "2025-06-29", "MIT")
# card.version = "2.0"  <- TypeError: frozen instance


# ----- Type hints worth knowing in AI code -----
from typing import Union, Sequence, Mapping, Iterator, Generator
import numpy as np

Tensor = np.ndarray   # common alias pattern

def batch_texts(
    texts: Sequence[str],
    batch_size: int = 32,
) -> Generator[list[str], None, None]:
    for i in range(0, len(texts), batch_size):
        yield list(texts[i : i + batch_size])
```

---

## 2. Functional Programming in Python

### 2.1 map, filter, reduce

```python
from functools import reduce

texts = ["  Hello World  ", "  foo bar  ", "  PYTHON  "]

# map — apply a function to every element
cleaned = list(map(str.strip, texts))
lowered  = list(map(str.lower, cleaned))

# filter — keep elements matching a predicate
long_texts = list(filter(lambda t: len(t) > 5, lowered))

# reduce — fold a sequence into a single value
from operator import add
total_chars = reduce(add, map(len, long_texts), 0)


# ----- Prefer comprehensions for simple cases -----
# map + filter equivalent — more readable
result = [t.strip().lower() for t in texts if len(t.strip()) > 5]
```

### 2.2 functools — partial, lru_cache, cached_property

```python
from functools import partial, lru_cache
from functools import cached_property

# partial — freeze some arguments
def call_api(prompt: str, model: str, temperature: float) -> str:
    ...

gpt4_caller = partial(call_api, model="gpt-4o", temperature=0.0)
# gpt4_caller("Summarize this text")


# lru_cache — memoize expensive pure functions
@lru_cache(maxsize=4096)
def encode_text(text: str, model_name: str) -> tuple[float, ...]:
    """Cache embeddings to avoid redundant API calls."""
    embedding = embedding_model.encode(text)
    return tuple(embedding)   # must be hashable for the cache


# cached_property — compute once, reuse on the same instance
class DocumentStore:
    def __init__(self, path: str):
        self.path = path

    @cached_property
    def vocab(self) -> set[str]:
        """Built once from disk on first access."""
        with open(self.path) as f:
            return {w for line in f for w in line.split()}
```

### 2.3 itertools — the toolkit for lazy iteration

```python
import itertools

# chain — flatten an iterable of iterables
from itertools import chain
all_tokens = list(chain.from_iterable(tokenized_sentences))

# islice — take first N items from a generator without exhausting it
from itertools import islice
first_100 = list(islice(stream_jsonl("huge_file.jsonl"), 100))

# batched (Python 3.12+) / manual batch with islice
def batched(iterable, n):
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk

# product — grid search over hyperparameters
from itertools import product
lr_values = [1e-3, 1e-4, 3e-5]
batch_sizes = [16, 32, 64]
for lr, bs in product(lr_values, batch_sizes):
    run_experiment(lr=lr, batch_size=bs)

# accumulate — running statistics
from itertools import accumulate
import operator
losses = [0.8, 0.65, 0.52, 0.48, 0.40]
cumulative_min = list(accumulate(losses, min))  # track best loss seen so far
```

---

## 3. OOP for Machine Learning

### 3.1 Class Hierarchies for Models

Well-designed OOP hierarchies make swapping components trivial — the key principle in PyTorch, scikit-learn, and most ML frameworks.

```python
from abc import ABC, abstractmethod
from typing import Any
import numpy as np

# ----- Abstract base class — contract every model must fulfill -----
class BaseModel(ABC):
    """Abstract interface for all classifiers in this project."""

    def __init__(self, name: str):
        self.name = name
        self._is_fitted = False

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseModel":
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """Default accuracy metric — override for regression."""
        predictions = self.predict(X)
        return float(np.mean(predictions == y))

    def __repr__(self) -> str:
        status = "fitted" if self._is_fitted else "unfitted"
        return f"{self.__class__.__name__}(name={self.name!r}, status={status})"


# ----- Concrete implementation -----
class LogisticClassifier(BaseModel):
    def __init__(self, learning_rate: float = 0.01, max_iter: int = 1000):
        super().__init__(name="logistic-regression")
        self.lr = learning_rate
        self.max_iter = max_iter
        self.weights: np.ndarray | None = None
        self.bias: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogisticClassifier":
        n_samples, n_features = X.shape
        self.weights = np.zeros(n_features)
        for _ in range(self.max_iter):
            logits = X @ self.weights + self.bias
            preds = 1 / (1 + np.exp(-logits))
            error = preds - y
            self.weights -= self.lr * (X.T @ error) / n_samples
            self.bias   -= self.lr * error.mean()
        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Call fit() before predict().")
        logits = X @ self.weights + self.bias
        return (1 / (1 + np.exp(-logits)) >= 0.5).astype(int)


# ----- Mixin for serialization -----
import pickle, pathlib

class SerializableMixin:
    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str) -> "SerializableMixin":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        if not isinstance(obj, cls):
            raise TypeError(f"Loaded object is {type(obj)}, expected {cls}")
        return obj


class ProductionLogisticClassifier(SerializableMixin, LogisticClassifier):
    """Production-ready classifier with save/load."""
    pass

model = ProductionLogisticClassifier()
model.fit(X_train, y_train)
model.save("models/logreg_v1.pkl")
```

### 3.2 Protocols — Structural Subtyping

Use `Protocol` when you want duck-typing without inheritance:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Tokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...
    def decode(self, ids: list[int]) -> str: ...

def tokenize_corpus(texts: list[str], tokenizer: Tokenizer) -> list[list[int]]:
    return [tokenizer.encode(t) for t in texts]
# Works with ANY object that has encode/decode — no inheritance required.
```

---

## 4. Async / Await for LLM API Calls

Synchronous LLM API calls block the event loop during network I/O. `asyncio` lets you saturate your rate limits with concurrent requests.

```python
import asyncio
import httpx
from dataclasses import dataclass

@dataclass
class CompletionRequest:
    id: str
    prompt: str

@dataclass
class CompletionResult:
    id: str
    text: str
    error: str | None = None


# ----- Single async call -----
async def fetch_completion(
    client: httpx.AsyncClient,
    request: CompletionRequest,
    semaphore: asyncio.Semaphore,
) -> CompletionResult:
    async with semaphore:   # limit concurrency to avoid 429s
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": request.prompt}],
                    "max_tokens": 256,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return CompletionResult(
                id=request.id,
                text=data["choices"][0]["message"]["content"],
            )
        except Exception as exc:
            return CompletionResult(id=request.id, text="", error=str(exc))


# ----- Fan-out across many prompts -----
async def batch_completions(
    requests: list[CompletionRequest],
    api_key: str,
    max_concurrency: int = 10,
) -> list[CompletionResult]:
    semaphore = asyncio.Semaphore(max_concurrency)
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [fetch_completion(client, req, semaphore) for req in requests]
        return await asyncio.gather(*tasks)


# ----- Entry point -----
import os

requests = [
    CompletionRequest(id=str(i), prompt=f"Summarize: {text}")
    for i, text in enumerate(corpus)
]

results = asyncio.run(
    batch_completions(requests, api_key=os.environ["OPENAI_API_KEY"])
)


# ----- Async generators for streaming responses -----
async def stream_completion(client: httpx.AsyncClient, prompt: str):
    async with client.stream(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}], "stream": True},
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                import json
                chunk = json.loads(line[6:])
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta   # caller can print tokens as they arrive
```

> **Key rules:**
> - Use `asyncio.gather` for independent concurrent calls.
> - Use `asyncio.Semaphore` to cap concurrency and stay inside rate limits.
> - Prefer `httpx.AsyncClient` over `aiohttp` for modern codebases; it has a synchronous fallback with the same API.
> - `asyncio.run()` is the correct entry point from synchronous code (not `loop.run_until_complete`).

---

## 5. Memory Management for Large Datasets

### 5.1 Why Memory Matters

| Approach | 1 M rows, 100 float32 cols | Notes |
|---|---|---|
| `pandas` DataFrame | ~400 MB | Loaded entirely into RAM |
| `numpy` memmap | ~400 MB on disk, <1 MB in RAM | Paged on access |
| Generator / chunked | Near zero per chunk | Sequential access only |
| `pyarrow` / `parquet` | ~100 MB (compressed) | Column-oriented, lazy reads |

### 5.2 Chunked Processing with Pandas

```python
import pandas as pd

CHUNK = 50_000

def process_large_csv(path: str) -> pd.DataFrame:
    results = []
    for chunk in pd.read_csv(path, chunksize=CHUNK):
        # feature engineering on one chunk at a time
        chunk["text_len"] = chunk["text"].str.len()
        chunk = chunk[chunk["text_len"] > 20]
        results.append(chunk[["id", "text_len", "label"]])
    return pd.concat(results, ignore_index=True)
```

### 5.3 numpy Memory Maps

```python
import numpy as np

# Write a large array to disk
embeddings = np.random.rand(1_000_000, 768).astype(np.float32)
np.save("embeddings.npy", embeddings)
del embeddings   # free RAM

# Read back with a memory map — only loads pages that are accessed
mmap = np.load("embeddings.npy", mmap_mode="r")
subset = mmap[0:1000]   # only these 1000 rows are paged into RAM
```

### 5.4 Python Memory Profiling

```python
# Install: pip install memory-profiler
from memory_profiler import profile

@profile
def build_vocab(texts: list[str]) -> dict[str, int]:
    vocab: dict[str, int] = {}
    for text in texts:
        for token in text.split():
            vocab[token] = vocab.get(token, 0) + 1
    return vocab

# Run: python -m memory_profiler script.py
# Each line annotated with mem usage increment


# ----- tracemalloc for production diagnostics -----
import tracemalloc

tracemalloc.start()
result = expensive_function()
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")
for stat in top_stats[:5]:
    print(stat)
```

### 5.5 Slots for Memory-Efficient Objects

```python
class TokenizerOutput:
    """Without __slots__: each instance has a __dict__ (~232 bytes overhead)."""
    __slots__ = ("input_ids", "attention_mask", "token_type_ids")

    def __init__(self, input_ids, attention_mask, token_type_ids):
        self.input_ids = input_ids
        self.attention_mask = attention_mask
        self.token_type_ids = token_type_ids
# With __slots__, 3–5x lower per-instance RAM usage at scale.
```

---

## 6. Python Performance Tips

### 6.1 Profiling First — Never Guess

```bash
# cProfile — deterministic profiler
python -m cProfile -s cumulative my_training_script.py | head -30

# line_profiler — line-by-line
pip install line_profiler
# Decorate the function with @profile, then:
kernprof -l -v my_script.py

# py-spy — sampling profiler, zero overhead, attach to running process
pip install py-spy
py-spy top --pid <PID>
```

### 6.2 Vectorization Mindset

The cardinal rule: **avoid Python loops over large arrays; push operations into NumPy/pandas/PyTorch kernels**.

```python
import numpy as np

# SLOW — Python loop over array
def cosine_similarity_slow(a: np.ndarray, b: np.ndarray) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(y ** 2 for y in b) ** 0.5
    return dot / (norm_a * norm_b)

# FAST — vectorized (100-1000x faster on large arrays)
def cosine_similarity_fast(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# FASTEST for many pairs — batched matrix multiply
def pairwise_cosine(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """A: (m, d), B: (n, d) -> (m, n) similarity matrix."""
    A_norm = A / np.linalg.norm(A, axis=1, keepdims=True)
    B_norm = B / np.linalg.norm(B, axis=1, keepdims=True)
    return A_norm @ B_norm.T
```

### 6.3 Built-in Tricks

```python
# join is faster than repeated string concatenation
tokens = ["the", "cat", "sat"]
sentence_fast = " ".join(tokens)      # O(n)
# sentence_slow = ""                  # O(n^2) due to string immutability
# for t in tokens: sentence_slow += t + " "

# collections.Counter vs manual dict
from collections import Counter
word_freq = Counter(corpus_tokens)   # 3x faster than defaultdict(int)

# deque for O(1) pops from both ends (queue/sliding window)
from collections import deque
window = deque(maxlen=512)   # automatically discards oldest element

# bisect for sorted insertion / binary search
import bisect
sorted_scores = []
bisect.insort(sorted_scores, new_score)   # O(log n) insert
```

### 6.4 Numba JIT for Numerical Loops

```python
from numba import njit
import numpy as np

@njit(cache=True)
def edit_distance(s1: str, s2: str) -> int:
    """Levenshtein distance — compiled to native code on first call."""
    m, n = len(s1), len(s2)
    dp = np.zeros((m + 1, n + 1), dtype=np.int32)
    for i in range(m + 1):
        dp[i, 0] = i
    for j in range(n + 1):
        dp[0, j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i, j] = min(dp[i-1,j]+1, dp[i,j-1]+1, dp[i-1,j-1]+cost)
    return int(dp[m, n])
```

---

## 7. Environment Management

### 7.1 venv (Standard Library)

```bash
# Create
python -m venv .venv

# Activate
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Freeze current state
pip freeze > requirements.txt

# Deactivate
deactivate
```

### 7.2 conda

```bash
# Create with specific Python version
conda create -n ml-project python=3.11

# Activate
conda activate ml-project

# Install packages (prefer conda for numerical libs)
conda install numpy pandas scikit-learn pytorch -c pytorch

# Install pip packages inside conda env
pip install transformers

# Export environment
conda env export > environment.yml

# Recreate on another machine
conda env create -f environment.yml
```

### 7.3 Poetry (Recommended for Production Projects)

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# New project
poetry new my-ai-project
cd my-ai-project

# Add dependencies
poetry add torch transformers
poetry add --group dev pytest black mypy

# Lock and install
poetry install

# Run inside the managed env
poetry run python train.py

# Export for Docker / CI
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

### 7.4 Choosing the Right Tool

| Tool | Best for | Lockfile | Virtualenv | Build/Publish |
|------|----------|----------|------------|---------------|
| `venv` + `pip` | Simple scripts, quick prototypes | `requirements.txt` (manual) | Yes | No |
| `conda` | Scientific computing, GPU drivers, C extensions | `environment.yml` | Yes | No |
| `poetry` | Production packages, libraries, reproducible builds | `poetry.lock` (automatic) | Yes | Yes |
| `uv` | Fastest installs (Rust-based, drop-in pip replacement) | `uv.lock` | Yes | Partial |

---

## 8. Jupyter Notebook Best Practices

### 8.1 Structure Your Notebooks

```
notebook.ipynb
├── ## 0. Setup & Imports       <- all imports at top, one cell
├── ## 1. Data Loading           <- load, do not transform
├── ## 2. EDA                    <- explore, visualize
├── ## 3. Preprocessing          <- clean, feature engineering
├── ## 4. Modeling               <- train / fine-tune
├── ## 5. Evaluation             <- metrics, confusion matrix
└── ## 6. Export / Save          <- write artifacts to disk
```

### 8.2 Magic Commands Worth Knowing

```python
%timeit np.dot(a, b)            # micro-benchmark a line
%%timeit                        # benchmark an entire cell

%load_ext autoreload
%autoreload 2                   # auto-reload imported modules on change

%matplotlib inline              # render matplotlib in cell output
%matplotlib widget              # interactive plots

%env TOKENIZERS_PARALLELISM=false   # set env var

!pip install tqdm               # run shell command
!git log --oneline -5

%debug                          # drop into pdb on last exception
```

### 8.3 Reproducibility

```python
# First cell of every notebook
import random, os
import numpy as np

SEED = 42

def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
    except ImportError:
        pass

set_seed()
```

### 8.4 nbstripout — Keep Notebooks Clean in Git

```bash
pip install nbstripout
nbstripout --install            # strips outputs before every git commit
```

### 8.5 Convert Notebooks to Scripts

```bash
# Export for production
jupyter nbconvert --to script my_notebook.ipynb

# Or use nbmake to run notebooks in CI
pip install nbmake
pytest --nbmake notebooks/
```

---

## 9. Python Anti-patterns in AI Code

### Anti-pattern 1: Accumulating in a Loop

```python
# BAD — O(n^2) due to repeated list copying
embeddings = []
for text in texts:
    embeddings = embeddings + [model.encode(text)]  # creates a new list each time

# GOOD — O(n)
embeddings = [model.encode(text) for text in texts]
# or
embeddings = []
for text in texts:
    embeddings.append(model.encode(text))   # in-place, amortised O(1)
```

### Anti-pattern 2: Loading the Entire Dataset into RAM

```python
# BAD — loads 50 GB into memory
with open("huge_corpus.txt") as f:
    lines = f.readlines()
for line in lines:
    process(line)

# GOOD — iterate lazily
with open("huge_corpus.txt") as f:
    for line in f:
        process(line)
```

### Anti-pattern 3: Mutable Default Arguments

```python
# BAD — the list is shared across ALL calls
def add_token(token: str, history: list = []) -> list:
    history.append(token)
    return history

add_token("hello")   # ['hello']
add_token("world")   # ['hello', 'world']  <- BUG: history persists!

# GOOD
def add_token(token: str, history: list | None = None) -> list:
    if history is None:
        history = []
    history.append(token)
    return history
```

### Anti-pattern 4: Using Bare Except

```python
# BAD — silently swallows all errors including KeyboardInterrupt
try:
    response = call_llm_api(prompt)
except:
    response = ""

# GOOD — catch only what you expect
try:
    response = call_llm_api(prompt)
except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
    logger.warning("API call failed: %s", exc)
    response = ""
```

### Anti-pattern 5: Recreating the Model Inside a Loop

```python
# BAD — loads model weights from disk on every iteration
for text in texts:
    model = SentenceTransformer("all-MiniLM-L6-v2")  # expensive!
    embedding = model.encode(text)

# GOOD — load once, reuse
model = SentenceTransformer("all-MiniLM-L6-v2")
for text in texts:
    embedding = model.encode(text)

# BEST — batch encode
embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)
```

### Anti-pattern 6: Not Using numpy Vectorization

```python
# BAD — Python loop over numpy array
def relu_slow(x: np.ndarray) -> np.ndarray:
    return np.array([max(0.0, v) for v in x])   # exits numpy, uses Python interpreter

# GOOD — stays in numpy
def relu_fast(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)   # ~100x faster on large arrays
```

### Anti-pattern 7: Storing Large Tensors in a Python List

```python
# BAD — Python list of small tensors, no batch parallelism
all_embeddings = []
for text in texts:
    emb = model.encode(text)          # shape (768,)
    all_embeddings.append(emb)        # list of numpy arrays
matrix = np.array(all_embeddings)     # copy into a new array at the end

# GOOD — pre-allocate
matrix = np.empty((len(texts), 768), dtype=np.float32)
for i, text in enumerate(texts):
    matrix[i] = model.encode(text)
```

---

## 10. Quiz — 10 Questions with Solutions

<details>
<summary><strong>Question 1</strong> — What is the output of <code>list(map(lambda x: x**2, filter(lambda x: x % 2 == 0, range(10))))</code>?</summary>

**Answer:** `[0, 4, 16, 36, 64]`

`filter` keeps even numbers `{0,2,4,6,8}`, then `map` squares each: `{0,4,16,36,64}`.

</details>

<details>
<summary><strong>Question 2</strong> — Why must mutable defaults in dataclasses use <code>field(default_factory=list)</code> instead of <code>= []</code>?</summary>

**Answer:** Python evaluates default argument values once at class definition time, not per-instance. Without `field(default_factory=list)`, all instances would share the same list object, and mutations on one instance would affect all others. `field(default_factory=list)` tells the dataclass machinery to call `list()` fresh for each new instance.

</details>

<details>
<summary><strong>Question 3</strong> — What is the difference between <code>@staticmethod</code> and <code>@classmethod</code>?</summary>

**Answer:** `@staticmethod` receives no implicit first argument — it is a regular function namespaced inside the class. `@classmethod` receives `cls` (the class itself) as its first argument, enabling it to create instances or access class-level state. In ML code `@classmethod` is common for factory methods like `Model.from_pretrained(path)`.

</details>

<details>
<summary><strong>Question 4</strong> — A generator function uses <code>yield</code>. What does calling it return before any iteration occurs?</summary>

**Answer:** Calling a generator function returns a **generator object** (a lazy iterator). None of the function body executes until the first call to `next()` or iteration begins. This is what makes generators memory-efficient — the values are produced on demand.

</details>

<details>
<summary><strong>Question 5</strong> — What does <code>functools.lru_cache</code> require of its arguments?</summary>

**Answer:** All arguments must be **hashable** because the cache uses them as dictionary keys. Lists, dicts, and numpy arrays are not hashable. A common workaround is to convert them to tuples before passing.

</details>

<details>
<summary><strong>Question 6</strong> — What is the purpose of <code>asyncio.Semaphore</code> in an LLM batch-calling pattern?</summary>

**Answer:** A `Semaphore(n)` limits the number of coroutines that can hold the semaphore simultaneously to `n`. In LLM API calling this enforces a concurrency cap so you don't exceed rate limits (requests-per-minute / tokens-per-minute) even when launching hundreds of coroutines with `asyncio.gather`.

</details>

<details>
<summary><strong>Question 7</strong> — What is a <code>Protocol</code> and how does it differ from an ABC?</summary>

**Answer:** A `Protocol` defines a structural interface — any class that has the required methods/attributes satisfies it, regardless of inheritance. An `ABC` requires explicit `class Foo(MyABC)` inheritance. Protocols enable duck-typing while retaining static type-checking. They are preferred when you want to accept third-party classes (e.g., HuggingFace tokenizers) without forcing them to subclass your ABC.

</details>

<details>
<summary><strong>Question 8</strong> — Name two ways to reduce per-instance memory usage when you have millions of Python objects.</summary>

**Answer:**
1. `__slots__` — eliminates the per-instance `__dict__`, reducing overhead by 3–5x.
2. Use `numpy` structured arrays or `pandas` DataFrames to store homogeneous data in contiguous C arrays instead of Python objects.

</details>

<details>
<summary><strong>Question 9</strong> — What does <code>poetry lock</code> produce and why is it important for reproducibility?</summary>

**Answer:** `poetry lock` resolves the full dependency graph (including transitive dependencies) and writes the exact versions and hashes of every package into `poetry.lock`. Committing this file ensures that `poetry install` on any machine — CI, production, a colleague's laptop — installs byte-for-byte identical packages, eliminating "works on my machine" failures.

</details>

<details>
<summary><strong>Question 10</strong> — Why is <code>" ".join(tokens)</code> faster than building a string with <code>+=</code> in a loop?</summary>

**Answer:** Python strings are immutable. `s += token` creates a brand-new string object on every iteration, copying all existing characters — O(n²) total work. `str.join` pre-calculates the final length, allocates one buffer, and fills it in a single pass — O(n).

</details>

---

## 11. Exercises — 5 Practical Problems

### Exercise 1 — Batched Embedding Pipeline

**Task:** Write a function `embed_dataset(texts: list[str], model, batch_size: int = 32) -> np.ndarray` that:
1. Splits `texts` into batches using a generator.
2. Calls `model.encode(batch)` on each batch.
3. Returns a single `(N, D)` numpy array without holding all intermediate results simultaneously.

<details>
<summary>Solution</summary>

```python
import numpy as np
from typing import Callable, Iterator

def _batches(texts: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(texts), size):
        yield texts[i : i + size]

def embed_dataset(
    texts: list[str],
    model,           # any object with .encode(list[str]) -> np.ndarray
    batch_size: int = 32,
) -> np.ndarray:
    results: list[np.ndarray] = []
    for batch in _batches(texts, batch_size):
        embeddings = model.encode(batch)          # shape (batch, D)
        results.append(embeddings)
    return np.vstack(results)                     # shape (N, D)
```

**Key points:** The generator avoids slicing the entire list upfront; `np.vstack` merges at the end in one allocation.

</details>

---

### Exercise 2 — Retry Decorator with Exponential Backoff

**Task:** Implement a `@retry_exponential(max_attempts, base_delay, exceptions)` decorator that doubles the wait time after each failed attempt (1s, 2s, 4s, …).

<details>
<summary>Solution</summary>

```python
import time, functools, random

def retry_exponential(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    sleep_time = delay + (random.random() * delay if jitter else 0)
                    print(f"Attempt {attempt}/{max_attempts} failed: {exc}. "
                          f"Retrying in {sleep_time:.2f}s…")
                    time.sleep(sleep_time)
                    delay *= 2
        return wrapper
    return decorator

@retry_exponential(max_attempts=4, base_delay=0.5)
def flaky_api_call(prompt: str) -> str:
    import random
    if random.random() < 0.7:
        raise ConnectionError("Simulated network error")
    return f"Response to: {prompt}"
```

</details>

---

### Exercise 3 — Async Parallel Summarisation

**Task:** Given a list of long texts, use `asyncio` + `httpx` to call a summarisation endpoint concurrently (max 5 concurrent requests). Return a list of summaries in the same order as the inputs.

<details>
<summary>Solution</summary>

```python
import asyncio, httpx, os

API_URL = "https://api.openai.com/v1/chat/completions"
API_KEY = os.environ["OPENAI_API_KEY"]

async def _summarise_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    idx: int,
    text: str,
) -> tuple[int, str]:
    async with sem:
        resp = await client.post(
            API_URL,
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Summarise in one sentence."},
                    {"role": "user", "content": text},
                ],
                "max_tokens": 64,
            },
        )
        resp.raise_for_status()
        summary = resp.json()["choices"][0]["message"]["content"]
        return idx, summary

async def parallel_summarise(texts: list[str]) -> list[str]:
    sem = asyncio.Semaphore(5)
    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        tasks = [_summarise_one(client, sem, i, t) for i, t in enumerate(texts)]
        pairs = await asyncio.gather(*tasks)
    return [summary for _, summary in sorted(pairs)]

summaries = asyncio.run(parallel_summarise(long_texts))
```

</details>

---

### Exercise 4 — Memory-Efficient Vocabulary Builder

**Task:** Build a word-frequency dictionary from a large text file (assume it does not fit in RAM) using a generator and `collections.Counter`. Then return only the top-K words by frequency.

<details>
<summary>Solution</summary>

```python
from collections import Counter
from itertools import islice

def token_stream(filepath: str):
    """Yield one token at a time from a large file."""
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            for token in line.lower().split():
                # basic cleaning — remove punctuation
                token = token.strip(".,!?;:\"'()[]{}")
                if token:
                    yield token

def build_top_vocab(filepath: str, top_k: int = 10_000) -> dict[str, int]:
    counter = Counter()
    CHUNK = 100_000
    stream = token_stream(filepath)
    while True:
        chunk = list(islice(stream, CHUNK))
        if not chunk:
            break
        counter.update(chunk)   # incremental update — never holds full stream
    return dict(counter.most_common(top_k))
```

</details>

---

### Exercise 5 — Configuration Dataclass with Validation and YAML I/O

**Task:** Create a `ModelConfig` dataclass that:
1. Validates `learning_rate > 0` and `batch_size` is a power of 2 in `__post_init__`.
2. Has a `from_yaml(path)` classmethod.
3. Has a `to_yaml(path)` method.

<details>
<summary>Solution</summary>

```python
from dataclasses import dataclass, field, asdict
import yaml, math

@dataclass
class ModelConfig:
    model_name: str
    learning_rate: float = 3e-4
    batch_size: int = 32
    max_epochs: int = 10
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.learning_rate <= 0:
            raise ValueError(f"learning_rate must be > 0, got {self.learning_rate}")
        if self.batch_size <= 0 or (self.batch_size & (self.batch_size - 1)) != 0:
            raise ValueError(f"batch_size must be a power of 2, got {self.batch_size}")

    @classmethod
    def from_yaml(cls, path: str) -> "ModelConfig":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(asdict(self), f, default_flow_style=False)

# Usage
cfg = ModelConfig(model_name="bert-base", batch_size=64)
cfg.to_yaml("config.yaml")
cfg2 = ModelConfig.from_yaml("config.yaml")
assert cfg == cfg2
```

</details>

---

## 12. References and Resources

### Free Resources

| Resource | URL | Notes |
|----------|-----|-------|
| Python Official Docs | https://docs.python.org/3/ | The authoritative source; especially `itertools`, `functools`, `asyncio` |
| Real Python | https://realpython.com | High-quality tutorials; "Python Generators", "Python Decorators", "Async IO" |
| Fast.ai Practical Deep Learning | https://course.fast.ai | Excellent Python-for-AI context; free, Jupyter-first |
| Python Design Patterns | https://python-patterns.guide | Brandon Rhodes' guide to patterns in idiomatic Python |
| Python Type Hints Cheat Sheet | https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html | Quick reference for `mypy` and `typing` module |
| Asyncio Docs | https://docs.python.org/3/library/asyncio.html | Official; pair with "Python Concurrency with asyncio" (Matthew Fowler) |
| nbstripout | https://github.com/kynan/nbstripout | Keep Jupyter outputs out of Git |

### Books

| Title | Author | Why it Matters for AI |
|-------|--------|----------------------|
| **Fluent Python** (2nd ed.) | Luciano Ramalho | Deep-dives on generators, protocols, metaclasses, async — the bible for Pythonic code |
| **Python Cookbook** (3rd ed.) | David Beazley & Brian Jones | Recipes for generators, decorators, metaprogramming; practical patterns |
| **High Performance Python** (2nd ed.) | Micha Gorelick & Ian Ozsvald | Profiling, Cython, Numba, memory layout — essential for ML performance work |
| **Robust Python** | Patrick Viafore | Type hints, dataclasses, protocols — modern type-safe Python |

### Paid Courses

| Course | Platform | Instructor | Best for |
|--------|----------|------------|----------|
| Complete Python Bootcamp: From Zero to Hero | Udemy | Jose Portilla | Comprehensive foundation; frequently on sale for <$20 |
| Python for Data Science and Machine Learning Bootcamp | Udemy | Jose Portilla | NumPy, pandas, sklearn, visualization |
| Python 3: Deep Dive (Parts 1–4) | Udemy | Fred Baptiste | Advanced internals — closures, descriptors, metaprogramming |
| Machine Learning with Python | Coursera | IBM / Ryan Ahmed | Gentle ML introduction with Python |

---

*Document version 1.0 — Last updated 2026-06-29*
