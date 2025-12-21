# 🚀 RepoWise - Knowledge Graph Repository Analysis System

> **An AI-powered repository analysis system combining RAG, Knowledge Graphs, and LLMs for intelligent code insights.**

A comprehensive platform that integrates vector search (ChromaDB), knowledge graphs (Neo4j), and hybrid RAG to provide deep insights about software repositories. Features include commit tracking, code structure analysis, contribution metrics, and intelligent query routing.

**BBM479 Graduation Project - Hacettepe University Computer Engineering**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.121.0-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://www.python.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-2025.10-008CC1?style=flat&logo=neo4j)](https://neo4j.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4.22-FF6B6B?style=flat)](https://www.trychroma.com/)

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

### 🔜 Phase 4 & 5 (Upcoming)

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
**Supervisor:** [Supervisor Name]  
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
**API Endpoints:** 29  
**Services:** 12  
**Database:** Neo4j (Graph) + ChromaDB (Vector)  
**Test Coverage:** Integration tests included  
**Documentation:** Comprehensive guides + Swagger

---

**Current Version:** 0.3.0 (Phase 3 Complete)  
**Status:** ✅ Production Ready  
**Last Updated:** December 22, 2024

---

<p align="center">
  <strong>Built with ❤️ by Hacettepe University Computer Engineering Students</strong>
</p>

<p align="center">
  <sub>Combining the power of RAG, Knowledge Graphs, and LLMs for intelligent code analysis</sub>
</p>
