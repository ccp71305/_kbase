# Convolutional Neural Networks (CNNs) & Computer Vision

> **Module 05** | AI/Deep Machine Learning Knowledge Base
> Last updated: 2026-06-29

---

## Table of Contents

1. [Introduction & Motivation](#1-introduction--motivation)
2. [The Convolution Operation](#2-the-convolution-operation)
3. [CNN Building Blocks](#3-cnn-building-blocks)
4. [Architecture Evolution](#4-architecture-evolution)
5. [ResNets in Depth](#5-resnets-in-depth)
6. [Transfer Learning](#6-transfer-learning)
7. [Object Detection: YOLO Family](#7-object-detection-yolo-family)
8. [Semantic Segmentation: U-Net](#8-semantic-segmentation-u-net)
9. [Vision Transformers (ViT)](#9-vision-transformers-vit)
10. [Data Augmentation for Computer Vision](#10-data-augmentation-for-computer-vision)
11. [Full Project: Transfer Learning Image Classifier](#11-full-project-transfer-learning-image-classifier)
12. [Quiz: 12 Questions with Solutions](#12-quiz-12-questions-with-solutions)
13. [References & Learning Resources](#13-references--learning-resources)

---

## 1. Introduction & Motivation

### Why Not Just Use Fully Connected Networks for Images?

Consider a modest 224x224 RGB image — that is **150,528 input pixels**. A single fully connected hidden layer with 1,000 neurons requires **150 million parameters** just for the first layer. This is:

- **Computationally prohibitive** — training and inference are extremely slow
- **Data-hungry** — millions of parameters require enormous datasets to avoid overfitting
- **Spatially ignorant** — a cat in the top-left corner and the same cat in the bottom-right corner produce completely different activations; the network has no notion of translation invariance
- **Structurally blind** — edges, textures, and shapes are local structures; fully connected layers process every pixel independently with no awareness of neighborhood relationships

Convolutional Neural Networks (CNNs) solve all four problems through three core ideas:

| Idea | Mechanism | Benefit |
|---|---|---|
| **Local connectivity** | Each neuron connects to a small local patch | Captures spatial locality |
| **Parameter sharing** | The same filter weights are used across all positions | Reduces parameters by orders of magnitude |
| **Hierarchical features** | Early layers detect edges, later layers detect objects | Compositional representation learning |

### The Visual Cortex Analogy

Hubel and Wiesel's 1959 experiments on cat visual cortex discovered that neurons in V1 respond to oriented edges in specific locations — simple cells. Higher visual areas combine these to detect complex shapes. CNNs deliberately mirror this hierarchy: early conv layers behave like simple cells detecting oriented edges and color blobs; deeper layers behave like complex cells sensitive to object parts and eventually whole objects.

---

## 2. The Convolution Operation

### Mathematical Definition

Given an input feature map **I** of size H x W and a kernel (filter) **K** of size k x k, the discrete 2D convolution (technically cross-correlation as used in deep learning) at position (i, j) is:

```
(I * K)[i, j] = SUM_{m=0}^{k-1} SUM_{n=0}^{k-1}  I[i+m, j+n] * K[m, n]
```

For a multi-channel input with C_in input channels, the full convolution producing one output channel is:

```
Output[i, j] = b + SUM_{c=0}^{C_in-1} SUM_{m=0}^{k-1} SUM_{n=0}^{k-1}  I[c, i+m, j+n] * K[c, m, n]
```

Where `b` is the bias term. Each output channel has its own unique filter of shape (C_in, k, k).

### Step-by-Step ASCII Diagram: 3x3 Kernel on 5x5 Input

```
INPUT (5x5)              KERNEL (3x3)           OUTPUT (3x3)
+---+---+---+---+---+    +---+---+---+
| 1 | 2 | 3 | 0 | 1 |    | 1 | 0 |-1 |          Position [0,0]:
+---+---+---+---+---+    +---+---+---+           1*1 + 2*0 + 3*(-1)
| 4 | 5 | 6 | 7 | 2 |    | 0 | 1 | 0 |    ==>   4*0 + 5*1 + 6* 0
+---+---+---+---+---+    +---+---+---+           7*(-1)+ 8*0+ 9*1
| 7 | 8 | 9 | 1 | 3 |    |-1 | 0 | 1 |
+---+---+---+---+---+    +---+---+---+           = 1-3+5-7+9 = 5
| 0 | 1 | 2 | 3 | 4 |
+---+---+---+---+---+
| 5 | 6 | 7 | 8 | 9 |    The 3x3 kernel SLIDES across the input
+---+---+---+---+---+    with stride=1, computing a dot product
                         at every valid position.

Sliding window visualization (stride=1):

Step 1           Step 2           Step 3
[X X X . .]      [. X X X .]      [. . X X X]
[X X X . .]      [. X X X .]      [. . X X X]
[X X X . .]      [. X X X .]      [. . X X X]
[. . . . .]      [. . . . .]      [. . . . .]
[. . . . .]      [. . . . .]      [. . . . .]
 -> out[0,0]      -> out[0,1]      -> out[0,2]
```

### Output Size Formula

```
Output_size = floor((Input_size - Kernel_size + 2 * Padding) / Stride) + 1
```

Examples:
- Input=28, Kernel=3, Padding=0, Stride=1 -> Output = (28-3+0)/1 + 1 = **26**
- Input=28, Kernel=3, Padding=1, Stride=1 -> Output = (28-3+2)/1 + 1 = **28** (same-size)
- Input=28, Kernel=3, Padding=0, Stride=2 -> Output = (28-3+0)/2 + 1 = **13** (halved)

### Feature Maps and Receptive Field

A **feature map** is the output of applying one filter to the input. If a conv layer has 64 filters, it produces 64 feature maps — each highlighting a different learned pattern (edge orientation, color transition, texture frequency, etc.).

The **receptive field** of a neuron is the region of the original input that influences its output. It grows with depth:

```
Layer 1 (3x3 conv): each output neuron sees a 3x3 patch
Layer 2 (3x3 conv): each output neuron sees a 5x5 patch of the original input
Layer 3 (3x3 conv): each output neuron sees a 7x7 patch of the original input

Receptive field after L layers of 3x3 convolutions:
  RF = 1 + L * (kernel_size - 1) = 1 + L * 2
```

Deeper networks have larger effective receptive fields, enabling them to detect larger structures. This is why stacking two 3x3 convolutions is preferred over one 5x5: same receptive field, fewer parameters (2 * 9 = 18 vs 25), and an extra nonlinearity.

---

## 3. CNN Building Blocks

### 3.1 Conv2d

```python
import torch.nn as nn

# Conv2d(in_channels, out_channels, kernel_size, stride=1, padding=0)
conv = nn.Conv2d(in_channels=3, out_channels=64, kernel_size=3, stride=1, padding=1)

# Parameter count for this layer:
# 64 filters * (3 channels * 3*3 weights + 1 bias) = 64 * 28 = 1,792 parameters
# Regardless of input spatial size!
```

Key properties:
- **Weight sharing**: every position in the feature map uses the same 64 filter weights
- **Translation equivariance**: if a cat shifts right by 2 pixels, the corresponding feature map activation also shifts right by 2 pixels (equivariant, not invariant — pooling adds the invariance)

### 3.2 Pooling: Max and Average

Pooling reduces spatial dimensions, building in translation invariance and reducing computation.

```
MAX POOLING (2x2, stride=2)          AVERAGE POOLING (2x2, stride=2)

Input:                               Input:
+---+---+---+---+                   +---+---+---+---+
| 1 | 3 | 2 | 4 |                   | 1 | 3 | 2 | 4 |
+---+---+---+---+                   +---+---+---+---+
| 5 | 6 | 7 | 8 |                   | 5 | 6 | 7 | 8 |
+---+---+---+---+                   +---+---+---+---+
| 3 | 2 | 1 | 0 |                   | 3 | 2 | 1 | 0 |
+---+---+---+---+                   +---+---+---+---+
| 9 | 8 | 7 | 6 |                   | 9 | 8 | 7 | 6 |
+---+---+---+---+                   +---+---+---+---+

Output (2x2):                       Output (2x2):
+---+---+                           +-------+-------+
| 6 | 8 |                           | 3.75  |  5.25 |
+---+---+                           +-------+-------+
| 9 | 7 |                           |  5.5  |  3.5  |
+---+---+                           +-------+-------+
```

```python
max_pool   = nn.MaxPool2d(kernel_size=2, stride=2)
avg_pool   = nn.AvgPool2d(kernel_size=2, stride=2)
global_avg = nn.AdaptiveAvgPool2d((1, 1))  # Squeeze spatial dims to 1x1
```

**Global Average Pooling (GAP)** — used in modern architectures instead of large fully-connected heads. Averages each feature map to a single number, yielding a vector of length C. This dramatically reduces parameters and acts as a structural regularizer.

### 3.3 Padding

| Padding Type | Effect | Use Case |
|---|---|---|
| `padding=0` (valid) | Output shrinks | Final layers, aggressive downsampling |
| `padding=k//2` (same) | Output same size as input | Preserve spatial resolution in residual blocks |
| `padding_mode='reflect'` | Mirror-pad border | Reduces border artifacts |

### 3.4 Stride

- **Stride 1**: standard, slides one step at a time
- **Stride 2**: halves spatial dimension (replaces max-pool in many modern nets)
- **Stride > 1 in first conv**: fast downsampling of high-resolution inputs (e.g., ResNet uses 7x7 conv with stride=2)

### 3.5 Batch Normalization

Batch Normalization (Ioffe & Szegedy, 2015) normalizes activations across the mini-batch, then applies a learnable scale (gamma) and shift (beta):

```
For each channel c, across the batch and spatial positions:

  mu_c    = mean of all activations in channel c
  sigma_c = std  of all activations in channel c

  x_hat = (x - mu_c) / sqrt(sigma_c^2 + epsilon)
  y     = gamma_c * x_hat + beta_c
```

Benefits:
- Allows much higher learning rates (less sensitive to initialization)
- Acts as regularization (slight noise from batch statistics)
- Reduces internal covariate shift — keeps activations in a stable distribution
- Typically placed **after Conv2d, before activation**

```python
# Standard conv block with BN
block = nn.Sequential(
    nn.Conv2d(64, 64, kernel_size=3, padding=1, bias=False),  # bias=False since BN has its own shift
    nn.BatchNorm2d(64),
    nn.ReLU(inplace=True)
)
```

### 3.6 Activation Functions in CNNs

| Activation | Formula | Notes |
|---|---|---|
| ReLU | max(0, x) | Standard, fast, sparse activations |
| LeakyReLU | max(0.01x, x) | Fixes dying ReLU problem |
| GELU | x * Phi(x) | Used in modern ViTs and transformers |
| Sigmoid | 1/(1+e^-x) | Only in output for binary classification |
| Softmax | e^x_i / sum(e^x_j) | Multi-class output layer |

---

## 4. Architecture Evolution

### 4.1 LeNet-5 (LeCun, 1998)

The pioneer. Designed for 32x32 grayscale digit recognition (MNIST):

```
INPUT      CONV1     POOL1     CONV2     POOL2    FC1     FC2    OUTPUT
32x32x1 -> 28x28x6 -> 14x14x6 -> 10x10x16 -> 5x5x16 -> 120 -> 84 -> 10
           (5x5)     (2x2)      (5x5)       (2x2)
```

Innovations: weight sharing, local connectivity, subsampling (pooling). Proved that learned hierarchical features beat hand-crafted ones on OCR.

### 4.2 AlexNet (Krizhevsky, 2012)

The ImageNet revolution. Won ILSVRC 2012 with 15.3% top-5 error vs 26.2% runner-up:

```
INPUT         CONV1          POOL1         CONV2         POOL2
227x227x3 -> 55x55x96    -> 27x27x96   -> 27x27x256  -> 13x13x256
             (11x11, s=4)   (3x3, s=2)    (5x5, p=2)    (3x3, s=2)

CONV3         CONV4         CONV5         POOL3    FC1    FC2    OUTPUT
13x13x384 -> 13x13x384  -> 13x13x256  -> 6x6x256 -> 4096 -> 4096 -> 1000
```

Key innovations:
- **ReLU activations** (vs tanh/sigmoid) — 6x faster convergence
- **Dropout** (p=0.5) in fully connected layers — powerful regularization
- **Data augmentation** — random crops, horizontal flips
- **GPU training** — two GTX 580s, split across devices
- **Local Response Normalization** — precursor to BatchNorm

### 4.3 VGGNet (Simonyan & Zisserman, 2014)

Very Deep Networks. VGG-16 (16 weight layers) and VGG-19 showed that depth matters enormously:

```
All convolutions: 3x3, stride=1, padding=1  (same-size)
All pooling:      2x2, stride=2             (halves spatial)

BLOCK 1:  2 x Conv(64)  -> MaxPool  -> 112x112x64
BLOCK 2:  2 x Conv(128) -> MaxPool  ->  56x56x128
BLOCK 3:  3 x Conv(256) -> MaxPool  ->  28x28x256
BLOCK 4:  3 x Conv(512) -> MaxPool  ->  14x14x512
BLOCK 5:  3 x Conv(512) -> MaxPool  ->   7x7x512
           GAP or Flatten -> FC(4096) -> FC(4096) -> FC(1000)
```

Key insight: **uniform 3x3 convolutions throughout**. Two stacked 3x3 convs have the same receptive field as one 5x5 but use fewer parameters (18 vs 25 per channel) with an extra nonlinearity. VGG is extremely uniform — no inception modules, no residual connections, just depth.

Downside: 138M parameters (mostly in FC layers), high memory footprint.

### 4.4 GoogLeNet / Inception (Szegedy, 2014)

Introduced the **Inception module** — apply multiple filter sizes in parallel and concatenate:

```
                     INPUT
                       |
         +-------------+-------------+
         |       |           |       |
       1x1     1x1->3x3   1x1->5x5  3x3MaxPool->1x1
      (64ch)   (128ch)     (32ch)        (32ch)
         |       |           |             |
         +-------+-----------+-------------+
                       |
                   CONCAT (256ch)
```

The 1x1 "bottleneck" convolutions reduce channel count before the expensive 3x3 and 5x5 ops — a crucial efficiency trick that appears in ResNet bottleneck blocks too.

### 4.5 ResNet (He et al., 2015)

Covered in depth in the next section. Won ILSVRC 2015 with 3.57% top-5 error, surpassing human performance (~5%). Introduced residual (skip) connections enabling networks of 50, 101, even 1000+ layers.

### 4.6 EfficientNet (Tan & Le, 2019)

Rather than scaling depth, width, or resolution individually, EfficientNet uses **compound scaling** — a principled search over all three dimensions simultaneously with a fixed budget:

```
Depth    d = alpha^phi
Width    w = beta^phi
Resolution r = gamma^phi

Constraint: alpha * beta^2 * gamma^2 ≈ 2
phi = user-specified coefficient (1 = B0, 7 = B7)
```

EfficientNet-B0 to B7 forms a family from mobile-scale (5.3M params) to state-of-the-art (66M params), each Pareto-optimal in the accuracy/compute tradeoff. The base architecture uses Mobile Inverted Bottleneck (MBConv) blocks with Squeeze-and-Excitation.

---

## 5. ResNets in Depth

### The Degradation Problem

Before ResNets, adding more layers reliably made training accuracy **worse** — not due to overfitting, but due to optimization difficulty. The training loss itself was higher for very deep plain networks. This is the degradation problem.

Hypothesis: it should be trivially easy for extra layers to learn the identity function and do no harm. If a shallower network achieves some accuracy, the deeper version should at least match it by learning identity in extra layers. But in practice, optimizers fail to find this solution.

### Skip Connections: The Residual Learning Framework

```
PLAIN BLOCK:                    RESIDUAL BLOCK:

  x                               x
  |                               |-----(shortcut)-----+
  v                               v                    |
[Conv -> BN -> ReLU]          [Conv -> BN -> ReLU]     |
  |                               |                    |
  v                               v                    |
[Conv -> BN -> ReLU]          [Conv -> BN       ]      |
  |                               |                    |
  v                               v                    v
  y = F(x)                       y = F(x) + x  <------+
                                  |
                                  v
                                [ReLU]
```

The key insight: instead of learning the target mapping H(x) directly, let the layers learn the **residual** F(x) = H(x) - x. The output is then H(x) = F(x) + x.

**Why this works:**

1. **Gradient highway**: the shortcut connection provides a direct path for gradients to flow back to early layers without passing through all the nonlinearities. The gradient of the loss with respect to x is:

   ```
   dL/dx = dL/dy * (dF/dx + 1)
   ```

   The `+1` ensures gradients cannot vanish to zero even if dF/dx is small — there is always at least a gradient of 1 flowing through.

2. **Identity initialization**: at initialization, if weights are near zero, F(x) ≈ 0, so the block outputs ≈ x. The network starts as a near-identity function and learns deviations from it — a much easier optimization landscape.

3. **Ensemble interpretation**: a ResNet with N residual blocks can be seen as an ensemble of 2^N shorter networks (each path through the residual connections corresponds to a subnetwork), explaining their strong regularization properties.

### ResNet Architecture Variants

```python
import torch.nn as nn

class BasicBlock(nn.Module):
    """Used in ResNet-18, ResNet-34"""
    expansion = 1

    def __init__(self, in_channels, out_channels, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, stride=stride, padding=1, bias=False)
        self.bn1   = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, stride=1,      padding=1, bias=False)
        self.bn2   = nn.BatchNorm2d(out_channels)

        # Projection shortcut if spatial size or channels change
        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        out = nn.functional.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)   # The residual addition
        return nn.functional.relu(out)


class Bottleneck(nn.Module):
    """Used in ResNet-50, ResNet-101, ResNet-152"""
    expansion = 4

    def __init__(self, in_channels, mid_channels, stride=1):
        super().__init__()
        out_channels = mid_channels * 4
        # 1x1 bottleneck to reduce channels
        self.conv1 = nn.Conv2d(in_channels,  mid_channels, 1, bias=False)
        self.bn1   = nn.BatchNorm2d(mid_channels)
        # 3x3 conv in the reduced channel space
        self.conv2 = nn.Conv2d(mid_channels, mid_channels, 3, stride=stride, padding=1, bias=False)
        self.bn2   = nn.BatchNorm2d(mid_channels)
        # 1x1 to expand back up
        self.conv3 = nn.Conv2d(mid_channels, out_channels, 1, bias=False)
        self.bn3   = nn.BatchNorm2d(out_channels)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        out = nn.functional.relu(self.bn1(self.conv1(x)))
        out = nn.functional.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        out += self.shortcut(x)
        return nn.functional.relu(out)
```

| Variant | Blocks | Params | Top-1 (ImageNet) |
|---|---|---|---|
| ResNet-18 | BasicBlock: [2,2,2,2] | 11.7M | 69.8% |
| ResNet-34 | BasicBlock: [3,4,6,3] | 21.8M | 73.3% |
| ResNet-50 | Bottleneck: [3,4,6,3] | 25.6M | 76.1% |
| ResNet-101 | Bottleneck: [3,4,23,3] | 44.5M | 77.4% |
| ResNet-152 | Bottleneck: [3,8,36,3] | 60.2M | 78.3% |

---

## 6. Transfer Learning

### Why Transfer Learning Works

ImageNet-pretrained CNNs develop a powerful visual feature hierarchy:

```
Layer Depth  |  What the Filters Detect
-------------|------------------------------------------
Layers 1-2   |  Edges, corners, color blobs, Gabor-like
Layers 3-4   |  Textures, patterns, object parts
Layers 5-6   |  Object detectors (faces, wheels, text)
Final layers |  Class-specific patterns
```

These low-to-mid level features are **universal** — they are useful across nearly all visual tasks. A network trained to distinguish 1,000 ImageNet classes has learned an extraordinarily rich prior about the visual world. Fine-tuning repurposes this prior for a new domain.

Empirical support: Yosinski et al. (2014) showed that transferability is high for early layers and drops for later layers, which become more task-specific.

### Feature Extraction vs Fine-Tuning

| Strategy | When to Use | How |
|---|---|---|
| **Linear probe** | Very small dataset (<500 images/class) | Freeze all conv layers; train only final classifier head |
| **Feature extraction** | Small-medium dataset | Freeze early layers; unfreeze last 1-2 blocks + head |
| **Fine-tuning** | Medium-large dataset | Unfreeze full network; use very low LR for pretrained layers |
| **Train from scratch** | Huge dataset, very different domain | No pretrained weights |

**Learning rate strategy for fine-tuning** — use discriminative learning rates: lower LR for early (more general) layers, higher LR for later (more task-specific) layers:

```python
# Discriminative learning rates
optimizer = torch.optim.Adam([
    {'params': model.layer1.parameters(), 'lr': 1e-5},
    {'params': model.layer2.parameters(), 'lr': 1e-5},
    {'params': model.layer3.parameters(), 'lr': 1e-4},
    {'params': model.layer4.parameters(), 'lr': 1e-4},
    {'params': model.fc.parameters(),     'lr': 1e-3},
])
```

---

## 7. Object Detection: YOLO Family

### The Object Detection Task

Unlike classification (one label per image), detection produces a set of **bounding boxes** each with a class and confidence score.

Output per detection: `[x_center, y_center, width, height, confidence, class_probs...]`

### Anchor Boxes

Rather than predicting absolute box coordinates, YOLO predicts **offsets** from pre-defined anchor boxes. Anchors are chosen by clustering ground-truth box dimensions in the training set (k-means on widths/heights).

```
Grid cell (i, j) predicts B boxes relative to anchors:

For anchor (pw, ph):
  bx = sigmoid(tx) + cx    (cx = grid cell x offset)
  by = sigmoid(ty) + cy
  bw = pw * exp(tw)
  bh = ph * exp(th)
  confidence = sigmoid(to)
```

### YOLO Architecture Evolution

| Version | Year | Key Innovation | mAP (COCO) | Speed (FPS) |
|---|---|---|---|---|
| YOLOv1 | 2015 | Single-shot detection in one pass | 63.4 (VOC) | 45 |
| YOLOv2 | 2016 | Anchor boxes, batch norm, multi-scale | 78.6 (VOC) | 67 |
| YOLOv3 | 2018 | Multi-scale detection (3 scales), DarkNet-53 | 33.0 | 35 |
| YOLOv4 | 2020 | CSP, PANet, mosaic augmentation | 43.5 | 65 |
| YOLOv5 | 2020 | AutoAnchor, PyTorch, easy deployment | 48.2 | 140 |
| YOLOv8 | 2023 | Anchor-free, decoupled head, C2f blocks | 53.9 | 180 |

### IoU and NMS

**Intersection over Union (IoU)**: measures overlap between predicted box P and ground truth G:

```
IoU = Area(P ∩ G) / Area(P ∪ G)

IoU = 1.0  ->  perfect overlap
IoU > 0.5  ->  typically considered a correct detection
IoU = 0.0  ->  no overlap
```

**Non-Maximum Suppression (NMS)**: when multiple boxes detect the same object:
1. Sort all boxes by confidence score (descending)
2. Keep the highest-confidence box
3. Suppress all other boxes with IoU > threshold (e.g., 0.45) with the kept box
4. Repeat for remaining boxes

---

## 8. Semantic Segmentation: U-Net

### The Task

Semantic segmentation assigns a class label to **every pixel** in the image. Applications: medical imaging (tumor segmentation), autonomous driving (road/pedestrian/car pixels), satellite imagery.

### U-Net Architecture

Introduced by Ronneberger et al. (2015) for biomedical image segmentation. The genius is the **encoder-decoder structure with skip connections**:

```
ENCODER (Contracting Path)          DECODER (Expanding Path)
                                    
Input 572x572x1                     
     |                                                    |
  [Conv3x3, Conv3x3, ReLU] ------COPY & CONCAT-------> [Conv3x3, Conv3x3]
  64 feature maps 570x570               ^               64 feature maps
     |                                  |               568x568
  [MaxPool 2x2]                         |                  |
     v                                  |               [UpConv 2x2]
  [Conv3x3, Conv3x3, ReLU] ---COPY & CONCAT----------> [Conv3x3, Conv3x3]
  128 feature maps 284x284             ^               128 feature maps
     |                                 |                  |
  [MaxPool 2x2]                        |               [UpConv 2x2]
     v                                 |                  |
  [Conv3x3, Conv3x3, ReLU] --COPY & CONCAT-----------> [Conv3x3, Conv3x3]
  256 feature maps 140x140            ^               256 feature maps
     |                                |                  |
  [MaxPool 2x2]                       |               [UpConv 2x2]
     v                                |                  |
  [Conv3x3, Conv3x3, ReLU] -COPY & CONCAT------------> [Conv3x3, Conv3x3]
  512 feature maps 68x68             ^               512 feature maps
     |                               |                  |
  [MaxPool 2x2]                      |               [UpConv 2x2]
     v                               |                  |
  [Conv3x3, Conv3x3, ReLU]          BOTTLENECK       [Conv 1x1]
  1024 feature maps 32x32                            2 output classes
  
                     U-shape topology (hence "U-Net")
```

**Why skip connections are crucial in U-Net:**

The encoder progressively downsamples, increasing receptive field and semantic abstraction but **losing spatial precision**. Upsampling (decoder) recovers resolution but loses fine-grained spatial information. Skip connections provide the decoder with the high-resolution feature maps from the corresponding encoder level — combining semantic meaning (from deep features) with spatial precision (from shallow features).

```python
import torch
import torch.nn as nn

class DoubleConv(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
        )
    def forward(self, x): return self.net(x)

class UNet(nn.Module):
    def __init__(self, in_channels=1, num_classes=2, features=[64,128,256,512]):
        super().__init__()
        self.downs, self.ups = nn.ModuleList(), nn.ModuleList()
        self.pool = nn.MaxPool2d(2, 2)

        # Encoder
        ch = in_channels
        for f in features:
            self.downs.append(DoubleConv(ch, f)); ch = f

        self.bottleneck = DoubleConv(features[-1], features[-1]*2)

        # Decoder
        for f in reversed(features):
            self.ups.append(nn.ConvTranspose2d(f*2, f, 2, stride=2))
            self.ups.append(DoubleConv(f*2, f))

        self.final = nn.Conv2d(features[0], num_classes, 1)

    def forward(self, x):
        skips = []
        for down in self.downs:
            x = down(x); skips.append(x); x = self.pool(x)

        x = self.bottleneck(x)
        skips = skips[::-1]

        for i in range(0, len(self.ups), 2):
            x = self.ups[i](x)                          # upsample
            skip = skips[i // 2]
            if x.shape != skip.shape:
                x = nn.functional.interpolate(x, skip.shape[2:])
            x = torch.cat([skip, x], dim=1)             # skip connection
            x = self.ups[i+1](x)                        # double conv

        return self.final(x)
```

---

## 9. Vision Transformers (ViT)

### From NLP to Vision: The Patch Idea

Dosovitskiy et al. (2020) asked: what if we apply the Transformer architecture directly to images, with minimal modifications? The key challenge: self-attention is O(n^2) in sequence length — a 224x224 image has 50,176 pixels, making pixel-level attention intractable.

**Solution**: divide the image into **non-overlapping patches** (e.g., 16x16 pixels), treat each patch as a "token", and run standard Transformer encoder on the sequence of patches.

```
ViT Processing Pipeline:

Image 224x224x3
      |
  PATCH SPLIT (16x16 patches)
      |
  196 patches of shape 16x16x3
      |
  LINEAR PROJECTION (flatten + embed)
      |
  196 patch embeddings of dim D=768
      |
  PREPEND [CLS] TOKEN -> sequence length 197
      |
  ADD POSITIONAL EMBEDDINGS (learned)
      |
  TRANSFORMER ENCODER (12 layers)
  Each layer:
    LayerNorm -> Multi-Head Self-Attention -> residual
    LayerNorm -> MLP (D -> 4D -> D)        -> residual
      |
  EXTRACT [CLS] token embedding
      |
  MLP HEAD -> class logits
```

### Self-Attention for Images

Each patch embedding computes queries, keys, and values:

```
Q = x @ W_Q,   K = x @ W_K,   V = x @ W_V

Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

The attention weights reveal which patches the model attends to when classifying — highly interpretable. The [CLS] token aggregates global information from all patches via attention.

### ViT vs CNN Trade-offs

| Aspect | CNN | ViT |
|---|---|---|
| **Inductive biases** | Strong (translation equivariance, locality) | Weak (no built-in structure) |
| **Data efficiency** | High — works well with small datasets | Low — needs large pretraining data |
| **Global context** | Requires depth to get large receptive fields | Global from layer 1 via attention |
| **Scaling behavior** | Saturates earlier | Scales better with data and compute |
| **Practical threshold** | < ~1M images | > ~1M images (or large pretraining) |

Modern hybrid approaches (DeiT, Swin Transformer) add CNN-like inductive biases back into ViT, making it competitive at smaller scales.

---

## 10. Data Augmentation for Computer Vision

Augmentation is the cheapest form of regularization — create transformed versions of training images to expose the model to more variation.

### Standard Geometric Augmentations

```python
import torchvision.transforms as T

train_transform = T.Compose([
    T.RandomResizedCrop(224, scale=(0.08, 1.0)),    # random crop + resize
    T.RandomHorizontalFlip(p=0.5),                   # horizontal flip
    T.RandomRotation(degrees=15),                    # rotation +-15 degrees
    T.RandomAffine(degrees=0, translate=(0.1, 0.1)), # small translation
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406],          # ImageNet stats
                std =[0.229, 0.224, 0.225])
])
```

### Color Augmentations

```python
color_jitter = T.ColorJitter(
    brightness=0.4,   # brightness factor in [1-b, 1+b]
    contrast=0.4,     # contrast factor
    saturation=0.4,   # saturation factor
    hue=0.1           # hue shift in [-h, +h]
)
```

### Advanced Augmentations

**Cutout / Random Erasing**: randomly mask out a rectangular region of the image with zeros or noise, forcing the model to classify from partial information.

```python
# Random Erasing (torchvision built-in)
random_erase = T.RandomErasing(p=0.5, scale=(0.02, 0.33), ratio=(0.3, 3.3))
```

**Mixup** (Zhang et al., 2018): interpolate between two training images and their labels:

```python
def mixup_data(x, y, alpha=0.2):
    """
    x: batch of images,  y: batch of one-hot labels
    Returns mixed inputs, pairs of targets, and lambda
    """
    lam = np.random.beta(alpha, alpha) if alpha > 0 else 1.0
    batch_size = x.size(0)
    index = torch.randperm(batch_size)

    mixed_x = lam * x + (1 - lam) * x[index, :]
    y_a, y_b = y, y[index]
    return mixed_x, y_a, y_b, lam

def mixup_criterion(criterion, pred, y_a, y_b, lam):
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)
```

**CutMix** (Yun et al., 2019): instead of blending, paste a rectangular patch from one image into another, mixing labels proportional to patch area:

```python
def cutmix_data(x, y, alpha=1.0):
    lam = np.random.beta(alpha, alpha)
    rand_index = torch.randperm(x.size(0))

    # Bounding box coordinates
    W, H = x.size(3), x.size(2)
    cut_rat = np.sqrt(1. - lam)
    cut_w, cut_h = int(W * cut_rat), int(H * cut_rat)
    cx, cy = np.random.randint(W), np.random.randint(H)
    x1, x2 = np.clip(cx - cut_w//2, 0, W), np.clip(cx + cut_w//2, 0, W)
    y1, y2 = np.clip(cy - cut_h//2, 0, H), np.clip(cy + cut_h//2, 0, H)

    x[:, :, y1:y2, x1:x2] = x[rand_index, :, y1:y2, x1:x2]
    lam = 1 - (x2-x1)*(y2-y1) / (W*H)
    return x, y, y[rand_index], lam
```

**AutoAugment / RandAugment**: learn or randomly sample from a policy space of augmentation operations. RandAugment uses a simple uniform sampling, requiring only N (number of ops) and M (magnitude) as hyperparameters.

### Augmentation Strategy Summary

| Dataset Size | Recommended Strategy |
|---|---|
| < 1K images | Heavy augmentation + transfer learning |
| 1K-100K images | Standard augmentation + Mixup/CutMix |
| > 100K images | RandAugment or AutoAugment |
| Medical images | Domain-specific: elastic deformation, intensity scaling |

---

## 11. Full Project: Transfer Learning Image Classifier

A complete, production-quality image classifier fine-tuning ResNet-50 on a custom dataset.

### Project Structure

```
image_classifier/
├── data/
│   ├── train/
│   │   ├── class_a/
│   │   └── class_b/
│   └── val/
│       ├── class_a/
│       └── class_b/
├── train.py
├── evaluate.py
└── inference.py
```

### Complete Training Script

```python
"""
train.py — Fine-tune ResNet-50 on a custom image classification dataset.

Usage:
    python train.py --data_dir ./data --num_classes 10 --epochs 30 --batch_size 32
"""

import argparse
import time
from pathlib import Path

import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as T
from torch.optim.lr_scheduler import CosineAnnealingLR
from torchvision.models import resnet50, ResNet50_Weights


# ──────────────────────────────────────────────
# 1. DATA LOADING
# ──────────────────────────────────────────────

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

def get_transforms(train: bool) -> T.Compose:
    if train:
        return T.Compose([
            T.RandomResizedCrop(224, scale=(0.08, 1.0)),
            T.RandomHorizontalFlip(),
            T.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1),
            T.RandomRotation(15),
            T.ToTensor(),
            T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            T.RandomErasing(p=0.25),
        ])
    return T.Compose([
        T.Resize(256),
        T.CenterCrop(224),
        T.ToTensor(),
        T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def get_dataloaders(data_dir: str, batch_size: int):
    data_dir = Path(data_dir)
    train_ds = torchvision.datasets.ImageFolder(data_dir / "train", get_transforms(train=True))
    val_ds   = torchvision.datasets.ImageFolder(data_dir / "val",   get_transforms(train=False))

    train_loader = torch.utils.data.DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=4, pin_memory=True
    )
    val_loader = torch.utils.data.DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=4, pin_memory=True
    )
    return train_loader, val_loader, train_ds.classes


# ──────────────────────────────────────────────
# 2. MODEL SETUP
# ──────────────────────────────────────────────

def build_model(num_classes: int, freeze_backbone: bool = False) -> nn.Module:
    """Load pretrained ResNet-50 and replace the classifier head."""
    model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)

    if freeze_backbone:
        # Feature extraction mode: freeze everything except the new head
        for param in model.parameters():
            param.requires_grad = False

    # Replace the final fully connected layer
    in_features = model.fc.in_features          # 2048 for ResNet-50
    model.fc = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, num_classes)
    )
    return model


def get_optimizer(model: nn.Module, base_lr: float) -> torch.optim.Optimizer:
    """Discriminative learning rates: lower LR for early layers."""
    params = [
        {"params": model.layer1.parameters(), "lr": base_lr / 10},
        {"params": model.layer2.parameters(), "lr": base_lr / 10},
        {"params": model.layer3.parameters(), "lr": base_lr / 5},
        {"params": model.layer4.parameters(), "lr": base_lr / 2},
        {"params": model.fc.parameters(),     "lr": base_lr},
    ]
    # Also include conv1, bn1 with very low lr
    params.append({"params": list(model.conv1.parameters()) +
                              list(model.bn1.parameters()), "lr": base_lr / 100})
    return torch.optim.AdamW(params, weight_decay=1e-4)


# ──────────────────────────────────────────────
# 3. TRAINING LOOP
# ──────────────────────────────────────────────

def train_one_epoch(model, loader, criterion, optimizer, device, scaler):
    model.train()
    total_loss = correct = total = 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        # Mixed precision training
        with torch.cuda.amp.autocast():
            outputs = model(images)
            loss = criterion(outputs, labels)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * images.size(0)
        preds = outputs.argmax(dim=1)
        correct += (preds == labels).sum().item()
        total   += images.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = correct = total = 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        preds = outputs.argmax(dim=1)
        correct += (preds == labels).sum().item()
        total   += images.size(0)

    return total_loss / total, correct / total


# ──────────────────────────────────────────────
# 4. MAIN TRAINING ENTRY POINT
# ──────────────────────────────────────────────

def main(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_loader, val_loader, classes = get_dataloaders(args.data_dir, args.batch_size)
    print(f"Classes ({len(classes)}): {classes}")

    # Phase 1: warm up the head with frozen backbone (5 epochs)
    model = build_model(args.num_classes, freeze_backbone=True).to(device)
    optimizer = torch.optim.AdamW(model.fc.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    scaler = torch.cuda.amp.GradScaler()

    print("\n-- Phase 1: Training head only (backbone frozen) --")
    for epoch in range(5):
        tr_loss, tr_acc = train_one_epoch(model, train_loader, criterion, optimizer, device, scaler)
        va_loss, va_acc = evaluate(model, val_loader, criterion, device)
        print(f"Epoch {epoch+1:2d}/5  |  Train {tr_acc:.3f}  Val {va_acc:.3f}")

    # Phase 2: unfreeze all layers and fine-tune with discriminative LRs
    for param in model.parameters():
        param.requires_grad = True

    optimizer  = get_optimizer(model, base_lr=args.lr)
    scheduler  = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr / 100)

    best_val_acc = 0.0
    print(f"\n-- Phase 2: Full fine-tuning ({args.epochs} epochs) --")

    for epoch in range(args.epochs):
        t0 = time.time()
        tr_loss, tr_acc = train_one_epoch(model, train_loader, criterion, optimizer, device, scaler)
        va_loss, va_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        elapsed = time.time() - t0
        lr_head = optimizer.param_groups[-2]["lr"]   # head LR
        print(f"Epoch {epoch+1:3d}/{args.epochs}"
              f"  |  Train loss={tr_loss:.4f} acc={tr_acc:.4f}"
              f"  |  Val   loss={va_loss:.4f} acc={va_acc:.4f}"
              f"  |  LR={lr_head:.2e}  [{elapsed:.0f}s]")

        if va_acc > best_val_acc:
            best_val_acc = va_acc
            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "val_acc": va_acc,
                "classes": classes
            }, "best_model.pt")
            print(f"    *** New best: {best_val_acc:.4f} — saved checkpoint ***")

    print(f"\nTraining complete. Best val accuracy: {best_val_acc:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir",    default="./data")
    parser.add_argument("--num_classes", type=int, default=10)
    parser.add_argument("--epochs",      type=int, default=30)
    parser.add_argument("--batch_size",  type=int, default=32)
    parser.add_argument("--lr",          type=float, default=1e-4)
    main(parser.parse_args())
```

### Inference Script

```python
"""
inference.py — Load the best checkpoint and predict on new images.
"""

import torch
import torchvision.transforms as T
from torchvision.models import resnet50
from PIL import Image

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

def load_model(checkpoint_path: str):
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    classes = ckpt["classes"]

    model = resnet50()
    import torch.nn as nn
    model.fc = nn.Sequential(nn.Dropout(0.3), nn.Linear(2048, len(classes)))
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, classes

def predict(model, classes, image_path: str, top_k: int = 5):
    transform = T.Compose([
        T.Resize(256), T.CenterCrop(224), T.ToTensor(),
        T.Normalize(IMAGENET_MEAN, IMAGENET_STD)
    ])
    img = Image.open(image_path).convert("RGB")
    x = transform(img).unsqueeze(0)

    with torch.no_grad():
        logits = model(x)
        probs  = torch.softmax(logits, dim=1)[0]

    top_probs, top_idxs = probs.topk(top_k)
    for prob, idx in zip(top_probs, top_idxs):
        print(f"  {classes[idx]:20s}  {prob.item()*100:6.2f}%")

if __name__ == "__main__":
    model, classes = load_model("best_model.pt")
    predict(model, classes, "test_image.jpg")
```

---

## 12. Quiz: 12 Questions with Solutions

---

**Q1.** A Conv2d layer has `in_channels=3, out_channels=64, kernel_size=5`. How many trainable parameters does it have?

<details>
<summary>Solution</summary>

Each of the 64 filters has shape (3, 5, 5) plus 1 bias per filter.

Parameters = 64 * (3 * 5 * 5 + 1) = 64 * 76 = **4,864**

</details>

---

**Q2.** What is the output spatial size when you apply a Conv2d with `kernel_size=3, stride=2, padding=1` to an input of size 64x64?

<details>
<summary>Solution</summary>

Output = floor((64 - 3 + 2*1) / 2) + 1 = floor(63/2) + 1 = 31 + 1 = **32x32**

</details>

---

**Q3.** Why do ResNets use 1x1 convolutions in bottleneck blocks?

<details>
<summary>Solution</summary>

1x1 convolutions reduce the channel dimension before the expensive 3x3 convolution and restore it afterward. For example, reducing 256 -> 64 before a 3x3 conv costs 256x64x1x1 + 64x64x3x3 = 53,248 parameters vs a direct 256x256x3x3 = 589,824 parameters — a ~11x reduction, while maintaining the same effective representation.

</details>

---

**Q4.** Explain the gradient vanishing problem in deep networks and how ResNet skip connections address it.

<details>
<summary>Solution</summary>

In a deep plain network, the gradient of the loss with respect to early-layer parameters is the product of many Jacobians. If each has spectral radius < 1, this product shrinks exponentially — gradients vanish and early layers learn extremely slowly or not at all.

In ResNets, the skip connection means `output = F(x) + x`. The gradient is:

`dL/dx = dL/dy * (dF/dx + I)`

The identity term `I` (from the skip) ensures a gradient of at least 1 always flows back, preventing vanishing regardless of how small `dF/dx` becomes.

</details>

---

**Q5.** What is the difference between semantic segmentation and instance segmentation?

<details>
<summary>Solution</summary>

**Semantic segmentation** assigns a class label to every pixel but does not distinguish between separate instances of the same class. All "car" pixels are labeled "car" regardless of which car.

**Instance segmentation** (e.g., Mask R-CNN) distinguishes individual object instances: "car_1", "car_2", etc., each with a separate mask. It combines object detection (bounding boxes) with pixel-level masks per detected instance.

</details>

---

**Q6.** A U-Net uses skip connections between encoder and decoder layers. How do these differ from ResNet skip connections?

<details>
<summary>Solution</summary>

| Aspect | ResNet | U-Net |
|---|---|---|
| Operation | Addition (F(x) + x) | Concatenation (torch.cat) |
| Purpose | Gradient flow through depth | Transfer spatial detail from encoder to decoder |
| Connection | Within the same resolution | Across encoder-decoder at matching resolutions |
| Feature interaction | Residual — learn the delta | Feature fusion — combine both representations |

U-Net skips are essential for recovering fine spatial detail lost during downsampling. ResNet skips are essential for gradient propagation through depth.

</details>

---

**Q7.** What is Global Average Pooling and why is it preferred over large fully connected layers in modern CNNs?

<details>
<summary>Solution</summary>

GAP computes the spatial average of each feature map, producing one scalar per channel. For a feature map of size H x W x C, GAP outputs a vector of length C.

Advantages over FC layers:
- **Parameter-free** — no weights to learn; reduces overfitting
- **Spatial invariance** — explicitly averages out spatial information; more robust to object location
- **Arbitrary input size** — works regardless of input resolution (no fixed spatial dimension requirement)
- **Interpretability** — the output channels can be used for Class Activation Mapping (CAM)

</details>

---

**Q8.** You have a dataset of 2,000 images across 5 classes. Should you use feature extraction or full fine-tuning with a pretrained ResNet-50?

<details>
<summary>Solution</summary>

With only 2,000 images (400 per class), **feature extraction / partial fine-tuning** is the better choice. Full fine-tuning 25M parameters with so little data will overfit severely.

Recommended strategy:
1. Freeze all conv layers initially; train only the final FC head for ~5 epochs
2. Unfreeze the last 1-2 residual blocks (layer3, layer4) with very low LR (1e-5 to 1e-4)
3. Apply heavy data augmentation: flips, crops, ColorJitter, Mixup
4. Use dropout (p=0.4-0.5) in the head

</details>

---

**Q9.** In YOLO, what are anchor boxes and why are they used?

<details>
<summary>Solution</summary>

Anchor boxes are a set of pre-defined bounding box shapes (aspect ratios and scales) obtained by k-means clustering of ground-truth box dimensions in the training dataset.

Instead of predicting absolute box coordinates (an unconstrained regression problem), YOLO predicts **offsets** relative to anchors. This:
- Provides a reasonable initialization for box regression
- Allows the network to specialize different anchors for different object scales (small anchors for small objects, large anchors for large objects)
- Makes training more stable as offsets are bounded (sigmoid for center, exp for scale)

Modern YOLO versions (v8+) are anchor-free, predicting distance from each point to the four box edges directly.

</details>

---

**Q10.** What is the key difference between a ViT and a CNN in terms of inductive biases? When would you prefer each?

<details>
<summary>Solution</summary>

**CNNs** have strong inductive biases baked in:
- **Translation equivariance**: the same filter is applied everywhere
- **Locality**: neurons only connect to local neighborhoods

**ViTs** have minimal inductive biases — they treat image patches as an unordered set and learn all spatial relationships from data via self-attention.

Consequences:
- CNNs learn efficiently from small datasets because their biases align with the structure of natural images
- ViTs require much more data (or large-scale pretraining like CLIP/DINO) to learn equivalent biases from scratch
- ViTs scale better: with sufficient data, their accuracy keeps improving with model size in ways CNNs do not match

**Use CNN when**: small/medium dataset, computational constraints, need for spatial precision (detection, segmentation).
**Use ViT when**: large dataset or pretrained backbone available, need global context modeling, scaling is the priority.

</details>

---

**Q11.** What does label smoothing do in cross-entropy loss, and when is it beneficial?

<details>
<summary>Solution</summary>

Standard cross-entropy: `L = -log(p_true)` — pushes the model to output probability 1.0 for the correct class.

With label smoothing (epsilon=0.1): instead of target [0, 0, 1, 0, ...], use [0.01, 0.01, 0.91, 0.01, ...] — distributing a small probability mass to non-correct classes.

```
target_smoothed[k] = (1 - epsilon) * one_hot[k] + epsilon / K
```

Benefits:
- Prevents the model from becoming **overconfident** (logits growing without bound)
- Acts as a **regularizer**, reducing gap between training and validation performance
- Improves **calibration** — predicted probabilities better reflect true confidence

Particularly beneficial for datasets with noisy labels or when the classifier head is fine-tuned aggressively.

</details>

---

**Q12.** Explain Mixup augmentation and describe one failure case where it could be harmful.

<details>
<summary>Solution</summary>

Mixup creates a virtual training example by linearly interpolating two real examples and their labels:

```
x_mix = lambda * x_i + (1 - lambda) * x_j
y_mix = lambda * y_i + (1 - lambda) * y_j
```

where lambda ~ Beta(alpha, alpha).

**Benefits**: smoother decision boundaries, better calibration, improved generalization.

**Failure cases**:
- **Detection/Segmentation tasks**: mixing bounding box labels is non-trivial; a mixed image of a cat and a dog does not have a well-defined bounding box for either. Mixup is primarily designed for classification.
- **Very small lambda**: when lambda is close to 0 or 1, the mixed image is nearly a single image but carries a fractional label from the other class — the network learns from an almost-clean example with slightly corrupted labels, which can confuse training.
- **High alpha values**: with alpha >> 1, lambda concentrates near 0.5, creating strongly mixed images that may not exist in the real distribution, causing the model to learn unrealistic manifolds.

</details>

---

## 13. References & Learning Resources

### Free Resources (Start Here)

| Resource | Format | Why It's Essential |
|---|---|---|
| **CS231n: Convolutional Neural Networks for Visual Recognition** (Stanford) | Lecture notes + videos | THE definitive academic treatment of CNNs. Covers all fundamentals with mathematical rigor. Free at cs231n.stanford.edu |
| **fast.ai Practical Deep Learning for Coders (Part 1)** | Interactive course | Top-down approach; get state-of-the-art results on day 1, understand theory incrementally. Free at course.fast.ai |
| **PyTorch Vision Tutorials** | Code tutorials | Official PyTorch tutorials covering finetuning, transfer learning, FGSM, spatial transformers. docs.pytorch.org/tutorials |
| **Papers With Code — Image Classification** | Benchmarks + papers | Track SOTA models; every result links to the implementation. paperswithcode.com |
| **The Unreasonable Effectiveness of Deep Features** (Yosinski 2014) | Paper | Foundational transfer learning analysis; explains layer transferability |
| **Deep Residual Learning for Image Recognition** (He 2016) | Paper (arXiv:1512.03385) | Original ResNet paper — remarkably clear and readable |

### Paid / Structured Learning

| Resource | Platform | Best For |
|---|---|---|
| **Convolutional Neural Networks** (Andrew Ng) | Coursera / deeplearning.ai | Structured curriculum; excellent intuition building; part of Deep Learning Specialization |
| **fast.ai Practical Deep Learning Part 1** | fast.ai (donation-based) | Fastest path from zero to production-grade CV models |
| **Computer Vision Nanodegree** | Udacity | Project-based; good for portfolio building |

### Key Papers Chronologically

```
1998  LeNet-5         LeCun et al.        — Gradient-based learning applied to document recognition
2012  AlexNet         Krizhevsky et al.   — ImageNet classification with deep CNNs
2014  VGGNet          Simonyan & Zisserman — Very deep convolutional networks
2014  GoogLeNet       Szegedy et al.      — Going deeper with convolutions
2015  ResNet          He et al.           — Deep residual learning for image recognition
2015  U-Net           Ronneberger et al.  — U-Net: convolutional networks for biomedical segmentation
2016  YOLOv1          Redmon et al.       — You only look once: unified, real-time object detection
2019  EfficientNet    Tan & Le            — Rethinking model scaling for CNNs
2020  ViT             Dosovitskiy et al.  — An image is worth 16x16 words: transformers for image recognition
2021  DeiT            Touvron et al.      — Training data-efficient image transformers
2021  Swin Transformer Liu et al.         — Hierarchical vision transformer using shifted windows
```

### Recommended Practice Datasets

| Dataset | Classes | Size | Task |
|---|---|---|---|
| CIFAR-10/100 | 10/100 | 60K images | Classification (baseline) |
| ImageNet-1K | 1,000 | 1.2M images | Classification (benchmark) |
| Pascal VOC 2012 | 20 | 11K images | Detection + Segmentation |
| MS COCO | 80 | 330K images | Detection + Segmentation + Keypoints |
| Oxford-IIIT Pets | 37 | 7.3K images | Fine-grained classification (great for transfer learning practice) |
| Kaggle Dogs vs Cats | 2 | 25K images | Binary classification (beginner) |

---

*End of Module 05 — Convolutional Neural Networks & Computer Vision*

> **Next**: Module 06 — Recurrent Neural Networks, LSTMs, and Sequence Modeling
