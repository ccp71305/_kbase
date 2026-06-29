# AI Engineering with Python: LLMs, LangChain & Production

> **Level:** Intermediate to Advanced  
> **Prerequisites:** Python 3.10+, basic ML concepts, REST APIs  
> **Time to complete:** 8–12 hours  
> **Last updated:** June 2026

---

## Table of Contents

1. [What is AI Engineering?](#1-what-is-ai-engineering)
2. [The Modern AI Stack](#2-the-modern-ai-stack)
3. [Anthropic Claude API](#3-anthropic-claude-api)
4. [OpenAI API](#4-openai-api)
5. [Embeddings & Similarity Search](#5-embeddings--similarity-search)
6. [Vector Databases](#6-vector-databases)
7. [Prompt Engineering](#7-prompt-engineering)
8. [LangChain Deep Dive](#8-langchain-deep-dive)
9. [RAG Pipeline Architecture](#9-rag-pipeline-architecture)
10. [Agents: ReAct & Tool Use](#10-agents-react--tool-use)
11. [Hugging Face & Open-Source Models](#11-hugging-face--open-source-models)
12. [Production Patterns](#12-production-patterns)
13. [Observability & LLMOps](#13-observability--llmops)
14. [Full Project: RAG Chatbot](#14-full-project-rag-chatbot)
15. [Quiz & Solutions](#15-quiz--solutions)
16. [References & Learning Resources](#16-references--learning-resources)

---

## 1. What is AI Engineering?

AI Engineering sits at the intersection of software engineering and machine learning. Unlike traditional ML engineering (which focuses on training and tuning models), AI Engineering is primarily about **building applications on top of pre-trained foundation models**.

```
Traditional ML Engineer          AI Engineer
─────────────────────────        ──────────────────────────
Train models from scratch        Prompt-engineer pre-trained LLMs
Tune hyperparameters             Build retrieval pipelines (RAG)
Manage GPU clusters              Orchestrate multi-step LLM chains
Write loss functions             Design tool-using agents
Evaluate perplexity/BLEU         Evaluate task completion, faithfulness
```

### Core competencies of an AI Engineer

- **Prompt design** — crafting instructions that reliably produce the desired output
- **Retrieval-Augmented Generation (RAG)** — grounding LLMs with your own data
- **Agent architecture** — building autonomous systems that use tools and reason step-by-step
- **LLM API fluency** — Anthropic, OpenAI, Cohere, Mistral, Google Gemini
- **Evaluation** — measuring accuracy, hallucination rate, latency, cost
- **Production hardening** — rate limits, retries, caching, cost controls

---

## 2. The Modern AI Stack

```
┌──────────────────────────────────────────────────────────────────────┐
│                        YOUR APPLICATION                              │
│   Chat UI  │  Slack Bot  │  CLI Tool  │  Internal Search  │  API    │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                     ORCHESTRATION LAYER                              │
│         LangChain  │  LlamaIndex  │  CrewAI  │  Custom Python        │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
          ┌────────────────────┼─────────────────────┐
          │                    │                     │
┌─────────▼────────┐  ┌────────▼────────┐  ┌────────▼──────────┐
│   LLM PROVIDERS  │  │  VECTOR STORES  │  │  EXTERNAL TOOLS   │
│  Claude / GPT-4  │  │  Chroma / Pinec │  │  Search / DB / API│
│  Mistral / Llama │  │  cone / Weavi   │  │  Code Exec / Email│
└──────────────────┘  └─────────────────┘  └───────────────────┘
```

### Installation

```bash
pip install anthropic openai langchain langchain-openai langchain-anthropic \
            langchain-community chromadb tiktoken sentence-transformers \
            faiss-cpu pinecone-client weaviate-client python-dotenv \
            httpx tenacity langsmith
```

---

## 3. Anthropic Claude API

### 3.1 Client Setup

```python
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()  # loads ANTHROPIC_API_KEY from .env

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
    # Optional: custom base URL for proxies
    # base_url="https://your-proxy.com"
)
```

### 3.2 Basic Message API

```python
message = client.messages.create(
    model="claude-opus-4-5",          # or claude-sonnet-4-5, claude-haiku-3-5
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain gradient descent in 3 sentences."}
    ]
)

print(message.content[0].text)
print(f"Input tokens: {message.usage.input_tokens}")
print(f"Output tokens: {message.usage.output_tokens}")
```

### 3.3 System Prompts

System prompts define the assistant's persona, constraints, and behavior. They are separate from the conversation.

```python
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=2048,
    system="""You are an expert Python code reviewer.
- Always provide line numbers when referencing code
- Point out security vulnerabilities first
- Suggest idiomatic Python alternatives
- Be concise but thorough""",
    messages=[
        {"role": "user", "content": "Review this code:\n```python\npassword = '12345'\nquery = f\"SELECT * FROM users WHERE pw='{password}'\"\n```"}
    ]
)
```

### 3.4 Multi-Turn Conversations

```python
conversation_history = []

def chat(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful data science tutor.",
        messages=conversation_history
    )

    assistant_message = response.content[0].text
    conversation_history.append({"role": "assistant", "content": assistant_message})
    return assistant_message

print(chat("What is overfitting?"))
print(chat("How do I detect it?"))
print(chat("Give me a code example using scikit-learn."))
```

### 3.5 Streaming

Streaming delivers tokens as they're generated — essential for responsive UIs.

```python
with client.messages.stream(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a haiku about neural networks."}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

# Access final message after stream completes
final_message = stream.get_final_message()
print(f"\n\nTotal tokens: {final_message.usage.input_tokens + final_message.usage.output_tokens}")
```

### 3.6 Tool Use (Function Calling)

Claude can call tools you define, enabling agents that interact with the world.

```python
tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        }
    }
]

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}]
)

# Check if Claude wants to use a tool
if response.stop_reason == "tool_use":
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    print(f"Tool: {tool_use_block.name}")
    print(f"Input: {tool_use_block.input}")

    # Execute the real tool
    weather_result = {"temperature": 22, "condition": "Partly cloudy", "city": "Tokyo"}

    # Send result back to Claude
    final_response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        tools=tools,
        messages=[
            {"role": "user", "content": "What's the weather in Tokyo?"},
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": str(weather_result)
                    }
                ]
            }
        ]
    )
    print(final_response.content[0].text)
```

### 3.7 Vision (Image Input)

```python
import base64
from pathlib import Path

def encode_image(image_path: str) -> str:
    return base64.standard_b64encode(Path(image_path).read_bytes()).decode("utf-8")

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": encode_image("architecture_diagram.png")
                    }
                },
                {"type": "text", "text": "Describe this architecture diagram."}
            ]
        }
    ]
)
```

### 3.8 Prompt Caching

Prompt caching dramatically reduces costs and latency when you repeat large context blocks (system prompts, documents, tool definitions).

```python
# Mark content as cacheable with cache_control
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are a code assistant with knowledge of our entire codebase.",
            "cache_control": {"type": "ephemeral"}  # Cache this block
        },
        {
            "type": "text",
            "text": open("codebase_context.txt").read(),  # 50k token context
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": "Where is the payment processing logic?"}]
)

# First call: cache miss (full cost)
# Subsequent calls within ~5 min: cache hit (~10% of input cost)
print(f"Cache write tokens: {response.usage.cache_creation_input_tokens}")
print(f"Cache read tokens: {response.usage.cache_read_input_tokens}")
```

---

## 4. OpenAI API

### 4.1 Client Setup & Chat Completions

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a concise technical writer."},
        {"role": "user", "content": "Explain the transformer architecture."}
    ],
    temperature=0.3,
    max_tokens=500
)

print(response.choices[0].message.content)
print(f"Tokens used: {response.usage.total_tokens}")
```

### 4.2 Streaming with OpenAI

```python
stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Count from 1 to 10 slowly."}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### 4.3 Function Calling / Structured Output

```python
from pydantic import BaseModel

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

# Structured output — guaranteed valid JSON matching your schema
response = client.beta.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[
        {"role": "system", "content": "Extract event information."},
        {"role": "user", "content": "Alice and Bob are meeting for lunch on July 4th."}
    ],
    response_format=CalendarEvent
)

event = response.choices[0].message.parsed
print(f"Event: {event.name}, Date: {event.date}, Participants: {event.participants}")
```

### 4.4 Embeddings

```python
def get_embedding(text: str, model="text-embedding-3-small") -> list[float]:
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding

embedding = get_embedding("Machine learning is transforming software.")
print(f"Embedding dimensions: {len(embedding)}")  # 1536 for text-embedding-3-small
```

---

## 5. Embeddings & Similarity Search

### 5.1 What Are Embeddings?

Embeddings are **dense numerical vectors** that capture semantic meaning. Similar concepts map to nearby points in high-dimensional space.

```
"dog"    → [0.23, -0.41, 0.88, ...]   ─┐
"puppy"  → [0.21, -0.39, 0.85, ...]   ─┴─ very close (cosine similarity ≈ 0.98)

"car"    → [-0.67, 0.12, -0.33, ...]  ─── far from dog/puppy
```

### 5.2 Cosine Similarity

```python
import numpy as np

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

texts = [
    "Python is a programming language",
    "JavaScript runs in the browser",
    "Snakes are reptiles",
    "Coding with Python is fun"
]

embeddings = [get_embedding(t) for t in texts]

query = get_embedding("Python programming")
similarities = [(texts[i], cosine_similarity(query, embeddings[i])) for i in range(len(texts))]
similarities.sort(key=lambda x: x[1], reverse=True)

for text, score in similarities:
    print(f"{score:.4f} | {text}")
# 0.9234 | Python is a programming language
# 0.8901 | Coding with Python is fun
# 0.6123 | JavaScript runs in the browser
# 0.3456 | Snakes are reptiles
```

### 5.3 Local Embeddings with Sentence Transformers

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")  # Fast, free, 384 dims
sentences = ["This is a sentence.", "Another sentence here."]
embeddings = model.encode(sentences)
print(embeddings.shape)  # (2, 384)
```

---

## 6. Vector Databases

Vector databases are purpose-built for storing embeddings and performing fast approximate nearest-neighbor (ANN) search.

### 6.1 Chroma (Local, Great for Prototyping)

```python
import chromadb
from chromadb.utils import embedding_functions

# In-memory client for prototyping
client = chromadb.Client()

# Persistent storage
client = chromadb.PersistentClient(path="./chroma_db")

# Use OpenAI embeddings
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.environ.get("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

collection = client.create_collection(
    name="my_docs",
    embedding_function=openai_ef
)

# Add documents
collection.add(
    documents=[
        "The transformer architecture uses self-attention mechanisms.",
        "LSTM networks process sequences with gating.",
        "CNNs excel at image recognition tasks."
    ],
    ids=["doc1", "doc2", "doc3"],
    metadatas=[
        {"source": "paper", "year": 2017},
        {"source": "paper", "year": 1997},
        {"source": "textbook", "year": 2012}
    ]
)

# Query
results = collection.query(
    query_texts=["How does attention work in neural networks?"],
    n_results=2,
    where={"year": {"$gte": 2000}}  # Metadata filtering
)
print(results["documents"])
```

### 6.2 Pinecone (Managed, Production-Scale)

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))

# Create index
pc.create_index(
    name="my-rag-index",
    dimension=1536,          # Must match your embedding model
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1")
)

index = pc.Index("my-rag-index")

# Upsert vectors
vectors = [
    ("id1", get_embedding("First document"), {"text": "First document", "source": "wiki"}),
    ("id2", get_embedding("Second document"), {"text": "Second document", "source": "manual"}),
]
index.upsert(vectors=[(id_, vec, meta) for id_, vec, meta in vectors])

# Query
query_vec = get_embedding("What is the first thing?")
results = index.query(vector=query_vec, top_k=3, include_metadata=True)

for match in results.matches:
    print(f"Score: {match.score:.4f} | {match.metadata['text']}")
```

### 6.3 Weaviate (Open Source + Cloud)

```python
import weaviate
import weaviate.classes as wvc

# Connect to local Weaviate instance
client = weaviate.connect_to_local()

# Or connect to Weaviate Cloud
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=os.environ.get("WEAVIATE_URL"),
    auth_credentials=wvc.init.Auth.api_key(os.environ.get("WEAVIATE_API_KEY"))
)

# Create a collection
client.collections.create(
    name="Article",
    vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai(),
    properties=[
        wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT)
    ]
)

articles = client.collections.get("Article")

# Semantic search
results = articles.query.near_text(
    query="machine learning fundamentals",
    limit=3
)
for obj in results.objects:
    print(obj.properties["title"])

client.close()
```

### 6.4 Choosing a Vector Database

| Database   | Best For                         | Hosting     | Cost Model        |
|------------|----------------------------------|-------------|-------------------|
| Chroma     | Local dev, prototypes            | Self-hosted | Free              |
| FAISS      | Research, offline batch search   | Self-hosted | Free              |
| Pinecone   | Managed production, simplicity   | Cloud       | Per vector stored |
| Weaviate   | Open source + rich filtering     | Both        | Free / paid cloud |
| Qdrant     | High-performance, Rust-based     | Both        | Free / paid cloud |
| pgvector   | Already using PostgreSQL         | Self-hosted | Postgres cost     |

---

## 7. Prompt Engineering

### 7.1 Zero-Shot vs Few-Shot

```python
# Zero-shot
zero_shot = "Classify the sentiment: 'The movie was absolutely terrible.'"

# Few-shot — dramatically improves accuracy
few_shot = """Classify sentiment as POSITIVE, NEGATIVE, or NEUTRAL.

Examples:
Text: "I loved every minute of it!" → POSITIVE
Text: "It was okay, nothing special." → NEUTRAL
Text: "Worst experience of my life." → NEGATIVE

Text: "The movie was absolutely terrible." → """
```

### 7.2 Chain-of-Thought (CoT)

CoT prompting asks the model to reason step by step before answering.

```python
cot_prompt = """Solve this step by step.

Problem: A train travels at 60 mph for 2.5 hours, then at 80 mph for 1.5 hours.
What is the total distance?

Let me think through this:
Step 1: Calculate distance for first segment."""

# Zero-shot CoT trigger: just append "Let's think step by step."
simple_cot = """If 5 machines take 5 minutes to make 5 widgets, how long would
100 machines take to make 100 widgets?

Let's think step by step."""
```

### 7.3 Structured Output via Prompting

```python
structured_prompt = """Extract information from this job posting and return JSON only.

Job Posting:
"Senior Python Engineer at TechCorp. 5+ years required. Skills: FastAPI, PostgreSQL, 
AWS. Salary: $150k-$180k. Remote OK."

Return this exact JSON structure:
{
  "title": "",
  "company": "",
  "years_experience": 0,
  "skills": [],
  "salary_range": {"min": 0, "max": 0},
  "remote": true/false
}"""
```

### 7.4 System Prompt Best Practices

```
DO:
✓ Define persona clearly ("You are an expert Python engineer with 10 years of experience")
✓ Specify output format ("Always respond in valid JSON")
✓ Set constraints explicitly ("Never include personally identifiable information")
✓ Provide context about the task domain
✓ Use imperative language ("Do X", "Never do Y")

DON'T:
✗ Make it too long (diminishing returns after ~500 tokens for simple tasks)
✗ Contradict instructions in the user turn
✗ Use vague directives ("Be helpful" without defining what helpful means)
✗ Forget to handle edge cases
```

### 7.5 Advanced: Meta-Prompting

```python
meta_prompt = """You are a prompt engineer. Your task is to improve the following
prompt to make it more effective for {task_description}.

Original prompt:
{original_prompt}

Improved prompt:"""
```

---

## 8. LangChain Deep Dive

LangChain provides composable abstractions for building LLM applications.

### 8.1 LangChain Expression Language (LCEL)

```python
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough

# Basic chain: prompt | model | parser
llm = ChatAnthropic(model="claude-sonnet-4-5")

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Answer in {language}."),
    ("human", "{question}")
])

chain = prompt | llm | StrOutputParser()

result = chain.invoke({"question": "What is RAG?", "language": "English"})
print(result)

# Batch processing
results = chain.batch([
    {"question": "What is RAG?", "language": "English"},
    {"question": "What is fine-tuning?", "language": "Spanish"},
    {"question": "What are embeddings?", "language": "French"},
])
```

### 8.2 Streaming with LCEL

```python
for chunk in chain.stream({"question": "Explain LLMs", "language": "English"}):
    print(chunk, end="", flush=True)
```

### 8.3 Memory

```python
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.chains import ConversationChain

# Buffer Memory — stores all messages
memory = ConversationBufferMemory(return_messages=True)

# Summary Memory — summarizes older messages to save tokens
summary_memory = ConversationSummaryMemory(
    llm=llm,
    return_messages=True
)

conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=True
)

conversation.predict(input="My name is Alice.")
conversation.predict(input="What's my name?")  # Will recall "Alice"
```

### 8.4 Document Loaders

```python
from langchain_community.document_loaders import (
    PyPDFLoader,
    WebBaseLoader,
    DirectoryLoader,
    UnstructuredMarkdownLoader,
    CSVLoader
)

# Load a PDF
loader = PyPDFLoader("document.pdf")
pages = loader.load()

# Load from URL
web_loader = WebBaseLoader("https://docs.anthropic.com/en/docs/overview")
docs = web_loader.load()

# Load entire directory
dir_loader = DirectoryLoader("./docs/", glob="**/*.pdf", loader_cls=PyPDFLoader)
all_docs = dir_loader.load()

print(f"Loaded {len(all_docs)} documents")
print(f"First doc metadata: {all_docs[0].metadata}")
```

### 8.5 Text Splitters

```python
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    MarkdownHeaderTextSplitter
)

# Most commonly used — tries paragraph, sentence, word boundaries
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,       # Target chunk size in characters
    chunk_overlap=200,     # Overlap for context continuity
    separators=["\n\n", "\n", ". ", " ", ""]
)

chunks = splitter.split_documents(all_docs)
print(f"Split into {len(chunks)} chunks")

# Token-aware splitting (more precise for LLM context windows)
token_splitter = TokenTextSplitter(chunk_size=500, chunk_overlap=50)

# Structure-aware splitting for markdown
headers_to_split = [("#", "h1"), ("##", "h2"), ("###", "h3")]
md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split)
```

### 8.6 Vector Store Integration

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Create vector store from documents
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db"
)

# Load existing store
vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings
)

# Similarity search
docs = vectorstore.similarity_search("How does attention work?", k=4)

# With relevance scores
docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
    "transformer architecture",
    k=4,
    score_threshold=0.7  # Only return docs above this similarity
)
```

---

## 9. RAG Pipeline Architecture

### 9.1 Complete RAG Flow

```
                    INDEXING PHASE (offline)
┌──────────┐    ┌───────────┐    ┌──────────────┐    ┌──────────────┐
│ Documents │───▶│  Loader   │───▶│   Splitter   │───▶│  Embeddings  │
│ PDFs/Web  │    │           │    │  chunk_size= │    │  model call  │
│ Markdown  │    └───────────┘    │  1000,       │    └──────┬───────┘
└──────────┘                      │  overlap=200 │           │
                                  └──────────────┘           ▼
                                                    ┌──────────────────┐
                                                    │  Vector Database  │
                                                    │  (Chroma/Pinecone)│
                                                    └──────────────────┘

                    RETRIEVAL PHASE (online, per query)
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  User    │───▶│  Embed       │───▶│  ANN Search  │───▶│  Top-K       │
│  Query   │    │  query text  │    │  vector db   │    │  Chunks      │
└──────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
                                                               │
                    GENERATION PHASE                            │
┌──────────┐    ┌──────────────────────────────────┐          │
│  Answer  │◀───│  LLM (Claude/GPT-4)               │◀─────────┘
│          │    │  System: "Use ONLY the context"   │
└──────────┘    │  Context: [retrieved chunks]      │
                │  Question: [user query]            │
                └──────────────────────────────────┘
```

### 9.2 RAG Chain with LangChain

```python
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

retriever = vectorstore.as_retriever(
    search_type="mmr",              # Maximum Marginal Relevance for diversity
    search_kwargs={"k": 5, "fetch_k": 20}
)

rag_prompt = PromptTemplate.from_template("""
You are an assistant that answers questions based ONLY on the provided context.
If the answer cannot be found in the context, say "I don't have information about that."

Context:
{context}

Question: {question}

Answer:""")

def format_docs(docs):
    return "\n\n---\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What is the main topic of the document?")
print(answer)
```

### 9.3 Advanced RAG: HyDE (Hypothetical Document Embeddings)

```python
# Generate a hypothetical answer, embed it, use that for retrieval
hyde_prompt = PromptTemplate.from_template(
    "Write a short paragraph that would answer: {question}"
)

hyde_chain = (
    hyde_prompt
    | llm
    | StrOutputParser()
)

def hyde_retriever(question: str):
    hypothetical_doc = hyde_chain.invoke({"question": question})
    # Use hypothetical doc embedding to find real relevant docs
    return retriever.invoke(hypothetical_doc)
```

---

## 10. Agents: ReAct & Tool Use

### 10.1 The ReAct Loop

```
┌─────────────────────────────────────────────────────┐
│                    AGENT LOOP                        │
│                                                      │
│  User Input ──▶  LLM (Reason + Act)                  │
│                      │                              │
│              ┌───────▼────────┐                     │
│              │  Thought:      │  "I need to search  │
│              │  I should...   │   for X to answer"  │
│              └───────┬────────┘                     │
│                      │                              │
│              ┌───────▼────────┐                     │
│              │  Action:       │  search("X")        │
│              │  tool_name(    │                     │
│              │    args)       │                     │
│              └───────┬────────┘                     │
│                      │                              │
│              ┌───────▼────────┐                     │
│              │  Observation:  │  "Search returned:  │
│              │  tool_result   │   ..."              │
│              └───────┬────────┘                     │
│                      │                              │
│              ┌───────▼────────┐                     │
│              │  Thought:      │  "Now I have        │
│              │  Based on...   │   enough to answer" │
│              └───────┬────────┘                     │
│                      │                              │
│              ┌───────▼────────┐                     │
│              │  Final Answer  │                     │
│              └────────────────┘                     │
└─────────────────────────────────────────────────────┘
```

### 10.2 LangChain Agent with Tools

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

@tool
def search_web(query: str) -> str:
    """Search the web for current information about a topic."""
    # In production, use Tavily, SerpAPI, etc.
    return f"Search results for '{query}': [simulated results]"

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression. Input: Python math expression string."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"

@tool
def get_stock_price(ticker: str) -> str:
    """Get the current stock price for a ticker symbol."""
    # In production, call a real API
    prices = {"AAPL": 195.50, "GOOGL": 178.25, "MSFT": 415.00}
    return f"${prices.get(ticker.upper(), 'Not found')}"

tools = [search_web, calculator, get_stock_price]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant with access to tools. Use them when needed."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

agent = create_tool_calling_agent(llm=ChatAnthropic(model="claude-sonnet-4-5"), tools=tools, prompt=prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,       # Print thought process
    max_iterations=5    # Safety limit
)

result = agent_executor.invoke({
    "input": "What is 25% of Apple's current stock price?"
})
print(result["output"])
```

### 10.3 Multi-Agent Systems (Intro)

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor

# Specialist agents
researcher_agent = AgentExecutor(
    agent=create_tool_calling_agent(llm, [search_web], research_prompt),
    tools=[search_web]
)

writer_agent = AgentExecutor(
    agent=create_tool_calling_agent(llm, [], writing_prompt),
    tools=[]
)

# Orchestrator
@tool
def research_topic(topic: str) -> str:
    """Use the research agent to gather information on a topic."""
    return researcher_agent.invoke({"input": f"Research: {topic}"})["output"]

@tool
def write_article(content_brief: str) -> str:
    """Use the writing agent to create an article from a brief."""
    return writer_agent.invoke({"input": content_brief})["output"]

orchestrator = AgentExecutor(
    agent=create_tool_calling_agent(llm, [research_topic, write_article], orchestrator_prompt),
    tools=[research_topic, write_article]
)
```

---

## 11. Hugging Face & Open-Source Models

### 11.1 The `pipeline` API

```python
from transformers import pipeline

# Text classification
classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
result = classifier("This movie was absolutely fantastic!")
# [{'label': 'POSITIVE', 'score': 0.9998}]

# Text generation
generator = pipeline("text-generation", model="gpt2", max_length=100)
output = generator("The future of AI is")

# Question answering
qa = pipeline("question-answering", model="deepset/roberta-base-squad2")
result = qa(
    question="What is the capital of France?",
    context="France is a country in Western Europe. Paris is its capital city."
)
print(result["answer"])  # Paris

# Named Entity Recognition
ner = pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english")
entities = ner("Apple is looking at buying U.K. startup for $1 billion")
```

### 11.2 Loading Models Directly

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

model_name = "meta-llama/Llama-3.2-1B-Instruct"  # Requires HF token

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.bfloat16,
    device_map="auto"   # Automatically distributes across available GPUs
)

inputs = tokenizer("Explain quantum computing:", return_tensors="pt")
outputs = model.generate(
    **inputs,
    max_new_tokens=200,
    temperature=0.7,
    do_sample=True
)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

### 11.3 Fine-Tuning with QLoRA

```python
from transformers import TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType

# Configure LoRA (Low-Rank Adaptation)
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,                           # Rank
    lora_alpha=32,                  # Scaling
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none"
)

peft_model = get_peft_model(model, lora_config)
peft_model.print_trainable_parameters()
# trainable params: 8,388,608 || all params: 1,249,017,856 || trainable%: 0.67

training_args = TrainingArguments(
    output_dir="./fine_tuned_model",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    fp16=True,
    logging_steps=10,
    save_strategy="epoch"
)
```

### 11.4 HuggingFace in LangChain

```python
from langchain_community.llms import HuggingFacePipeline
from transformers import pipeline

pipe = pipeline("text-generation", model="mistralai/Mistral-7B-Instruct-v0.2",
                max_new_tokens=512, torch_dtype=torch.bfloat16, device_map="auto")

local_llm = HuggingFacePipeline(pipeline=pipe)

# Use exactly like any other LangChain LLM
chain = prompt | local_llm | StrOutputParser()
```

---

## 12. Production Patterns

### 12.1 Async API Calls

```python
import asyncio
import anthropic

async_client = anthropic.AsyncAnthropic()

async def process_document(doc: str) -> str:
    message = await async_client.messages.create(
        model="claude-haiku-3-5",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Summarize: {doc}"}]
    )
    return message.content[0].text

async def process_all_documents(docs: list[str]) -> list[str]:
    # Process 10 documents concurrently instead of sequentially
    tasks = [process_document(doc) for doc in docs]
    return await asyncio.gather(*tasks)

summaries = asyncio.run(process_all_documents(my_documents))
```

### 12.2 Retry Logic with Exponential Backoff

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import anthropic

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((
        anthropic.RateLimitError,
        anthropic.APIStatusError
    ))
)
def call_claude_with_retry(prompt: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

### 12.3 Rate Limiting

```python
import time
from collections import deque
from threading import Lock

class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.rpm = requests_per_minute
        self.requests = deque()
        self.lock = Lock()

    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()

            if len(self.requests) >= self.rpm:
                sleep_time = 60 - (now - self.requests[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)

            self.requests.append(time.time())

limiter = RateLimiter(requests_per_minute=50)

def rate_limited_call(prompt: str) -> str:
    limiter.wait_if_needed()
    return call_claude_with_retry(prompt)
```

### 12.4 Cost Management

```python
# Claude Sonnet 4.5 pricing (approximate, check anthropic.com for current rates)
COST_PER_MILLION = {
    "claude-haiku-3-5":  {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-5": {"input": 3.00,  "output": 15.00},
    "claude-opus-4-5":   {"input": 15.00, "output": 75.00},
}

class CostTracker:
    def __init__(self, budget_usd: float):
        self.budget = budget_usd
        self.spent = 0.0
        self.calls = 0

    def track(self, model: str, input_tokens: int, output_tokens: int):
        costs = COST_PER_MILLION.get(model, COST_PER_MILLION["claude-sonnet-4-5"])
        call_cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000
        self.spent += call_cost
        self.calls += 1

        if self.spent >= self.budget * 0.9:
            print(f"WARNING: 90% of budget used (${self.spent:.4f} / ${self.budget})")

    def remaining(self) -> float:
        return self.budget - self.spent

tracker = CostTracker(budget_usd=10.00)
```

### 12.5 Caching LLM Responses

```python
import hashlib
import json
import shelve

class LLMCache:
    def __init__(self, cache_path: str = "./llm_cache"):
        self.cache_path = cache_path

    def _key(self, model: str, messages: list, **kwargs) -> str:
        payload = json.dumps({"model": model, "messages": messages, **kwargs}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, model: str, messages: list, **kwargs) -> str | None:
        key = self._key(model, messages, **kwargs)
        with shelve.open(self.cache_path) as db:
            return db.get(key)

    def set(self, model: str, messages: list, response: str, **kwargs):
        key = self._key(model, messages, **kwargs)
        with shelve.open(self.cache_path) as db:
            db[key] = response

cache = LLMCache()

def cached_claude_call(messages: list, model="claude-sonnet-4-5") -> str:
    cached = cache.get(model, messages)
    if cached:
        return cached

    response = client.messages.create(model=model, max_tokens=1024, messages=messages)
    result = response.content[0].text
    cache.set(model, messages, result)
    return result
```

---

## 13. Observability & LLMOps

### 13.1 LangSmith

LangSmith is the official LangChain observability platform — traces every chain and agent run.

```python
import os

# Set env vars before importing LangChain
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "your_langsmith_api_key"
os.environ["LANGCHAIN_PROJECT"] = "my-rag-project"

# Now all LangChain calls are automatically traced
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-5")
result = chain.invoke({"question": "What is RAG?"})
# LangSmith records: inputs, outputs, latency, tokens, errors
```

### 13.2 Langfuse (Open Source Alternative)

```python
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

langfuse = Langfuse(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
    host="https://cloud.langfuse.com"
)

@observe()  # Auto-traces this function
def rag_pipeline(question: str) -> str:
    langfuse_context.update_current_trace(
        name="rag-query",
        input=question,
        metadata={"user_id": "user_123"}
    )

    docs = retriever.invoke(question)

    langfuse_context.update_current_observation(
        name="retrieval",
        output={"num_docs": len(docs)}
    )

    answer = rag_chain.invoke(question)

    langfuse_context.update_current_trace(
        output=answer,
        tags=["rag", "production"]
    )
    return answer
```

### 13.3 Structured Logging for LLM Apps

```python
import structlog
import time

logger = structlog.get_logger()

def traced_llm_call(prompt: str, model: str = "claude-sonnet-4-5") -> str:
    start = time.time()
    try:
        response = client.messages.create(
            model=model, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        latency = time.time() - start
        logger.info(
            "llm_call_success",
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=round(latency * 1000, 2),
            stop_reason=response.stop_reason
        )
        return response.content[0].text
    except Exception as e:
        logger.error("llm_call_failed", model=model, error=str(e), latency_ms=round((time.time()-start)*1000, 2))
        raise
```

---

## 14. Full Project: RAG Chatbot

Build a production-quality RAG chatbot that can answer questions over a document collection.

### Project Structure

```
rag_chatbot/
├── .env
├── requirements.txt
├── ingest.py          # Index documents
├── chatbot.py         # Main chatbot logic
├── app.py             # CLI or web interface
├── config.py          # Settings
└── docs/              # Your document collection
    ├── paper1.pdf
    └── manual.txt
```

### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str
    chroma_persist_dir: str = "./chroma_db"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_k: int = 4
    model: str = "claude-sonnet-4-5"

    class Config:
        env_file = ".env"

settings = Settings()
```

### `ingest.py`

```python
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ingest_documents(docs_dir: str = "./docs"):
    logger.info(f"Loading documents from {docs_dir}")

    loaders = [
        DirectoryLoader(docs_dir, glob="**/*.pdf", loader_cls=PyPDFLoader),
        DirectoryLoader(docs_dir, glob="**/*.txt"),
        DirectoryLoader(docs_dir, glob="**/*.md"),
    ]

    all_docs = []
    for loader in loaders:
        try:
            docs = loader.load()
            all_docs.extend(docs)
            logger.info(f"Loaded {len(docs)} documents with {loader.__class__.__name__}")
        except Exception as e:
            logger.warning(f"Loader failed: {e}")

    logger.info(f"Total documents loaded: {len(all_docs)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " "]
    )
    chunks = splitter.split_documents(all_docs)
    logger.info(f"Split into {len(chunks)} chunks")

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.openai_api_key
    )

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=settings.chroma_persist_dir,
        collection_metadata={"hnsw:space": "cosine"}
    )

    logger.info(f"Indexed {len(chunks)} chunks into ChromaDB at {settings.chroma_persist_dir}")
    return vectorstore

if __name__ == "__main__":
    ingest_documents()
```

### `chatbot.py`

```python
import anthropic
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from config import settings
from typing import Generator

class RAGChatbot:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key
        )
        self.vectorstore = Chroma(
            persist_directory=settings.chroma_persist_dir,
            embedding_function=embeddings
        )
        self.retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": settings.retrieval_k, "fetch_k": 20}
        )

        self.conversation_history = []
        self.system_prompt = """You are a helpful assistant that answers questions based on the provided document context.

RULES:
1. Answer ONLY from the provided context documents
2. If the answer isn't in the context, say "I couldn't find that in the available documents"
3. Always cite which document/section your answer comes from
4. Be concise but complete"""

    def _retrieve_context(self, query: str) -> tuple[str, list]:
        docs = self.retriever.invoke(query)
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            location = f"{source}" + (f" (page {page+1})" if page != "" else "")
            context_parts.append(f"[Source {i}: {location}]\n{doc.page_content}")
        return "\n\n".join(context_parts), docs

    def chat(self, user_message: str) -> Generator[str, None, None]:
        context, source_docs = self._retrieve_context(user_message)

        augmented_message = f"""Context documents:
{context}

User question: {user_message}"""

        self.conversation_history.append({
            "role": "user",
            "content": augmented_message
        })

        with self.client.messages.stream(
            model=settings.model,
            max_tokens=2048,
            system=self.system_prompt,
            messages=self.conversation_history
        ) as stream:
            full_response = ""
            for text in stream.text_stream:
                full_response += text
                yield text

        self.conversation_history.append({
            "role": "assistant",
            "content": full_response
        })

        # Keep only last 10 turns to manage context window
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def reset(self):
        self.conversation_history = []
        print("Conversation history cleared.")
```

### `app.py`

```python
from chatbot import RAGChatbot
import sys

def main():
    print("=" * 60)
    print("  RAG Chatbot - Ask questions about your documents")
    print("  Type 'quit' to exit, 'reset' to clear history")
    print("=" * 60)

    bot = RAGChatbot()

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("Goodbye!")
            break

        if user_input.lower() == "reset":
            bot.reset()
            continue

        print("\nAssistant: ", end="", flush=True)
        for chunk in bot.chat(user_input):
            print(chunk, end="", flush=True)
        print()

if __name__ == "__main__":
    main()
```

### Running the Project

```bash
# 1. Set up environment
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
echo "OPENAI_API_KEY=sk-..." >> .env

# 2. Add documents to ./docs/

# 3. Index documents
python ingest.py

# 4. Start chatting
python app.py
```

**Expected output:**
```
============================================================
  RAG Chatbot - Ask questions about your documents
  Type 'quit' to exit, 'reset' to clear history
============================================================

You: What are the main topics covered in the documentation?
Assistant: Based on the documents in your collection, the main topics covered are...
[streams response here]
```

---

## 15. Quiz & Solutions

Test your understanding of AI Engineering fundamentals.

### Questions

**Q1.** What is the difference between zero-shot and few-shot prompting?

**Q2.** In a RAG pipeline, what is the purpose of chunking documents? What tradeoffs does chunk size involve?

**Q3.** What does `stop_reason == "tool_use"` mean in the Anthropic response object?

**Q4.** Explain the ReAct pattern. What does each step (Reason, Act, Observe) do?

**Q5.** Why would you use prompt caching in Claude? What types of content are best to cache?

**Q6.** What is the difference between semantic search and keyword (BM25) search? When would you prefer each?

**Q7.** What is Maximum Marginal Relevance (MMR) retrieval and why might it produce better RAG results than pure similarity search?

**Q8.** List three strategies for reducing LLM API costs in a production application.

**Q9.** What is fine-tuning and when should you prefer it over RAG? When should you prefer RAG over fine-tuning?

**Q10.** What are embeddings? Why are they useful for building a search system over documents?

---

### Solutions

<details>
<summary><strong>Click to reveal answers</strong></summary>

**A1.** Zero-shot prompting provides no examples — the model must generalize from training alone. Few-shot prompting provides 2-10 examples of the desired input/output behavior in the prompt, which significantly improves accuracy for tasks that benefit from demonstration (classification, extraction, formatting). Few-shot adds tokens (cost) but reduces ambiguity.

**A2.** Chunking splits large documents into segments that fit within LLM context windows and can be retrieved individually. Smaller chunks (200-500 tokens) improve retrieval precision but may lack context. Larger chunks (1000-2000 tokens) preserve more context but may retrieve irrelevant content. Overlap between chunks helps ensure important sentences near boundaries are not lost.

**A3.** `stop_reason == "tool_use"` means Claude has decided it needs to call a function/tool to answer the question. The response contains a `tool_use` content block with the tool name and arguments. Your application must execute that tool and return the result in a follow-up message with a `tool_result` content block before Claude can give a final answer.

**A4.** ReAct stands for Reasoning + Acting. In each loop iteration: **Thought** - the LLM reasons about what it knows and what it needs; **Action** - the LLM selects and calls a tool with specific parameters; **Observation** - the tool result is fed back to the LLM. This repeats until the LLM has enough information to produce a **Final Answer**. The pattern gives LLMs the ability to iteratively gather information rather than relying solely on parametric knowledge.

**A5.** Prompt caching reduces cost (approximately 10% of normal input cost) and latency for content that is repeated across many requests - system prompts, long documents, tool definitions, few-shot examples. Best candidates: large stable system prompts (>1000 tokens), reference documents included in every request, tool schemas shared across calls. Content must be at a supported cache breakpoint and used repeatedly within the cache TTL (approximately 5 minutes for ephemeral).

**A6.** Semantic search uses embeddings to find conceptually similar content regardless of exact word matches ("car" is similar to "automobile"). Keyword search (BM25) finds documents containing exact or stemmed query terms and excels at specific terminology, product names, codes, and acronyms. Prefer semantic for natural language questions over prose documents; prefer keyword (or hybrid) for technical docs, code, or queries containing specific identifiers.

**A7.** MMR retrieves documents that are both relevant to the query AND diverse from each other. Pure similarity search can return 5 nearly identical chunks from the same paragraph, wasting context window and providing no additional information. MMR balances relevance with diversity by penalizing candidates that are too similar to already-selected documents. This produces more comprehensive context for the LLM to work with.

**A8.** (Any three): (1) Use a smaller/cheaper model for simple tasks (Haiku/GPT-4o-mini for classification, Sonnet/GPT-4o for reasoning); (2) Prompt caching for repeated long context; (3) Cache responses for identical queries; (4) Reduce max_tokens to match actual output needs; (5) Batch requests when real-time is not required; (6) Use async/concurrent calls to avoid retry waste; (7) Implement tiered routing - try cheap model first, escalate if confidence is low.

**A9.** RAG is preferred when: knowledge needs to be up-to-date (new documents can be indexed without retraining); you need source citations; the information corpus is large; you want to keep proprietary data out of model training. Fine-tuning is preferred when: you need the model to adopt a specific style or persona deeply; you have thousands of domain-specific input/output examples; you want to reduce prompt length (bake knowledge into weights); latency and cost from large context are prohibitive. They can be combined: fine-tune for style/format, RAG for factual grounding.

**A10.** Embeddings are dense numerical vectors (typically 768-3072 dimensions) produced by neural networks that represent the semantic meaning of text. Similar meanings produce nearby vectors in embedding space (measurable by cosine similarity). For document search: embed all document chunks at index time, embed the query at search time, then find the chunks whose vectors are closest to the query vector. This enables "find me text that means the same thing as my question" rather than just matching keywords.

</details>

---

## 16. References & Learning Resources

### Free Resources

| Resource | URL | What You Get |
|---|---|---|
| Anthropic Docs | https://docs.anthropic.com | Claude API reference, cookbook, prompt library |
| OpenAI Docs | https://platform.openai.com/docs | GPT API, embeddings, function calling guides |
| LangChain Docs | https://python.langchain.com | Full LCEL, agents, RAG tutorials |
| LangSmith | https://smith.langchain.com | Free observability tier |
| Hugging Face Course | https://huggingface.co/learn | NLP, diffusion, RL - all free |
| fast.ai | https://fast.ai | Practical deep learning (top-down approach) |
| DeepLearning.AI Short Courses | https://learn.deeplearning.ai | 1-hour courses, many free |

### DeepLearning.AI Free Short Courses (learn.deeplearning.ai)

- **ChatGPT Prompt Engineering for Developers** - Andrew Ng & Isa Fulford (OpenAI)
- **Building Systems with the ChatGPT API** - chaining, classification, moderation
- **LangChain for LLM Application Development** - Andrew Ng & Harrison Chase
- **LangChain: Chat with Your Data** - RAG pipeline end-to-end
- **Building and Evaluating Advanced RAG** - advanced chunking, evaluation
- **Functions, Tools and Agents with LangChain** - tool use, agents
- **Evaluating and Debugging Generative AI** - LangSmith, evaluation
- **Large Language Models with Semantic Search** - Cohere embeddings + Elasticsearch
- **Building Generative AI Applications with Gradio** - UI for LLM apps
- **Vector Databases: from Embeddings to Applications** - Weaviate

### Paid Courses (Worth It)

| Course | Platform | Why |
|---|---|---|
| LangChain for LLM Application Development | DeepLearning.AI | Best structured intro to LangChain with Andrew Ng |
| Building Systems with the ChatGPT API | DeepLearning.AI | Multi-step pipelines, safety, evaluation |
| Practical Deep Learning for Coders | fast.ai | Free but top-rated - gold standard |

### Books

- **"Hands-On Large Language Models"** - Jay Alammar & Maarten Grootendorst (O'Reilly, 2024)
- **"Building LLM Powered Applications"** - Valentina Alto (Packt, 2024)
- **"AI Engineering"** - Chip Huyen (O'Reilly, 2025)

### GitHub Repositories

- `anthropics/anthropic-cookbook` - production patterns for Claude
- `langchain-ai/langchain` - source + extensive examples
- `chroma-core/chroma` - Chroma vector database
- `openai/openai-cookbook` - OpenAI best practices

---

## Quick Reference: Model Selection Guide

```
Task                          Recommended Model            Why
─────────────────────────     ──────────────────────────   ──────────────────────
Simple classification/QA      claude-haiku-3-5             Fast, cheap
Code generation               claude-sonnet-4-5            Balanced capability/cost
Complex reasoning/analysis    claude-opus-4-5              Best capability
Document summarization        claude-haiku-3-5             Cost-effective for bulk
Vision tasks                  claude-sonnet-4-5            Strong vision + text
High-volume production        claude-haiku-3-5             Rate limits + cost
Research/exploration          claude-opus-4-5              Maximum reasoning depth
Simple completions/batch      gpt-4o-mini                  OpenAI cost-effective
Structured output (JSON)      gpt-4o with response_format  Guaranteed schema
Local/private data            Llama3 / Mistral via HF      No data leaves your infra
```

---

> **Next in this series:** `07-ai-evaluation-testing.md` - Evaluating LLM applications: metrics, frameworks (RAGAS, TruLens), A/B testing, red-teaming, and building eval pipelines.

