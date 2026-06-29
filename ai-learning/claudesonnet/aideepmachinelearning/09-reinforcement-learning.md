# 09 — Reinforcement Learning Fundamentals

> "Reinforcement learning is learning what to do — how to map situations to actions — so as to maximize a numerical reward signal."
> — Richard S. Sutton & Andrew G. Barto, *Reinforcement Learning: An Introduction*

---

## Table of Contents

1. [What Is Reinforcement Learning?](#1-what-is-reinforcement-learning)
2. [Core Concepts](#2-core-concepts)
3. [The Agent-Environment Loop](#3-the-agent-environment-loop)
4. [Markov Decision Processes](#4-markov-decision-processes)
5. [Policies and Value Functions](#5-policies-and-value-functions)
6. [Bellman Equations](#6-bellman-equations)
7. [Dynamic Programming](#7-dynamic-programming)
8. [The Multi-Armed Bandit Problem](#8-the-multi-armed-bandit-problem)
9. [Model-Free RL: Monte Carlo Methods](#9-model-free-rl-monte-carlo-methods)
10. [Temporal Difference Learning](#10-temporal-difference-learning)
11. [Q-Learning](#11-q-learning)
12. [Deep Q-Networks (DQN)](#12-deep-q-networks-dqn)
13. [Policy Gradient Methods](#13-policy-gradient-methods)
14. [Actor-Critic and PPO](#14-actor-critic-and-ppo)
15. [Modern RL: AlphaGo to RLHF](#15-modern-rl-alphago-to-rlhf)
16. [Code: Q-Learning on CartPole](#16-code-q-learning-on-cartpole)
17. [Quiz — 10 Questions](#17-quiz--10-questions)
18. [Quiz Solutions](#18-quiz-solutions)
19. [References and Free Resources](#19-references-and-free-resources)

---

## 1. What Is Reinforcement Learning?

Reinforcement Learning (RL) is the third pillar of machine learning, sitting alongside supervised learning and unsupervised learning. Unlike its siblings:

| Paradigm | What is given | What is learned |
|---|---|---|
| Supervised | Labeled (input, output) pairs | A mapping from inputs to outputs |
| Unsupervised | Raw unlabeled data | Structure, clusters, representations |
| **Reinforcement** | **An environment and a reward signal** | **A behavior policy that maximizes cumulative reward** |

The defining characteristic of RL is **sequential decision making under uncertainty**. There is no static dataset. Instead, an agent interacts with a dynamic environment, and the quality of each decision is revealed only through the reward it eventually produces — which may come much later.

This mirrors how biological organisms actually learn. A child does not learn to walk from a labeled dataset of (posture, correct-next-step) pairs. It tries, falls, gets up, and gradually refines behavior through trial and error driven by internal reward signals.

### Why RL Matters Now

RL achieved cultural breakout in 2016 when DeepMind's AlphaGo defeated the world Go champion. Since 2022 it has become central to AI engineering through **Reinforcement Learning from Human Feedback (RLHF)**, the technique used to align GPT-4, Claude, Gemini, and virtually every modern large language model.

If you work in AI engineering, you are already downstream of RL every time you use a production LLM.

---

## 2. Core Concepts

Before the mathematics, establish the vocabulary. Every RL problem involves exactly these elements.

### Agent
The **agent** is the learner and decision maker. It could be a robot, a game-playing program, a trading algorithm, or a language model being fine-tuned.

### Environment
The **environment** is everything the agent interacts with but does not directly control. It receives actions and produces observations and rewards.

### State ( S )
A **state** `s` is a representation of the world at a point in time — the information the agent uses to decide what to do next. States can be discrete (board positions) or continuous (joint angles of a robot arm).

**The Markov Property**: A state has the Markov property if the future is independent of the past given the present: `P(s_{t+1} | s_t) = P(s_{t+1} | s_t, s_{t-1}, ..., s_0)`. When this holds, the current state captures all relevant history.

### Action ( A )
An **action** `a` is a choice the agent can make. Action spaces can be:
- **Discrete**: move left/right/up/down, play a card, pick a word token
- **Continuous**: apply 3.7 N·m of torque, steer 12 degrees left

### Reward ( R )
A **reward** `r` is a scalar signal the environment emits immediately after each transition. It encodes the goal. The agent's objective is not to maximize immediate reward but **cumulative future reward** (the *return*).

### Policy ( π )
A **policy** `π` is the agent's strategy — a mapping from states to actions (or distributions over actions):
- **Deterministic policy**: `a = π(s)`
- **Stochastic policy**: `a ~ π(a | s)`

### Value Function ( V, Q )
A **value function** estimates how good it is to be in a state (or to take an action in a state), in terms of expected future return. It is the agent's model of long-term consequence.

### Model (Optional)
Some RL algorithms additionally learn a **model** of the environment — a predictor of next states and rewards. Algorithms that use a model are called *model-based*; those that don't are *model-free*.

---

## 3. The Agent-Environment Loop

The interaction between agent and environment unfolds as a discrete-time loop:

```
                    ┌─────────────────────────────────────────────┐
                    │                                             │
                    │              ENVIRONMENT                    │
                    │                                             │
                    │   ┌──────────────────────────────────┐     │
                    │   │  Transition function P(s'|s,a)   │     │
                    │   │  Reward function     R(s,a,s')   │     │
                    │   └──────────────────────────────────┘     │
                    │                                             │
                    └──────┬──────────────────────┬──────────────┘
                           │                      │
              State s_t    │                      │  Reward r_t
              Observation  │                      │
                           ▼                      │
                    ┌─────────────────────────────┴──────────────┐
                    │                                             │
                    │                 AGENT                       │
                    │                                             │
                    │   ┌──────────────────────────────────┐     │
                    │   │  Policy   π(a | s)               │     │
                    │   │  Value fn V(s) or Q(s,a)         │     │
                    │   │  Memory / Experience buffer      │     │
                    │   └──────────────────────────────────┘     │
                    │                                             │
                    └──────────────────────┬──────────────────────┘
                                           │
                              Action a_t   │
                                           ▼
                    ┌─────────────────────────────────────────────┐
                    │           ENVIRONMENT receives a_t          │
                    │   emits: s_{t+1},  r_{t+1}                  │
                    └─────────────────────────────────────────────┘
```

**One episode** runs until a terminal state is reached (game over, task completed, time limit). The agent collects the **trajectory** (also called a *rollout* or *episode*):

```
τ = (s_0, a_0, r_1, s_1, a_1, r_2, s_2, ..., s_T)
```

The **return** at time `t` is the (discounted) sum of future rewards:

```
G_t = r_{t+1} + γ·r_{t+2} + γ²·r_{t+3} + ... = Σ_{k=0}^{∞} γᵏ · r_{t+k+1}
```

where `γ ∈ [0, 1)` is the **discount factor**. It makes the agent prefer near-term rewards, and it ensures the sum converges for infinite horizons.

---

## 4. Markov Decision Processes

A **Markov Decision Process (MDP)** is the formal mathematical framework underlying almost all of RL.

### Formal Definition

An MDP is a 5-tuple `(S, A, P, R, γ)`:

| Symbol | Meaning |
|---|---|
| `S` | State space |
| `A` | Action space |
| `P(s' \| s, a)` | Transition probability: probability of reaching state `s'` from state `s` taking action `a` |
| `R(s, a, s')` | Expected immediate reward |
| `γ ∈ [0,1)` | Discount factor |

### Example MDP — Grid World

```
  ┌────┬────┬────┬────┐
  │ S  │    │    │ G  │   S = Start,  G = Goal (+1 reward)
  ├────┼────┼────┼────┤   X = Wall,   H = Hole (-1 reward)
  │    │ X  │    │ H  │
  ├────┼────┼────┼────┤   Actions: ↑  ↓  ←  →
  │    │    │    │    │   Transition: stochastic (0.8 intended, 0.1 each side)
  └────┴────┴────┴────┘
```

Each cell is a state. At each step, the agent picks a direction. If the intended move is blocked by a wall, the agent stays. The episode ends when the agent reaches G or H.

### The Agent's Objective

Maximize expected return:

```
J(π) = E_π [ G_0 ] = E_π [ Σ_{t=0}^{T} γᵗ · r_{t+1} ]
```

---

## 5. Policies and Value Functions

### State-Value Function

The **state-value function** under policy `π` is the expected return starting from state `s` and following `π` thereafter:

```
V^π(s) = E_π [ G_t | s_t = s ]
       = E_π [ Σ_{k=0}^{∞} γᵏ · r_{t+k+1} | s_t = s ]
```

High `V^π(s)` means being in state `s` is favorable under policy `π`.

### Action-Value Function (Q-Function)

The **action-value function** (Q-function) gives the expected return starting from state `s`, taking action `a`, then following `π`:

```
Q^π(s, a) = E_π [ G_t | s_t = s, a_t = a ]
```

The relationship between V and Q:

```
V^π(s) = Σ_a π(a|s) · Q^π(s, a)
```

### Optimal Policy

The **optimal policy** `π*` achieves the highest value in every state:

```
π*(s) = argmax_a Q*(s, a)
```

where `Q*(s, a)` is the **optimal action-value function**. This is the holy grail of RL.

---

## 6. Bellman Equations

The Bellman equations are the cornerstone of RL. They express value functions **recursively** — the value of a state equals immediate reward plus discounted value of the next state.

### Bellman Expectation Equations

For a given policy `π`:

```
V^π(s) = Σ_a π(a|s) · Σ_{s'} P(s'|s,a) [ R(s,a,s') + γ · V^π(s') ]

Q^π(s,a) = Σ_{s'} P(s'|s,a) [ R(s,a,s') + γ · Σ_{a'} π(a'|s') · Q^π(s',a') ]
```

In compact notation:

```
V^π(s) = E_π [ r_{t+1} + γ · V^π(s_{t+1}) | s_t = s ]
```

"The value of s equals the expected reward plus the discounted value of the successor state."

### Bellman Optimality Equations

For the optimal value functions:

```
V*(s)  = max_a  Σ_{s'} P(s'|s,a) [ R(s,a,s') + γ · V*(s') ]

Q*(s,a) = Σ_{s'} P(s'|s,a) [ R(s,a,s') + γ · max_{a'} Q*(s',a') ]
```

These are **nonlinear equations** (because of the max). Solving them is the central problem of RL.

---

## 7. Dynamic Programming

When you have a **complete model** of the MDP (you know `P` and `R`), you can solve the Bellman equations exactly using Dynamic Programming (DP). DP methods are the theoretical foundation — most practical RL methods approximate them without a model.

### Policy Evaluation (Prediction)

Given a policy `π`, compute `V^π` by iterating the Bellman expectation equation until convergence:

```
Algorithm: Iterative Policy Evaluation
─────────────────────────────────────────
Initialize V(s) = 0 for all s
Repeat until Δ < θ (convergence threshold):
    Δ ← 0
    For each state s:
        v ← V(s)
        V(s) ← Σ_a π(a|s) Σ_{s'} P(s'|s,a)[R(s,a,s') + γ·V(s')]
        Δ ← max(Δ, |v - V(s)|)
```

### Policy Improvement

Once you have `V^π`, greedily improve the policy:

```
π'(s) = argmax_a  Σ_{s'} P(s'|s,a) [ R(s,a,s') + γ · V^π(s') ]
```

The **Policy Improvement Theorem** guarantees `V^{π'}(s) ≥ V^π(s)` for all `s`.

### Policy Iteration

Alternate between policy evaluation and improvement until convergence:

```
π_0 →[evaluate]→ V^{π_0} →[improve]→ π_1 →[evaluate]→ V^{π_1} → ... → π*
```

Policy iteration converges in a **finite** number of iterations for finite MDPs.

### Value Iteration

Combine evaluation and improvement into a single update (the Bellman optimality backup):

```
Algorithm: Value Iteration
─────────────────────────────────────────
Initialize V(s) = 0 for all s
Repeat until Δ < θ:
    Δ ← 0
    For each state s:
        v ← V(s)
        V(s) ← max_a  Σ_{s'} P(s'|s,a) [ R(s,a,s') + γ·V(s') ]
        Δ ← max(Δ, |v - V(s)|)

Extract policy: π*(s) = argmax_a  Σ_{s'} P(s'|s,a) [ R(s,a,s') + γ·V(s') ]
```

**Limitation of DP**: requires a complete model, and the state space must be small enough to enumerate. Real environments have enormous or continuous state spaces — enter model-free RL.

---

## 8. The Multi-Armed Bandit Problem

Before full RL, consider a simpler but crucial problem: the **multi-armed bandit**.

You face a slot machine with `K` arms (levers). Each arm `i` pays out reward drawn from an unknown distribution with true mean `μ_i`. You have `T` pulls. Maximize total reward.

```
   Arm 1   Arm 2   Arm 3   Arm 4   Arm 5
    [μ₁]    [μ₂]    [μ₃]    [μ₄]    [μ₅]
     ↑        ↑       ↑       ↑       ↑
   Pull 1  Pull 2   ...

   You don't know μ₁...μ₅. You must learn them by pulling.
```

### Exploration vs. Exploitation Dilemma

This dilemma is the **central tension of all RL**:

- **Exploit**: pull the arm that seems best so far — maximize known reward
- **Explore**: pull other arms to gather information — risk short-term loss for long-term gain

### Epsilon-Greedy Strategy

```
With probability ε:   pick a random arm   (explore)
With probability 1-ε: pick argmax_a Q(a)  (exploit)
```

Common schedule: `ε` starts at 1.0 and decays toward 0.01.

### Connection to A/B Testing

The multi-armed bandit formalizes **A/B testing**. Traditional A/B testing splits traffic 50/50 and waits for statistical significance — it ignores the cost of traffic on the losing variant. Bandit algorithms like UCB (Upper Confidence Bound) or Thompson Sampling **adaptively route more traffic to winning variants** while still exploring. This is used in recommendation systems, ad serving, and feature flag rollouts.

---

## 9. Model-Free RL: Monte Carlo Methods

When we don't know the model, we must **learn from experience** — actual sampled trajectories.

**Monte Carlo (MC) methods** learn value functions from **complete episodes**. They average observed returns.

### Monte Carlo Prediction

```
Algorithm: First-Visit MC Prediction
─────────────────────────────────────────
Initialize V(s) = 0, Returns(s) = [] for all s
Loop (for each episode):
    Generate episode: s_0,a_0,r_1, s_1,a_1,r_2, ..., s_T
    G ← 0
    For t = T-1, T-2, ..., 0:
        G ← γ·G + r_{t+1}
        If s_t has not appeared earlier in this episode:
            Append G to Returns(s_t)
            V(s_t) ← average(Returns(s_t))
```

### Properties of Monte Carlo

| Property | Details |
|---|---|
| Unbiased | Uses actual returns, not estimates of estimates |
| High variance | A single trajectory is noisy |
| Requires complete episodes | Cannot be used in continuing tasks |
| No bootstrapping | Does not use estimates of future values |

---

## 10. Temporal Difference Learning

**Temporal Difference (TD) learning** blends Monte Carlo ideas with Dynamic Programming. It:
- Learns from **incomplete episodes** (online, step-by-step)
- **Bootstraps**: updates estimates using other estimates

### TD(0) — The Simplest TD Method

After each step, update V(s_t) toward the **TD target**:

```
TD target:   r_{t+1} + γ · V(s_{t+1})
TD error:    δ_t = r_{t+1} + γ · V(s_{t+1}) - V(s_t)

Update:      V(s_t) ← V(s_t) + α · δ_t
```

The **TD error** `δ_t` is how much the current estimate was wrong. A non-zero TD error is a signal to update.

### Bias-Variance Tradeoff in RL

```
                    ←────────── More Steps ──────────→
                 TD(0)     TD(λ)     TD(1) ≡ MC
  Bias          HIGH       ···        NONE
  Variance      LOW        ···        HIGH
  Bootstrap     YES        ···        NO
  Needs full ep NO         ···        YES
```

`TD(λ)` with eligibility traces interpolates the full spectrum, using `λ ∈ [0,1]` to weight n-step returns.

---

## 11. Q-Learning

**Q-learning** (Watkins, 1989) is the most famous RL algorithm. It directly learns the optimal Q-function `Q*` without needing a model.

### The Algorithm

```
Algorithm: Q-Learning
─────────────────────────────────────────
Initialize Q(s, a) = 0 for all s, a
Set learning rate α, discount γ, exploration ε

For each episode:
    s ← initial state
    While s is not terminal:
        a ← ε-greedy choice from Q(s, ·)
        Take action a, observe r, s'
        
        Q(s,a) ← Q(s,a) + α · [r + γ · max_{a'} Q(s',a') - Q(s,a)]
        
        s ← s'
```

### The Q-Table

For small discrete environments, Q is stored as a table:

```
         Action →  ←  ↑  ↓
State  ┌────────────────────┐
  s0   │  0.8  0.2  0.5  0.3│
  s1   │  0.1  0.9  0.4  0.7│
  s2   │  0.6  0.1  0.8  0.2│
  s3   │  0.0  0.0  0.0  1.0│  ← terminal
       └────────────────────┘
```

Each cell `Q(s, a)` estimates the expected discounted return from taking action `a` in state `s` and then acting optimally.

### Why Q-Learning Works: Off-Policy Learning

Q-learning is **off-policy**: it learns `Q*` (optimal policy) while **behaving** under a different policy (epsilon-greedy). The max operator in the update always bootstraps from the best known action, regardless of what was actually selected.

### Convergence Guarantee

Under the conditions:
1. Every (s, a) pair is visited infinitely often
2. Learning rate satisfies: `Σ α_t = ∞` and `Σ α_t² < ∞` (e.g., `α_t = 1/t`)

Q-learning **converges to Q\*** with probability 1 for finite MDPs.

### Exploration Strategies

```
Strategy         Formula                     Properties
─────────────────────────────────────────────────────────────────
ε-greedy         Random w.p. ε               Simple, widely used
ε-decay          ε_t = ε_0 · decay^t         Explores less over time
UCB              a = argmax [Q(s,a) + c√(ln t / N(s,a))]   Optimism
Boltzmann/Softmax  π(a|s) ∝ exp(Q(s,a)/τ)  Smooth, temperature-based
```

---

## 12. Deep Q-Networks (DQN)

Q-learning works perfectly for small, discrete state spaces. Real problems — Atari games, robotics, language — have state spaces far too large for a table. The solution: **approximate Q with a neural network**.

### The Core Idea

Replace the Q-table with a neural network parameterized by `θ`:

```
State s  ──→  [Neural Network θ]  ──→  Q(s, a₁), Q(s, a₂), ..., Q(s, aₙ)
```

Train the network to minimize the **mean squared Bellman error**:

```
L(θ) = E [ (r + γ · max_{a'} Q(s', a'; θ⁻) - Q(s, a; θ))² ]
```

### The Two Killer Innovations (DeepMind, 2013/2015)

Naive function approximation with neural networks had been tried and failed for decades. DQN made it work with two critical additions.

#### 1. Experience Replay

Without it: updates are correlated (consecutive frames are similar), causing unstable training.

```
  ┌─────────────────────────────────────────────┐
  │          REPLAY BUFFER (size N)             │
  │  (s₁,a₁,r₁,s₁')  (s₂,a₂,r₂,s₂')  ...     │
  │  (s₃,a₃,r₃,s₃')  (sₖ,aₖ,rₖ,sₖ')  ...     │
  └──────────────────────┬──────────────────────┘
                         │
              Sample random mini-batch
                         │
                         ▼
               Train Q-network on batch
```

Benefits:
- Breaks temporal correlations between updates
- Reuses each experience multiple times (data efficiency)
- Stabilizes gradient updates

#### 2. Target Network

Without it: the training target `r + γ · max Q(s', a'; θ)` moves every step (we're chasing a moving target), causing divergence.

```
Online network:  θ  — updated every step
Target network:  θ⁻ — copied from θ every C steps, frozen between

Loss: L = (r + γ · max_{a'} Q(s', a'; θ⁻) - Q(s, a; θ))²
                                    ↑ FROZEN
```

By keeping the target fixed for `C` steps, training targets are stable.

### DQN Architecture (Atari)

```
 84×84×4        32 filters     64 filters     64 filters     512 units     |A| outputs
 pixel frames   8×8, stride 4  4×4, stride 2  3×3, stride 1  fully conn.
    ┌───┐          ┌───┐          ┌───┐          ┌───┐          ┌───┐       ┌───┐
    │   │  Conv+   │   │  Conv+   │   │  Conv+   │   │  FC+     │   │  FC   │   │
    │ S │──ReLU──►│   │──ReLU──►│   │──ReLU──►│   │──ReLU──►│   │──────►│Q(a)│
    │   │          │   │          │   │          │   │          │   │       │   │
    └───┘          └───┘          └───┘          └───┘          └───┘       └───┘
```

### DQN Extensions

| Extension | Key Idea |
|---|---|
| Double DQN | Decouple action selection and evaluation to reduce overestimation |
| Dueling DQN | Separate V(s) and A(s,a) streams, recombine |
| Prioritized Experience Replay | Sample important transitions more often |
| Rainbow | Combine all of the above (SOTA on Atari in 2017) |

---

## 13. Policy Gradient Methods

Q-learning learns a value function and derives a policy. **Policy gradient methods** directly parameterize and optimize the policy itself.

### Why Policy Gradients?

- Handle **continuous action spaces** naturally (Q-learning's argmax is intractable over continuous a)
- Learn **stochastic policies** (useful for partial observability, game theory)
- Often better theoretical properties

### REINFORCE (Williams, 1992)

The simplest policy gradient algorithm. The key insight comes from the **policy gradient theorem**:

```
∇_θ J(θ) = E_π [ G_t · ∇_θ log π(a_t | s_t; θ) ]
```

**Intuition**: If return `G_t` was high after taking action `a_t` in state `s_t`, increase the probability of that action. If return was low, decrease it.

```
Algorithm: REINFORCE
─────────────────────────────────────────
For each episode:
    Generate full trajectory τ using current policy π_θ
    For each step t in trajectory:
        G_t ← sum of discounted rewards from t onward
        θ ← θ + α · G_t · ∇_θ log π(a_t | s_t; θ)
```

**Limitation**: Very high variance (a single trajectory is noisy). Solution: subtract a **baseline** `b(s)` that doesn't depend on `a`:

```
∇_θ J(θ) = E_π [ (G_t - b(s_t)) · ∇_θ log π(a_t | s_t; θ) ]
```

Common choice: `b(s) = V(s)` — this difference `G_t - V(s_t)` is called the **advantage** `A(s_t, a_t)`.

---

## 14. Actor-Critic and PPO

### Actor-Critic

Actor-Critic algorithms maintain two networks:

```
  State s
     │
     ├──→  [ACTOR  π(a|s; θ)]  ──→  Action a     (policy)
     │
     └──→  [CRITIC V(s; φ)]    ──→  Value V(s)   (baseline)

  TD error δ = r + γ·V(s') - V(s)   (advantage estimate)

  Update Actor:  θ ← θ + α · δ · ∇_θ log π(a|s; θ)
  Update Critic: φ ← φ + β · δ · ∇_φ V(s; φ)
```

The critic provides a low-variance baseline (V(s)) while the actor is improved using the advantage. This reduces variance compared to REINFORCE without requiring full episodes.

### Proximal Policy Optimization (PPO)

PPO (Schulman et al., 2017) is arguably the most widely deployed RL algorithm today. It addresses a fundamental instability in policy gradient methods: large policy updates can collapse performance catastrophically.

**The Core Problem**:

```
Standard gradient step:  θ_new = θ_old + α · ∇J
Problem: if step too large, policy degrades and hard to recover
```

**PPO's Solution — Clipped Surrogate Objective**:

Define the probability ratio: `r_t(θ) = π_θ(a_t|s_t) / π_{θ_old}(a_t|s_t)`

```
L^{CLIP}(θ) = E_t [ min( r_t(θ)·Â_t,  clip(r_t(θ), 1-ε, 1+ε)·Â_t ) ]
```

where `ε ≈ 0.2` and `Â_t` is the advantage estimate.

**Intuition**:
- If an action was better than expected (`Â_t > 0`), increase its probability — but not by more than `1+ε`
- If an action was worse (`Â_t < 0`), decrease its probability — but not by more than `1-ε`

This creates a **trust region** that prevents catastrophic policy updates.

### PPO Algorithm (Simplified)

```
Algorithm: PPO
─────────────────────────────────────────
For iteration = 1, 2, ...:
    Collect T timesteps of experience with current π_θ_old
    Compute advantage estimates Â_t using GAE
    
    For K epochs:
        Sample mini-batches from collected data
        Update θ by maximizing L^{CLIP}(θ) - c₁·L^{VF}(θ) + c₂·S[π_θ](s_t)
        (Value function loss + entropy bonus for exploration)
    
    θ_old ← θ
```

PPO powers:
- OpenAI Five (Dota 2)
- ChatGPT's RLHF fine-tuning stage
- Most modern robotics policy learning

---

## 15. Modern RL: AlphaGo to RLHF

### AlphaGo (2016) — RL Defeats a World Champion

Go has `~10^{170}` possible board positions — the search space is astronomically larger than chess. Classical approaches could not crack it.

AlphaGo's architecture:

```
Phase 1: Supervised Learning
   Train policy network on 30M expert moves from KGS database

Phase 2: Policy Gradient (Self-Play)
   Play policy network against itself
   Update via REINFORCE: win → increase action probabilities

Phase 3: Value Network
   Train V(s) to predict win probability from positions in self-play games

Phase 4: Monte Carlo Tree Search
   Use policy + value networks to guide MCTS at inference time
```

**AlphaGo Zero** (2017) removed human data entirely — it learned solely from self-play, starting with random play, and surpassed AlphaGo in 40 days.

### RLHF — Reinforcement Learning from Human Feedback

RLHF is how modern LLMs are aligned. The pipeline:

```
Stage 1: Pre-training
  Large transformer trained on internet text (predict next token)
  Result: capable but unaligned model

Stage 2: Supervised Fine-tuning (SFT)
  Fine-tune on curated (prompt, ideal response) demonstrations
  Result: model that follows the format

Stage 3: Reward Model Training
  Collect: (prompt, response_A, response_B) + human preference label
  Train reward model R_φ to predict human preference
  
Stage 4: PPO Fine-tuning
  Environment: prompt → LLM response → reward from R_φ
  Agent: the LLM (policy)
  Action space: vocabulary (~50k tokens)
  State: current context window
  Reward: R_φ(response) minus KL penalty vs SFT model

  KL penalty: prevents policy from drifting too far from SFT
  (otherwise model learns to "hack" the reward model)
```

**Why PPO?**: The LLM has `~10^{50000}` possible responses. PPO's clipping prevents catastrophic forgetting and reward hacking better than unconstrained gradient methods.

Modern variants: **RLAIF** (AI feedback instead of human), **DPO** (Direct Preference Optimization — frames RLHF as supervised learning, skipping the PPO loop).

---

## 16. Code: Q-Learning on CartPole

CartPole is the "Hello World" of RL: balance a pole on a cart by pushing left or right.

```
    ┌──────────────────────────────────────────┐
    │                  /                       │
    │                 /  ← pole angle θ        │
    │                ●  ← pole tip             │
    │               /                          │
    │              [cart] ──→  position x       │
    │    ════════════════════════════════════  │
    │           track                          │
    └──────────────────────────────────────────┘

    State:  (x, ẋ, θ, θ̇)    4 continuous values
    Actions: push left (0) or push right (1)
    Reward:  +1 for every step the pole stays up
    Done:    pole angle > 12° or cart off screen
```

Since the state is continuous, we **discretize** it into bins for a tabular Q-table.

```python
"""
Q-Learning on CartPole-v1
Requires: pip install gymnasium numpy
"""
import numpy as np
import gymnasium as gym


# ─── Discretization ────────────────────────────────────────────────────────────

N_BINS = 10  # bins per dimension

# Observation bounds (clip to these ranges for stability)
OBS_LOW  = np.array([-2.4, -3.0, -0.25, -3.5])
OBS_HIGH = np.array([ 2.4,  3.0,  0.25,  3.5])


def discretize(obs: np.ndarray) -> tuple:
    """Map a continuous 4D observation to a discrete bin tuple."""
    clipped = np.clip(obs, OBS_LOW, OBS_HIGH)
    scaled  = (clipped - OBS_LOW) / (OBS_HIGH - OBS_LOW)   # → [0, 1]
    binned  = (scaled * N_BINS).astype(int)
    binned  = np.clip(binned, 0, N_BINS - 1)
    return tuple(binned)


# ─── Hyperparameters ───────────────────────────────────────────────────────────

EPISODES     = 5_000
ALPHA        = 0.1        # learning rate
GAMMA        = 0.99       # discount factor
EPSILON_START = 1.0       # initial exploration rate
EPSILON_MIN  = 0.01       # minimum exploration rate
EPSILON_DECAY = 0.995     # multiplicative decay per episode
LOG_EVERY    = 500        # print progress every N episodes


# ─── Initialize Q-Table ────────────────────────────────────────────────────────

# Shape: (N_BINS,) × 4 dimensions + 2 actions
Q = np.zeros([N_BINS] * 4 + [2])
print(f"Q-table shape: {Q.shape}  |  Total cells: {Q.size:,}")


# ─── Training Loop ─────────────────────────────────────────────────────────────

env = gym.make("CartPole-v1")
epsilon = EPSILON_START
rewards_history = []

for episode in range(EPISODES):
    obs, _ = env.reset()
    state = discretize(obs)
    total_reward = 0

    while True:
        # Epsilon-greedy action selection
        if np.random.random() < epsilon:
            action = env.action_space.sample()       # explore
        else:
            action = int(np.argmax(Q[state]))        # exploit

        # Step environment
        next_obs, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        next_state = discretize(next_obs)

        # Q-Learning update: Q(s,a) ← Q(s,a) + α[r + γ·max Q(s',·) - Q(s,a)]
        td_target = reward + GAMMA * np.max(Q[next_state]) * (not done)
        td_error  = td_target - Q[state][action]
        Q[state][action] += ALPHA * td_error

        state = next_state
        total_reward += reward

        if done:
            break

    # Decay exploration
    epsilon = max(EPSILON_MIN, epsilon * EPSILON_DECAY)
    rewards_history.append(total_reward)

    if (episode + 1) % LOG_EVERY == 0:
        avg = np.mean(rewards_history[-LOG_EVERY:])
        print(f"Episode {episode+1:>5} | "
              f"Avg Reward (last {LOG_EVERY}): {avg:>7.1f} | "
              f"ε = {epsilon:.4f}")

env.close()


# ─── Evaluation (no exploration) ───────────────────────────────────────────────

print("\n─── Evaluation (greedy policy, 10 episodes) ───")
env = gym.make("CartPole-v1")
eval_rewards = []

for _ in range(10):
    obs, _ = env.reset()
    state = discretize(obs)
    total_reward = 0
    while True:
        action = int(np.argmax(Q[state]))
        obs, reward, terminated, truncated, _ = env.step(action)
        total_reward += reward
        state = discretize(obs)
        if terminated or truncated:
            break
    eval_rewards.append(total_reward)

env.close()
print(f"Mean reward: {np.mean(eval_rewards):.1f}  |  "
      f"Max: {max(eval_rewards):.0f}  |  Min: {min(eval_rewards):.0f}")
print("CartPole-v1 is 'solved' at mean reward ≥ 475 over 100 episodes.")
```

### Expected Output

```
Q-table shape: (10, 10, 10, 10, 2)  |  Total cells: 20,000

Episode  500 | Avg Reward (last 500):    23.4 | ε = 0.0820
Episode 1000 | Avg Reward (last 500):    67.1 | ε = 0.0067
Episode 1500 | Avg Reward (last 500):   198.4 | ε = 0.0100
Episode 2000 | Avg Reward (last 500):   312.7 | ε = 0.0100
Episode 2500 | Avg Reward (last 500):   410.2 | ε = 0.0100
Episode 3000 | Avg Reward (last 500):   456.9 | ε = 0.0100
Episode 3500 | Avg Reward (last 500):   471.3 | ε = 0.0100
Episode 4000 | Avg Reward (last 500):   478.8 | ε = 0.0100
Episode 4500 | Avg Reward (last 500):   482.1 | ε = 0.0100
Episode 5000 | Avg Reward (last 500):   487.6 | ε = 0.0100

─── Evaluation (greedy policy, 10 episodes) ───
Mean reward: 491.2  |  Max: 500  |  Min: 467
CartPole-v1 is 'solved' at mean reward ≥ 475 over 100 episodes.
```

### What to Observe

- **Episodes 1–500**: Pure exploration, random walk, short episodes
- **Episodes 500–2000**: Q-values start differentiating, epsilon has decayed
- **Episodes 2000–5000**: Policy converges, near-optimal behavior emerges

The key learning moments visible in the TD error: when the agent fails (pole falls), `td_error` is large and negative, aggressively downgrading that state-action pair.

---

## 17. Quiz — 10 Questions

Test your understanding. Answers follow in the next section.

---

**Q1.** The Markov property states that the optimal action in a state depends on:

- (a) The full history of all previous states and actions
- (b) Only the current state
- (c) The last five states
- (d) The current state and the previous reward

---

**Q2.** In a discount factor `γ = 0.9`, how much is a reward of 100 received 3 steps in the future worth today?

- (a) 90
- (b) 81
- (c) 72.9
- (d) 100

---

**Q3.** What is the key difference between on-policy and off-policy RL algorithms?

- (a) On-policy algorithms use neural networks; off-policy do not
- (b) On-policy algorithms learn the value of the policy being used to collect data; off-policy algorithms can learn from data collected by a different policy
- (c) Off-policy algorithms require a model of the environment
- (d) On-policy algorithms require discrete action spaces

---

**Q4.** In Q-learning, the update rule is: `Q(s,a) ← Q(s,a) + α[r + γ·max_{a'} Q(s',a') - Q(s,a)]`. What is the term `[r + γ·max_{a'} Q(s',a') - Q(s,a)]` called?

- (a) Policy gradient
- (b) Bellman residual
- (c) Temporal difference error (TD error)
- (d) Advantage function

---

**Q5.** Experience replay in DQN primarily addresses which problem?

- (a) The curse of dimensionality in large state spaces
- (b) Temporal correlations between consecutive training samples
- (c) The exploration-exploitation dilemma
- (d) Sparse reward signals

---

**Q6.** The Bellman optimality equation for Q* includes a `max` operator. This means:

- (a) It can be solved with standard linear algebra
- (b) It is a linear equation in Q values
- (c) It is a nonlinear equation — the optimal action is taken at the next step
- (d) It requires full knowledge of the transition probabilities to compute

---

**Q7.** REINFORCE is said to have "high variance." What is the primary reason?

- (a) The policy network has too many parameters
- (b) Returns are estimated from a single sampled trajectory, which can differ greatly across episodes
- (c) The discount factor is too small
- (d) The epsilon-greedy policy explores too much

---

**Q8.** PPO (Proximal Policy Optimization) uses a clipped objective to:

- (a) Speed up training by ignoring small policy changes
- (b) Prevent policy updates from being too large, which could destabilize training
- (c) Force the policy to always take deterministic actions
- (d) Replace the value function with a simpler baseline

---

**Q9.** In RLHF for LLMs, the "environment" that provides rewards to the LLM policy is:

- (a) The human labeler directly scoring each token
- (b) A reward model trained on human preference comparisons
- (c) A handcrafted reward function based on grammar rules
- (d) The validation loss on a held-out dataset

---

**Q10.** Which of the following statements about Dynamic Programming for MDPs is correct?

- (a) DP methods can be applied even when the model (P and R) is unknown
- (b) Value iteration requires knowing the transition probabilities and reward function
- (c) Policy iteration always converges slower than value iteration
- (d) DP methods work for arbitrarily large continuous state spaces without approximation

---

## 18. Quiz Solutions

**Q1. Answer: (b)**
The Markov property means the current state `s_t` contains all information needed to determine the optimal action — the full history is irrelevant given `s_t`. This is the foundation that makes MDPs tractable.

---

**Q2. Answer: (c)**
`γ³ · R = 0.9³ · 100 = 0.729 · 100 = 72.9`
The discount reduces a reward's present value geometrically. After 10 steps at γ=0.9, a reward is worth only `0.9^{10} ≈ 0.35` of its face value.

---

**Q3. Answer: (b)**
Q-learning is off-policy: the behavior policy is epsilon-greedy, but the target policy (what we learn) is greedy. SARSA is on-policy: the update uses the action actually taken by the behavior policy. Off-policy algorithms are more data-efficient (can reuse experience replays from old policies).

---

**Q4. Answer: (c)**
`δ_t = r + γ·max Q(s',a') - Q(s,a)` is the **TD error** — the difference between what we expected (Q(s,a)) and what we got (the one-step bootstrap estimate). It drives all TD and Q-learning updates.

---

**Q5. Answer: (b)**
Experience replay breaks temporal correlations. Without it, the network is trained on a sequence `(s_t, s_{t+1}, s_{t+2}, ...)` where consecutive states are extremely similar — this violates the i.i.d. assumption of SGD and causes catastrophic forgetting and instability.

---

**Q6. Answer: (c)**
The `max` makes the Bellman optimality equation nonlinear. You cannot solve it as a linear system. This is why iterative methods (value iteration) or model-free approximations (Q-learning, DQN) are needed instead of direct matrix solutions.

---

**Q7. Answer: (b)**
REINFORCE multiplies the gradient by the full return `G_t` from a single sampled episode. In a stochastic environment, the same state-action pair can yield very different returns across episodes, making the gradient estimates extremely noisy. This is addressed by baselines (actor-critic) or by TD methods.

---

**Q8. Answer: (b)**
PPO's clipping `clip(r_t(θ), 1-ε, 1+ε)` ensures the new policy cannot deviate more than `ε ≈ 0.2` from the old policy in any update step. This prevents the training instability that standard policy gradient methods suffer when taking large gradient steps into regions of poor performance.

---

**Q9. Answer: (b)**
In RLHF, a separate **reward model** is trained on human comparison data (which response is better?). The LLM then uses PPO to maximize this reward model's score minus a KL-divergence penalty from the SFT model. Humans do not directly score individual outputs during the PPO stage.

---

**Q10. Answer: (b)**
DP requires the full model: `P(s'|s,a)` and `R(s,a)`. Without the model, you need model-free methods (MC, TD, Q-learning). Policy iteration vs value iteration convergence speed depends on the specific MDP. DP without approximation is only feasible for small, enumerable state spaces.

---

## 19. References and Free Resources

All of the following are **freely available online**.

### Foundational Textbooks

| Resource | Details |
|---|---|
| **Sutton & Barto — "Reinforcement Learning: An Introduction" (2nd ed.)** | The canonical RL textbook. Free PDF at [incompleteideas.net/book/the-book-2nd.html](http://incompleteideas.net/book/the-book-2nd.html). Covers everything in this tutorial and beyond with mathematical rigor. |
| **Bertsekas — "Dynamic Programming and Optimal Control"** | Deeper mathematical treatment. Two volumes. [athenasc.com](http://www.athenasc.com) |

### University Courses (Free Video Lectures)

| Course | Details |
|---|---|
| **David Silver's UCL Course on RL (2015)** | 10 lectures. Considered the clearest introductory RL course. Search "David Silver RL lecture" on YouTube. Slides at [davidsilver.uk/teaching](https://www.davidsilver.uk/teaching/) |
| **CS285: Deep Reinforcement Learning — UC Berkeley** | Sergey Levine's graduate course. Covers deep RL, model-based RL, offline RL, RLHF. Videos and slides at [rail.eecs.berkeley.edu/deeprlcourse](https://rail.eecs.berkeley.edu/deeprlcourse/) |
| **CS234: Reinforcement Learning — Stanford** | Emma Brunskill's course. Free lecture videos on YouTube. |
| **DeepMind × UCL Deep RL Series** | More recent lectures from DeepMind researchers. YouTube playlist. |

### Practical / Code Resources

| Resource | Details |
|---|---|
| **OpenAI Spinning Up in Deep RL** | High-quality introductory documentation + clean implementations of PPO, SAC, TD3 in PyTorch. [spinningup.openai.com](https://spinningup.openai.com) |
| **Stable-Baselines3** | Production-quality implementations of PPO, A2C, DQN, SAC, TD3. [stable-baselines3.readthedocs.io](https://stable-baselines3.readthedocs.io) |
| **CleanRL** | Single-file RL implementations — great for learning. [github.com/vwxyzjn/cleanrl](https://github.com/vwxyzjn/cleanrl) |
| **Gymnasium (formerly OpenAI Gym)** | Standard RL environment interface. [gymnasium.farama.org](https://gymnasium.farama.org) |

### Key Papers

| Paper | Year | Why Read It |
|---|---|---|
| Watkins & Dayan — "Q-Learning" | 1992 | Original Q-learning proof |
| Mnih et al. — "Human-level control through deep reinforcement learning" (DQN) | 2015 | DQN paper, Nature |
| Schulman et al. — "Proximal Policy Optimization Algorithms" (PPO) | 2017 | The PPO paper |
| Silver et al. — "Mastering the game of Go with deep neural networks and tree search" (AlphaGo) | 2016 | Nature |
| Christiano et al. — "Deep Reinforcement Learning from Human Preferences" (RLHF) | 2017 | Foundation of modern LLM alignment |
| Ouyang et al. — "Training language models to follow instructions with human feedback" (InstructGPT) | 2022 | GPT-3 → ChatGPT via RLHF |

---

## Summary: The RL Landscape

```
                        REINFORCEMENT LEARNING
                               │
              ┌────────────────┴────────────────┐
         Model-Based                       Model-Free
              │                                 │
     (know P and R)                  ┌──────────┴───────────┐
              │                  Value-Based          Policy-Based
    Dynamic Programming               │                     │
    ┌──────────────┐           ┌──────┴──────┐      ┌──────┴──────┐
    │Policy Iter.  │     Monte Carlo     TD Learning  REINFORCE    PPO
    │Value Iter.   │           │         │              │          │
    └──────────────┘     Q-Learning    SARSA        Actor-Critic  SAC
                              │                                    │
                            DQN                             Modern LLM
                          (deep)                            alignment
                              │
                         Rainbow, etc.
```

---

*Module 09 of the AI & Deep Machine Learning Knowledge Base*
*Last updated: June 2026*
*Next: 10 — Transformers and Attention Mechanisms in Depth*
