# 🚀 RepoWise - AI-Powered Repository Analysis with AutoFix

> **An AI-powered repository analysis system combining RAG, Knowledge Graphs, and LLMs for intelligent code insights.**

A comprehensive platform that integrates vector search (ChromaDB), knowledge graphs (Neo4j), and hybrid RAG to provide deep insights about software repositories. Features include commit tracking, code structure analysis, contribution metrics, and intelligent query routing.

**BBM479 Graduation Project - Hacettepe University Computer Engineering**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.121.0-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://www.python.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-2025.10-008CC1?style=flat&logo=neo4j)](https://neo4j.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4.22-FF6B6B?style=flat)](https://www.trychroma.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker)](https://www.docker.com/)
[![AutoCodeRover](https://img.shields.io/badge/AutoFix-Integrated-FF6F00?style=flat&logo=robot)](https://github.com/nus-apr/auto-code-rover)

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Technology Stack](#-technology-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [Usage Guide](#-usage-guide)
- [Development Roadmap](#-development-roadmap)
- [Team](#-team)

---

## ✨ Features

### ✅ Phase 1 - Foundation (COMPLETE)

- 🔍 **GitHub/GitLab Integration**: Multi-platform repository support
- 🤖 **LLM-Powered Chat**: OpenAI GPT with intelligent fallback
- 🎯 **Smart Query Detection**: Automatic question type recognition
- 📚 **Source Attribution**: Shows data sources for each response
- 💯 **Confidence Scoring**: Response reliability indicators

### ✅ Phase 2 - RAG Pipeline (COMPLETE)

- 🗂️ **ChromaDB Vector Store**: Semantic code search with 384-dim embeddings
- 🔎 **Intelligent Indexing**: Smart code chunking with metadata
- 📖 **Context-Aware Responses**: RAG-powered Q&A generation
- ⚡ **Fast Search**: Sub-second semantic search
- 🎨 **Multi-Language Support**: 14 programming languages

### ✅ Phase 3 - Knowledge Graph (COMPLETE)

- 🕸️ **Neo4j Graph Database**: Complete repository structure mapping
- 📊 **Commit Tracking**: File-level changes with diff data (958 additions, 762 deletions)
- 👥 **Author Analytics**: Contribution metrics and code ownership
- 🔥 **Hot Spots Detection**: Most frequently modified files
- 🔗 **Hybrid RAG**: Vector + Graph search with intent-based routing (~80% accuracy)
- 📈 **Analytics API**: 7 endpoints for repository insights

### ✅ Phase 4 - Multi-Agent Systems & AutoFix (COMPLETE) 🆕

**AutoFix - Automated Code Fixing:**
- 🤖 AutoCodeRover integration with custom Docker build (12.8GB)
- 🎨 Frontend component with 640+ lines of React code
- ⚡ 4 API endpoints: health, submit, status, sync-wait
- 🎯 Natural language issue descriptions → AI-generated patches
- 🔄 Real-time status polling with progress indicators
- 🎛️ Model selection: GPT-4o, GPT-4o-mini, GPT-4 Turbo
- 🌡️ Temperature control (0.0-1.0)
- 📥 Patch preview with syntax highlighting

**Docker Infrastructure:**
- 📦 docker-compose.yml with 3 services
- 🔧 AutoCodeRover service (Miniconda3-based)
- 🗄️ Neo4j 5.13.0 with APOC plugins
- 🔢 ChromaDB with persistent storage
- 💾 Resource management (4 CPU, 8GB RAM)

**Documentation:**
- 📄 End of Term Development Report (15,000+ LOC documented)
- 📊 14-slide professional presentation
- 📖 AutoFix setup guides and API documentation

### 📅 Phase 5 - Evaluation & Production (PLANNED)

- Multi-Agent System (AutoCodeRover, CodexGraph)
- Advanced Code Analysis
- Comprehensive Evaluation Framework

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         RepoWise System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────┐      ┌──────────────┐      ┌─────────────┐     │
│  │   React    │ ───> │   FastAPI    │ ───> │   Services  │     │
│  │  Frontend  │      │   Backend    │      │    Layer    │     │
│  └────────────┘      └──────────────┘      └─────────────┘     │
│                                                    │             │
│                           ┌────────────────────────┼─────────┐  │
│                           │                        │         │  │
│                    ┌──────▼──────┐        ┌───────▼──────┐  │  │
│                    │  Vector DB  │        │   Graph DB   │  │  │
│                    │  ChromaDB   │        │    Neo4j     │  │  │
│                    │  (Semantic) │        │  (Structure) │  │  │
│                    └─────────────┘        └──────────────┘  │  │
│                                                              │  │
│                           ┌──────────────────────────────────┘  │
│                           │                                     │
│                    ┌──────▼───────┐                            │
│                    │  Hybrid RAG  │                            │
│                    │ Query Router │                            │
│                    └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User Query** → Intent Detection
2. **Intent Routing**:
   - Structure/Dependency/History → **Neo4j Graph**
   - Implementation/Usage → **ChromaDB Vector**
3. **Result Fusion** → LLM Enhancement → Response

---

## 🛠️ Technology Stack

### Backend
- **API**: FastAPI, Uvicorn, Pydantic
- **Graph DB**: Neo4j 2025.10.1
- **Vector DB**: ChromaDB 0.4.22
- **Git Integration**: PyGithub, python-gitlab
- **AI/ML**: LangChain, sentence-transformers, OpenAI GPT

### Frontend
- **Framework**: React 18+, Vite
- **Styling**: Tailwind CSS
- **State**: React Hooks

### Infrastructure
- **Python**: 3.11/3.12
- **Node.js**: 18+
- **Database**: Neo4j, ChromaDB (persistent storage)

---

## 📋 Prerequisites

### Required Software
- **Python 3.11 or 3.12** (NOT 3.13 - compatibility issues)
- **Node.js 18+** and npm
- **Neo4j Desktop** or **Neo4j Server** (for Knowledge Graph)
- **Git**

### API Keys
- **GitHub Token** (Required - Free) - for GitHub repositories
- **GitLab Token** (Required - Free) - for GitLab repositories
- **OpenAI API Key** (Optional - $5-10) - for LLM responses
- **Groq API Key** (Optional - Free) - alternative LLM provider

---

## 🚀 Installation


### Method 1: Docker Compose (Recommended for Production)

This method automatically sets up AutoCodeRover, Neo4j, and ChromaDB.

#### Step 1: Clone and Setup Environment

```bash
# Clone repository
git clone https://github.com/memo-13-byte/RepoWise.git
cd RepoWise

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# Required: OPENAI_API_KEY, GITHUB_TOKEN, GITLAB_TOKEN
```

#### Step 2: Pull Docker Images

```bash
# Pull AutoCodeRover image (12.8 GB - may take 10-30 min)
docker pull ghcr.io/nus-apr/auto-code-rover:v0.1.0

# Verify image
docker images | grep auto-code-rover
```

#### Step 3: Start All Services

```bash
# Start AutoCodeRover, Neo4j, ChromaDB
docker-compose up -d

# Check status
docker-compose ps

# Expected output:
# repowise-autocoderover  Up (healthy)
# repowise-neo4j          Up
# repowise-chromadb       Up
```

#### Step 4: Start Backend

```bash
cd Repowise-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate    # Linux/Mac

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

#### Step 5: Start Frontend

```bash
cd repowise-frontend
npm install
npm run dev
```

Access: http://localhost:5173

### Method 2: Manual Setup (Development)

Follow the existing installation steps for manual setup without Docker Compose.


### 1. Backend Setup

```powershell
# Clone repository
git clone https://github.com/memo-13-byte/RepoWise.git
cd RepoWise/Repowise-backend

# Create virtual environment (Python 3.11/3.12 ONLY!)
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# If you get "Execution Policy" error:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Neo4j Setup

**Option A: Neo4j Desktop (Recommended for Development)**
1. Download: https://neo4j.com/download/
2. Install and create new project
3. Create new database (Graph DBMS)
4. Set password (e.g., `password`)
5. Start database
6. Note connection details:
   - URI: `bolt://localhost:7687`
   - Username: `neo4j`
   - Password: `password`

**Option B: Neo4j Server (For Production)**
```bash
# Docker
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    neo4j:latest
```

### 3. Configuration

Create `.env` file in `Repowise-backend/`:

```env
# GitHub Integration (Required)
GITHUB_TOKEN=ghp_your_github_token_here

# GitLab Integration (Required)
GITLAB_TOKEN=glpat_your_gitlab_token_here

# LLM Services (Optional)
OPENAI_API_KEY=sk-proj-your_openai_key_here
GROQ_API_KEY=gsk_your_groq_key_here

# Neo4j Configuration (Required for Phase 3)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# ChromaDB (Auto-configured)
CHROMA_PERSIST_DIRECTORY=./chroma_db
```

### 4. Get API Keys

**GitHub Token:**
1. Go to: https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `read:user`
4. Copy token (starts with `ghp_`)

**GitLab Token:**
1. Go to: https://gitlab.com/-/user_settings/personal_access_tokens
2. Add new token
3. Select scopes: `read_api`, `read_repository`
4. Copy token (starts with `glpat-`)

**OpenAI Key (Optional):**
1. Go to: https://platform.openai.com/api-keys
2. Create new secret key
3. Copy key (starts with `sk-proj-`)

### 5. Frontend Setup

```powershell
# Open new terminal
cd RepoWise/repowise-frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

---

## 🏃 Running the Application

### Start Backend (Terminal 1)

```powershell
cd Repowise-backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**Backend will run at:**
- API: http://127.0.0.1:8000
- Swagger Docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### Start Frontend (Terminal 2)

```powershell
cd repowise-frontend
npm run dev
```

**Frontend will run at:**
- App: http://localhost:5173

### Verify Neo4j (Optional)

- Neo4j Browser: http://localhost:7474
- Login with credentials from `.env`
- Run: `MATCH (n) RETURN n LIMIT 25`

---

## 📚 API Documentation

### 29 Total Endpoints

#### Core Endpoints (2)
```http
GET  /              # Welcome message
GET  /health        # System health check
```

#### Chat Endpoints (7)
```http
POST /api/chat/send                    # Send message
GET  /api/chat/conversations           # List conversations
GET  /api/chat/conversations/{id}      # Get conversation
DELETE /api/chat/conversations/{id}    # Delete conversation
GET  /api/chat/status                  # Chat status
POST /api/chat/clear                   # Clear history
GET  /api/chat/config                  # Chat configuration
```

#### Repository Endpoints (6)
```http
POST /api/repository/analyze           # Analyze repository
GET  /api/repository/                  # List repositories
GET  /api/repository/{name}/stats      # Repository statistics
GET  /api/repository/{repo_name}/files # List files
POST /api/repository/index             # Index repository
GET  /api/repository/index/status      # Index status
```

#### RAG Endpoints (7)
```http
POST   /api/rag/index                  # Index for semantic search
POST   /api/rag/search                 # Semantic code search
POST   /api/rag/answer                 # RAG-powered Q&A
GET    /api/rag/collections            # List collections
GET    /api/rag/collections/{name}     # Collection stats
DELETE /api/rag/collections/{name}     # Delete collection
GET    /api/rag/health                 # RAG health check
```

#### Analytics Endpoints (7) - NEW!
```http
GET /api/repository/analytics/stats              # Repository statistics
GET /api/repository/analytics/contributors       # Top contributors
GET /api/repository/analytics/hot-spots          # Most modified files
GET /api/repository/analytics/file-history       # File change history
GET /api/repository/analytics/code-owners        # File ownership
GET /api/repository/analytics/commit-diff        # Commit diff viewer
GET /api/repository/analytics/compare-commits    # Compare commits
```

### Example Usage

**Analyze Repository:**
```bash
curl -X POST "http://localhost:8000/api/repository/analyze" \
  -H "Content-Type: application/json" \
  -d '{"repository_url": "https://github.com/psf/requests"}'
```

**Index with Enhanced Tracking:**
```bash
curl -X POST "http://localhost:8000/api/repository/index" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/psf/requests",
    "max_commits": 50,
    "include_file_tracking": true,
    "include_diffs": true
  }'
```

**Get Repository Statistics:**
```bash
curl "http://localhost:8000/api/repository/analytics/stats?repo_name=psf/requests"
```

**Response Example:**
```json
{
  "total_commits": 50,
  "authors": 19,
  "files": 37,
  "classes": 86,
  "functions": 102,
  "total_additions": 958,
  "total_deletions": 762,
  "languages": {
    "python": 9,
    "rst": 7,
    "yml": 4
  }
}
```

Full documentation: **http://127.0.0.1:8000/docs**

---

## 📖 Usage Guide

### 1. Index a Repository

```python
# Via API
POST /api/repository/index
{
  "repo_url": "https://github.com/psf/requests",
  "max_commits": 50,
  "include_file_tracking": true,
  "include_diffs": true
}

# Via Frontend
1. Enter repository URL
2. Click "Index Repository"
3. Wait for completion
```

### 2. Query Repository

**Structure Questions (→ Graph):**
```
"How is the code organized?"
"What modules depend on sessions.py?"
"Show me the repository structure"
```

**History Questions (→ Graph):**
```
"Who are the main contributors?"
"Who modified the authentication code recently?"
"What files did John commit?"
```

**Implementation Questions (→ Vector):**
```
"How does the session class work?"
"What does this library do?"
"Explain the authentication mechanism"
```


#### AutoFix Endpoints (4 endpoints) 🆕

Base path: `/api/v1/autofix`

| Method | Endpoint | Description | Request | Response |
|--------|----------|-------------|---------|----------|
| GET | `/health` | Check service health | - | `{status: "healthy"}` |
| POST | `/submit` | Submit fixing task | `{repo_url, issue_description, model, temperature}` | `{task_id, status}` |
| GET | `/status/{task_id}` | Check task status | - | `{status, progress, patch_url}` |
| GET | `/sync-wait/{task_id}` | Wait for completion | - | `{status, patch}` |

**Example - Submit AutoFix Task:**

```bash
POST /api/v1/autofix/submit
Content-Type: application/json

{
  "repo_url": "https://github.com/psf/requests",
  "issue_description": "Add type hints to Session class in requests/sessions.py",
  "model": "gpt-4o-mini",
  "temperature": 0.2
}

# Response:
{
  "task_id": "fix_abc123",
  "status": "submitted",
  "estimated_time": "30-120 seconds"
}
```

**Check Status:**

```bash
GET /api/v1/autofix/status/fix_abc123

# Response (Completed):
{
  "task_id": "fix_abc123",
  "status": "completed",
  "patch_url": "/outputs/fix_abc123.patch",
  "files_modified": 1,
  "lines_added": 25
}
```

**Download & Apply Patch:**

```bash
# Download
curl http://localhost:8080/outputs/fix_abc123.patch > fix.patch

# Apply
git apply fix.patch
```



### 3. Use AutoFix (Automated Code Fixing) 🆕

**Via Frontend:**

1. Navigate to **AutoFix** tab
2. Enter repository URL: `https://github.com/psf/requests`
3. Describe the issue:
   ```
   Add type hints to the Session class in requests/sessions.py.
   Include hints for __init__, request, get, post methods.
   Use typing module (Dict, List, Optional).
   ```
4. Select model:
   - **GPT-4o-mini**: Fast, cost-effective (10-30s)
   - **GPT-4o**: Balanced (30-90s)
   - **GPT-4 Turbo**: Best quality (60-180s)
5. Adjust temperature:
   - **0.0-0.2**: Deterministic fixes
   - **0.3-0.5**: Balanced
   - **0.6-1.0**: Creative solutions
6. Click "Generate Fix"
7. Wait for completion (10s - 10min)
8. Preview patch with syntax highlighting
9. Download and apply

**Via API:**

```bash
# Submit task
curl -X POST http://localhost:8080/api/v1/autofix/submit   -H "Content-Type: application/json"   -d '{
    "repo_url": "https://github.com/psf/requests",
    "issue_description": "Add type hints to Session class",
    "model": "gpt-4o-mini",
    "temperature": 0.2
  }'

# Check status
curl http://localhost:8080/api/v1/autofix/status/{task_id}

# Download patch
curl http://localhost:8080/outputs/{task_id}.patch > fix.patch

# Apply
git apply fix.patch
```

**Best Practices:**

✅ **DO:**
- Be specific about files to modify
- Provide examples of desired output
- Use appropriate model for complexity
- Test patches before committing
- Review patches carefully

❌ **DON'T:**
- Request major architectural changes
- Provide vague descriptions
- Apply without reviewing
- Use high temperature for critical fixes


### 3. View Analytics

```bash
# Top Contributors
GET /api/repository/analytics/contributors?repo_name=psf/requests

# Hot Spots (most modified files)
GET /api/repository/analytics/hot-spots?repo_name=psf/requests

# File History
GET /api/repository/analytics/file-history?file_path=requests/sessions.py

# Compare Commits
GET /api/repository/analytics/compare-commits?from=abc123&to=def456
```

---

## 🗺️ Development Roadmap

### ✅ Phase 1: Foundation (Weeks 1-8) - COMPLETE
- ✅ FastAPI backend + React frontend
- ✅ GitHub/GitLab API integration
- ✅ LLM service with Groq/OpenAI
- ✅ Smart chat system
- ✅ Full-stack integration

### ✅ Phase 2: RAG Pipeline (Weeks 8-11) - COMPLETE
- ✅ ChromaDB vector database
- ✅ sentence-transformers embeddings
- ✅ Semantic code search
- ✅ Context-aware RAG responses
- ✅ 7 RAG API endpoints

### ✅ Phase 3: Knowledge Graph (Weeks 11-13) - COMPLETE
- ✅ Neo4j graph database integration
- ✅ Enhanced commit tracking with diff data
- ✅ File-level change tracking (109 files, 958 additions, 762 deletions)
- ✅ Code structure mapping (Files → Classes → Functions)
- ✅ Hybrid RAG (Vector + Graph) with intent routing
- ✅ 7 Analytics API endpoints
- ✅ Author contribution metrics
- ✅ Hot spots detection

### 🔄 Phase 4: Multi-Agent (Weeks 11-13) - IN PROGRESS
- AutoCodeRover integration
- CodexGraph integration
- Agent orchestration
- Performance comparison

### 📅 Phase 5: Evaluation (Weeks 13-24) - PLANNED
- Question dataset (80-100)
- User study (10-15 developers)
- Academic paper
- Production deployment

---

## 📁 Project Structure

```
RepoWise/

│
├── docker/                           # Docker configurations
│   └── autofix/
│       ├── auto-code-rover/          # AutoCodeRover source (cleaned)
│       ├── Dockerfile                # Custom ACR build
│       ├── wrapper_api.py            # FastAPI wrapper
│       └── .env.example             # ACR environment
│
├── docs/                             # Documentation
│   ├── AUTOFIX_SETUP.md             # AutoFix setup guide
│   ├── API.md                       # API documentation  
│   └── EOTDR.docx                   # End of Term Report
├── Repowise-backend/
│   ├── app/
│   │   ├── api/                      # API Endpoints
│   │   │   ├── chat.py              # Chat endpoints (7)
│   │   │   ├── repository.py        # Repo + Analytics (13)
│   │   │   └── rag_endpoints.py     # RAG endpoints (7)
│   │   ├── core/
│   │   │   └── config.py            # Configuration
│   │   ├── services/
│   │   │   ├── chromadb_service.py          # Vector DB
│   │   │   ├── rag_service.py               # RAG Pipeline
│   │   │   ├── neo4j_service_enhanced.py    # Graph DB
│   │   │   ├── commit_indexing_service_enhanced.py  # Commit tracking
│   │   │   ├── hybrid_rag_extension.py      # Hybrid RAG
│   │   │   ├── github_service.py            # GitHub API
│   │   │   ├── gitlab_service.py            # GitLab API
│   │   │   ├── llm_service.py               # LLM integration
│   │   │   ├── embedding_service.py         # Embeddings
│   │   │   └── document_processor.py        # Code chunking
│   │   └── main.py                          # FastAPI app
│   ├── .env                                  # Environment variables
│   ├── requirements.txt                      # Python dependencies
│   └── chroma_db/                           # ChromaDB storage
│
├── repowise-frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx       # Chat interface
│   │   │   └── RepositorySelector.jsx
│   │   ├── services/
│   │   │   └── api.js               # API client
│   │   └── App.jsx                  # Main app
│   └── package.json                 # npm dependencies
│
└── README.md                        # This file
```

---

## 🛠️ Troubleshooting

### Common Issues

**1. Neo4j Connection Error**
```
Error: Could not connect to Neo4j
Solution:
- Check Neo4j is running (Desktop or Docker)
- Verify NEO4J_URI in .env
- Check credentials (NEO4J_USER, NEO4J_PASSWORD)
- Test connection: http://localhost:7474
```

**2. Python Version Error**
```
Error: Python 3.13 incompatible
Solution:
- Use Python 3.11 or 3.12
- Check: python --version
- Create new venv: py -3.11 -m venv .venv
```


**3. Docker AutoCodeRover Issues**

```
Error: AutoCodeRover container unhealthy
```

**Solutions:**

```bash
# Check container status
docker-compose ps

# View logs
docker logs repowise-autocoderover

# Restart service
docker-compose restart autocoderover

# Rebuild if needed
docker-compose build --no-cache autocoderover
docker-compose up -d
```

**4. AutoFix Timeout**

```
Error: Task timeout after 10 minutes
```

**Solutions:**

```bash
# Increase timeout in docker-compose.yml
# environment:
#   - TASK_TIMEOUT=1800  # 30 minutes

# Restart services
docker-compose down && docker-compose up -d

# Or target specific files in issue description
```

**5. Out of Memory (AutoFix)**

```
Error: Container killed due to OOM
```

**Solutions:**

```bash
# Increase Docker Desktop memory
# Settings → Resources → Memory → 16GB

# Adjust limits in docker-compose.yml
# deploy:
#   resources:
#     limits:
#       memory: 12G
```


**3. ChromaDB Error**
```
Error: Metadata validation failed
Solution:
- Delete chroma_db/ folder
- Restart backend
- Re-index repository
```

**4. API Key Issues**
```
Error: GitHub rate limit exceeded
Solution:
- Add GITHUB_TOKEN to .env
- Get token: https://github.com/settings/tokens
- Restart backend
```

**5. Module Not Found**
```
Error: ModuleNotFoundError
Solution:
- Activate venv: .\.venv\Scripts\Activate.ps1
- Install: pip install -r requirements.txt
```

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m "feat: add amazing feature"`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

**Commit Message Convention:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Tests
- `chore`: Maintenance

---

## 👥 Team

**BBM479 Graduation Project - Hacettepe University**

- **Mehmet Oğuz Kocadere** - Backend, Knowledge Graph, Frontend, UI/UX
- **Yusuf Emir Cömert** - LLM Integration, RAG Pipeline, GitLab Support
- **Südenaz Yazıcı** - RAG Pipeline, LLM, Evaluation
- **Şamil Giray Karaçay** - Knowledge Graph, Neo4j, RAG
- **İbrahim Baran Yıldız** - Multi-Agent Integration

**Course:** BBM479 - Graduation Project  
**Supervisor:** Asst. Prof. Tuğba Gürgen Erdoğan  
**University:** Hacettepe University - Computer Engineering  
**Year:** 2024-2025

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 📞 Contact

**Project Repository:** https://github.com/memo-13-byte/RepoWise  
**Issues:** https://github.com/memo-13-byte/RepoWise/issues  
**Email:** canmehmetoguz@gmail.com

---

## 🙏 Acknowledgments

Special thanks to:
- **FastAPI** - Modern web framework
- **Neo4j** - Graph database platform
- **ChromaDB** - Vector database
- **LangChain** - LLM framework
- **PyGithub** - GitHub API wrapper
- **Hacettepe University** - Academic support

---

## 📊 Project Statistics

**Lines of Code:** ~15,000+  
**API Endpoints:** 31  
**Services:** 15  
**Database:** Neo4j (Graph) + ChromaDB (Vector)  
**Test Coverage:** Integration tests included  
**Documentation:** Comprehensive guides + Swagger

---

**Current Version:** 1.0.0 (Phase 4 Complete)  
**Status:** ✅ Production Ready  
**Last Updated:** February 22, 2025

---

<p align="center">
  <strong>Built with ❤️ by Hacettepe University Computer Engineering Students</strong>
</p>

<p align="center">
  <sub>Combining the power of RAG, Knowledge Graphs, and LLMs for intelligent code analysis</sub>
</p>