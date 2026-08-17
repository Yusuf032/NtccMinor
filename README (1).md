# NTCC MINOR 

**SecureWealth AI** is an advanced, AI-powered assistant service designed for **banking professionals**. It leverages **Retrieval-Augmented Generation (RAG)** with a **LangGraph orchestrator** to provide accurate, context-aware responses based on customer financial data — accounts, transactions, and banking records.

Built with **FastAPI**, **Celery**, **Qdrant**, and **LangGraph**, this service ensures high performance, security, and scalability for production banking environments.

---

## 🚀 Key Features

*   **🔒 Secure & Private (Financial Compliance Design)**:
    *   **AES-256 Encryption**: All sensitive data (customer financial records, account details) is encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256).
    *   **PAN Masking**: PAN numbers are encrypted AND masked (XXXXX1234F) — dual protection for regulatory compliance.
    *   **Encrypted Chat History**: Both Redis (short-term) and MongoDB (long-term) message stores are encrypted.
    *   **Anonymized Search**: Identifiers (CIN, customer_id, account_id) are hashed with PBKDF2-SHA256 for secure lookups — raw PII never stored in cache keys or logs.
    *   **Role-Based Access**: Strict JWT authentication via dependency injection for bank officials.
    *   **Input Sanitization**: Security middleware validates all inputs against XSS, SQL injection, path traversal, and code injection patterns.

*   **⚡ High-Performance Architecture**:
    *   **Asynchronous Processing**: Heavy tasks like embedding generation are offloaded to **Celery** workers with idempotency guards.
    *   **Hybrid Search**: Combines **Qdrant** (Vector Search) with MongoDB legacy metadata lookups for maximum recall.
    *   **Multi-Layer Caching**:
        *   **Redis**: Read-through cache for records (1h TTL) and query results.
        *   **Semantic Cache**: RedisVL-powered vector similarity cache for LLM response reuse.
    *   **LangGraph Query Routing**: Intelligent state machine classifies queries as identity, conversational, or factual — routes to cache or RAG accordingly.

*   **🛡️ Robust & Resilient**:
    *   **Circuit Breakers**: Implemented for **Redis**, **Qdrant**, and **LLM** calls to prevent cascading failures.
    *   **Graceful Shutdown**: Background monitoring tasks are cleanly cancelled on service exit.
    *   **Health Monitoring**: Comprehensive `/health` endpoint checking DB, Redis, and Qdrant connectivity.
    *   **Rate Limiting**: IP-based request throttling (configurable window and limit).

*   **🧠 Intelligent Insights**:
    *   **Groq (Llama 3)**: Ultra-fast inference for generating financially relevant summaries and answers.
    *   **Semantic Understanding**: Finds records based on meaning (e.g., "large withdrawals") even if exact keywords mismatch.
    *   **Session Memory**: Multi-turn conversations backed by short-term (Redis) and long-term (MongoDB) memory with LLM-generated session summaries.

---

## 🛠️ Technology Stack

| Category | Technology |
| :--- | :--- |
| **Framework** | FastAPI (Python 3.10+) |
| **Task Queue** | Celery (Redis Broker + Backend) |
| **Vector Database** | Qdrant (Cosine Similarity, 384-dim) |
| **Cache** | Redis Stack (Async + Sync + RediSearch) |
| **Database** | MongoDB (Motor async + PyMongo sync) |
| **LLM Engine** | Groq — Llama 3 (via LangChain) |
| **Embeddings** | Sentence-Transformers (`all-MiniLM-L6-v2`) |
| **Orchestrator** | LangGraph (State Machine for query routing) |
| **Semantic Cache** | RedisVL (Vector similarity search) |
| **Encryption** | Fernet (AES-128-CBC + HMAC-SHA256) |
| **Logging** | AI-Watchman (Centralized log aggregation) |
| **CI/CD** | GitHub Actions → AWS ECR |
| **Container** | Docker + Docker Compose |

---

## 🏗️ System Architecture

### Overall Architecture

```mermaid
graph TD
    BankOfficial["🏦 Bank Official"] -->|"JWT Auth"| API["⚡ FastAPI Service"]
    
    subgraph "SecureWealth AI Platform"
        API -->|"/banking/*"| Routes["🔀 Banking Routes"]
        
        subgraph "BankingService"
            Routes -->|"POST /transaction"| AddRecord["📝 Add Record"]
            Routes -->|"GET /customer"| GetRecords["📋 Get Records"]
            Routes -->|"GET /query"| QueryPipeline["🤖 AI Query"]
            Routes -->|"POST /session/start"| StartSession["▶️ Start Session"]
            Routes -->|"DELETE /session/close"| CloseSession["⏹️ Close Session"]
            
            AddRecord -->|"Encrypt"| Encryption["🔐 AES-256 + SHA-256 + PAN Mask"]
            GetRecords -->|"Hash Lookup"| Encryption
        end
        
        subgraph "AI Query Pipeline"
            QueryPipeline --> RedisCache{"📦 Redis Cache"}
            RedisCache -->|"HIT"| InstantReturn["⚡ Instant Return"]
            RedisCache -->|"MISS"| CB["🛡️ Circuit Breaker"]
            CB -->|"OPEN"| FastFail["⛔ Fast Fail"]
            CB -->|"CLOSED"| Orchestrator["🔀 LangGraph Orchestrator"]
            
            Orchestrator -->|"Classify"| Classifier["🏷️ Query Classifier"]
            Classifier -->|"Factual"| SemanticCache["🧊 Semantic Cache"]
            Classifier -->|"Conversational"| RAG["📚 RAG Pipeline"]
            Classifier -->|"Identity"| Memory["🧠 Short Memory"]
            
            SemanticCache -->|"Cache Miss"| RAG
            SemanticCache -->|"Cache Hit"| CachedReturn["⚡ Cached Response"]
            RAG -->|"Context"| Memory
        end
        
        subgraph "Session Management"
            StartSession -->|"Load Summaries"| LongMemory["💾 Long Memory"]
            StartSession -->|"Background"| Celery["⚙️ Celery Worker"]
            CloseSession -->|"Summarize + Archive"| LongMemory
        end
        
        subgraph "Data Stores"
            Encryption --> Mongo[("🍃 MongoDB")]
            RAG -->|"Vector Search"| Qdrant[("🔍 Qdrant")]
            Memory -->|"Chat History"| Redis[("📦 Redis")]
            LongMemory -->|"Summaries"| Mongo
            Celery -->|"Embeddings"| Qdrant
            Celery -->|"Fetch Records"| Mongo
        end
    end
    
    subgraph "External AI"
        Memory -->|"Inference"| Groq["🧠 Groq / Llama 3"]
    end
```

### Banking Module Architecture

```mermaid
graph TD
    Official["🏦 Bank Official"] -->|"JWT Auth"| Routes["Banking Routes<br/>/banking/*"]
    
    Routes -->|"POST /transaction"| AddRecord["Add Banking Record"]
    Routes -->|"GET /customer"| GetRecords["Get Customer Records"]
    Routes -->|"POST /session/start"| StartSession["Start Session"]
    Routes -->|"DELETE /session/close"| CloseSession["Close Session"]
    Routes -->|"GET /query"| RAGQuery["AI Query (RAG)"]
    Routes -->|"POST /embeddings/load"| LoadEmbed["Load Embeddings"]
    
    subgraph "BankingService"
        AddRecord -->|"1. Validate"| Validate["Validate Input"]
        Validate -->|"2. Encrypt"| Encrypt["Encrypted_BankingRecord"]
        Encrypt -->|"3. Store"| MongoBanking[("MongoDB<br/>banking_transactions")]
        
        GetRecords -->|"1. Hash CIN"| HashLookup["SHA-256 Hash Lookup"]
        HashLookup -->|"2. Cache Check"| RedisCache[("Redis Cache<br/>1h TTL")]
        RedisCache -->|"3. Cache Miss"| MongoBanking
        MongoBanking -->|"4. Decrypt"| Decrypt["AES-256 Decrypt"]
        
        RAGQuery -->|"1. Context"| QdrantSearch["Qdrant Semantic Search"]
        QdrantSearch -->|"2. Prompt"| LLM["Groq LLM"]
    end
    
    subgraph "Data Security"
        Encrypt -->|"AES-256"| EncField["customer_data_encrypted<br/>account_data_encrypted<br/>transaction_data_encrypted"]
        Encrypt -->|"SHA-256"| HashField["customer_id_search_hash<br/>account_id_search_hash<br/>txn_id_search_hash"]
        Encrypt -->|"Mask"| MaskField["pan_masked: XXXXX1234F"]
    end
```

### Banking Data Model

```mermaid
erDiagram
    BankingRecord ||--|| CustomerData : contains
    BankingRecord ||--|| AccountData : contains
    BankingRecord ||--|| TransactionData : contains
    
    CustomerData {
        string customer_id "CIN (Primary Key)"
        string name "Encrypted"
        string mobile "Encrypted"
        string email "Encrypted"
        string dob "Encrypted"
        string pan_number "Encrypted + Masked"
    }
    
    AccountData {
        string account_id "Hashed for Search"
        string customer_id "CIN Reference"
        string account_type "Savings/Current/FD/RD"
        float balance "Encrypted"
        string branch_code "Encrypted"
        string account_status "Active/Dormant/Closed"
        string last_updated "ISO Timestamp"
    }
    
    TransactionData {
        string txn_id "Hashed for Search"
        string account_id "Reference"
        string date "YYYY-MM-DD"
        float amount "Encrypted"
        string txn_type "Credit/Debit/Transfer"
    }
```

### LangGraph Orchestrator — Query Routing Engine

```mermaid
stateDiagram-v2
    [*] --> Classify: Incoming Query
    
    Classify --> Identity: "your name" / "who are you"
    Classify --> Conversational: "name" / "remember" / "earlier"
    Classify --> Factual: Default (data queries)
    
    Identity --> Memory: Skip RAG Context
    
    Conversational --> FetchContext: Needs records + memory
    
    Factual --> SemanticCache: Check similar queries
    SemanticCache --> CacheHIT: Similar query found
    SemanticCache --> FetchContext: Cache MISS
    
    CacheHIT --> [*]: Return cached response<br/>source: semantic_cache
    
    FetchContext --> Memory: RAG context from Qdrant
    
    Memory --> StoreCache: Generate LLM response
    StoreCache --> [*]: Return response<br/>source: memory
```

### Memory Architecture — Short-Term & Long-Term

```mermaid
graph TD
    subgraph "Session Lifecycle"
        Start["POST /session/start"] --> LoadLong["Load Long Memory<br/>(Previous Summaries)"]
        LoadLong --> InitShort["Initialize Short Memory<br/>(Redis Chat History)"]
        InitShort --> CeleryTask["Celery: Load Embeddings<br/>(Background)"]
    end

    subgraph "Query Flow (During Session)"
        Query["GET /query"] --> RedisCache{"Redis Cache<br/>(Exact Match)"}
        RedisCache -->|"HIT"| InstantReturn["⚡ Instant Return"]
        RedisCache -->|"MISS"| CB1{"🛡️ Circuit Breaker L1<br/>(BankingService)"}
        CB1 -->|"OPEN"| FastFail["❌ Fast Fail<br/>'Retry in 30s'"]
        CB1 -->|"CLOSED"| Orchestrator["LangGraph Orchestrator"]
        Orchestrator --> Classify["Classify Query"]
        Classify --> SemanticCache{"Semantic Cache<br/>(Vector Similarity)"}
        SemanticCache -->|"HIT"| CachedResponse["Return Cached"]
        SemanticCache -->|"MISS"| Qdrant["Qdrant Vector Search"]
        Qdrant --> ShortMemory["Short Memory<br/>(LangChain + History)"]
        ShortMemory --> CB2{"🛡️ Circuit Breaker L2<br/>(ShortMemory)"}
        CB2 -->|"OPEN"| LLMFail["❌ LLM Unavailable"]
        CB2 -->|"CLOSED"| Groq["🧠 Groq LLM"]
        Groq --> Response["✅ AI Response"]
        Response --> CacheStore["Store in Redis + Semantic Cache"]
    end

    subgraph "Session Close"
        Close["DELETE /session/close"] --> Summarize["LLM: Generate Summary"]
        Summarize --> ArchiveLong["Archive to Long Memory<br/>(MongoDB Encrypted)"]
        ArchiveLong --> ClearShort["Clear Short Memory<br/>(Redis)"]
        ClearShort --> OptionalDelete["Optional: Delete Embeddings<br/>(Qdrant)"]
    end
```

### Circuit Breaker — Dual Layer Protection

```mermaid
graph LR
    subgraph "Layer 1: BankingService"
        Request["API Request"] --> CB1{"Circuit Breaker<br/>failure_threshold=3<br/>timeout=30s"}
        CB1 -->|"CLOSED"| Pipeline["Full Pipeline<br/>Qdrant + Orchestrator + LLM"]
        CB1 -->|"OPEN"| Block1["⛔ Instant Error<br/>source: circuit_breaker"]
    end
    
    subgraph "Layer 2: ShortMemory"
        Pipeline --> CB2{"Circuit Breaker<br/>failure_threshold=3<br/>timeout=30s"}
        CB2 -->|"CLOSED"| LLM["Groq API Call"]
        CB2 -->|"OPEN"| Block2["⛔ LLM Unavailable"]
    end
    
    LLM -->|"Success"| OK["✅ Response"]
    LLM -->|"Fail x3"| Trip2["CB2 Trips OPEN"]
    Pipeline -->|"Fail x3"| Trip1["CB1 Trips OPEN"]
```

---

## 📋 Prerequisites

Before running the application, ensure you have:

*   **Python 3.10+**
*   **Docker & Docker Compose** (for Qdrant & Redis Stack)
*   **Redis Stack** (Local or Cloud — requires RediSearch module for Semantic Cache)
*   **MongoDB Connection** (Atlas or Local)
*   **Groq API Key** ([console.groq.com](https://console.groq.com))

