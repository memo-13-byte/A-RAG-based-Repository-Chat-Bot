# 🚀 RepoWise - RAG-Based Repository Chatbot

> **A web-based RAG-powered chatbot that provides intelligent insights about software repositories using LLMs.**

Combines retrieval techniques with knowledge graphs to answer developer queries about code, documentation, issues, and commits. Features LLM-powered responses with fallback mechanisms and comprehensive repository analysis.

**BBM479 Graduation Project - Hacettepe University Computer Engineering**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.121.0-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-0.1.0-121212?style=flat)](https://www.langchain.com/)

---

## 📋 Table of Contents

- [Features](#-features)
- [Demo](#-demo)
- [Technology Stack](#-technology-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [Project Structure](#-project-structure)
- [Usage Guide](#-usage-guide)
- [Development Roadmap](#-development-roadmap)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [Team](#-team)

---

## ✨ Features

### ✅ Phase 1 - Complete

- 🔍 **Repository Analysis**: GitHub metadata, statistics, and content
- 🤖 **LLM-Powered Responses**: OpenAI GPT or Anthropic Claude
- 🎯 **Smart Query Detection**: Automatic question type recognition
- 🔄 **Fallback Mechanism**: Rule-based responses when LLM unavailable
- 📚 **Source Attribution**: Shows data sources for each response
- 💯 **Confidence Scoring**: Response reliability indicators
- 📖 **Interactive API Docs**: Swagger/ReDoc interface
- 🎨 **Modern UI**: Responsive design with Tailwind CSS

### 🔜 Phase 2-5 (Upcoming)

- RAG Pipeline with ChromaDB
- Neo4j Knowledge Graph
- Multi-Agent System
- Advanced Code Analysis
- Comprehensive Evaluation

---

## 🛠️ Technology Stack

**Backend**: FastAPI, Python 3.11+, PyGithub, LangChain  
**Frontend**: React 18+, Vite, Tailwind CSS  
**AI/ML**: OpenAI GPT, LangChain, tiktoken

---

## 📋 Prerequisites

### Required
- **Python 3.11 or 3.12** (NOT 3.13)
- **Node.js 18+** and npm
- **Git**

### API Keys
- **GitHub Token** (Required - Free)
- **OpenAI API Key** (Optional - $5-10 recommended)

---

## 🚀 Installation

### 1. Backend Setup

```powershell
# Clone and navigate
git clone https://github.com/your-username/RepoWise.git
cd RepoWise/Repowise-backend

# Create virtual environment (Python 3.11/3.12!)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
notepad .env
```

**Add to .env:**
```env
GITHUB_TOKEN=ghp_your_token_here
OPENAI_API_KEY=sk-proj-your_key_here  # Optional
```

**Start backend:**
```powershell
uvicorn app.main:app --reload
```

Visit: http://127.0.0.1:8000 (API) and http://127.0.0.1:8000/docs (Swagger)

---

### 2. Frontend Setup

```powershell
# New terminal
cd RepoWise/repowise-frontend

# Install and run
npm install
npm run dev
```

Visit: http://localhost:5173

---

## 🔑 Configuration

### GitHub Token

1. Go to: https://github.com/settings/tokens
2. Create token (classic)
3. Select scopes: `repo`, `read:user`
4. Copy token (starts with `ghp_`)
5. Add to `.env`: `GITHUB_TOKEN=ghp_...`

### OpenAI API Key (Optional)

1. Go to: https://platform.openai.com/api-keys
2. Create new key
3. Add to `.env`: `OPENAI_API_KEY=sk-proj-...`

**Note**: System works without OpenAI using rule-based fallback!

---

## 🏃 Running the Application

**Terminal 1 - Backend:**
```powershell
cd Repowise-backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```powershell
cd repowise-frontend
npm run dev
```

**Access:**
- Frontend: http://localhost:5173
- Backend: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs

---

## 📚 API Documentation

### Analyze Repository
```http
POST /api/repository/analyze
{
  "repository_url": "https://github.com/langchain-ai/langchain"
}
```

### Send Chat Message
```http
POST /api/chat/send
{
  "message": "What does this repository do?",
  "repository_url": "https://github.com/langchain-ai/langchain",
  "use_llm": true
}
```

Full docs: http://127.0.0.1:8000/docs

---

## 📁 Project Structure

```
RepoWise/
├── Repowise-backend/
│   ├── app/
│   │   ├── api/              # Endpoints
│   │   ├── core/             # Configuration
│   │   ├── services/         # Business logic
│   │   └── main.py           # FastAPI app
│   ├── .env                  # Environment variables
│   └── requirements.txt      # Dependencies
│
└── repowise-frontend/
    ├── src/
    │   ├── components/       # React components
    │   ├── services/         # API client
    │   └── App.jsx           # Main app
    └── package.json          # npm dependencies
```

---

## 📖 Usage Guide

### Add Repository
1. Enter GitHub URL: `https://github.com/owner/repo`
2. Click search 🔍
3. Wait for "Repository analyzed successfully" ✅

### Ask Questions
```
"What does this repository do?"
"How many stars does it have?"
"What language is it written in?"
"Who are the main contributors?"
"Show me recent commits"
```

### View Responses
- 💬 Detailed answer
- 📚 Sources (README.md, GitHub API)
- 💯 Confidence score (0-100%)

---

## 🗺️ Development Roadmap

### ✅ Phase 1: Foundation (Weeks 1-8) - COMPLETE
- FastAPI backend + React frontend
- GitHub API integration
- LLM service with fallback
- Smart chat system
- Full-stack integration

### 🔄 Phase 2: RAG Pipeline (Weeks 8-11)
- ChromaDB vector database
- CodeBERT embeddings
- Semantic code search
- Context-aware responses

### 📅 Phase 3: Knowledge Graph (Weeks 11-13)
- Neo4j graph database
- Code structure mapping
- Dependency analysis
- Graph visualization

### 📅 Phase 4: Multi-Agent (Weeks 11-13) (Parallely)
- AutoCodeRover, CodexGraph
- Agent orchestration
- Performance comparison

### 📅 Phase 5: Evaluation and Refactoring (Weeks 13-24)
- Question dataset (80-100)
- User study (10-15 developers)
- Academic paper

---

## 🐛 Troubleshooting

**Python not found?**
```powershell
py --version
py -3.11 -m venv .venv
```

**Module not found?**
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**.env not loaded?**
```powershell
# Create .env in Repowise-backend/
notepad .env
# Add: GITHUB_TOKEN=ghp_...
```

**OpenAI quota exceeded?**
- Add credit OR set `use_llm: false` for fallback

**More help**: See full troubleshooting section above

---

## 🤝 Contributing

1. Fork repository
2. Create branch: `git checkout -b feature/name`
3. Commit: `git commit -m "feat: description"`
4. Push: `git push origin feature/name`
5. Open Pull Request

**Commit types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

---

## 👥 Team

**BBM479 Graduation Project - Hacettepe University**

- Mehmet Oğuz Kocadere - Backend, Frontend, UI/UX
- Yusuf Emir Cömert - LLM, RAG, Agent Integration
- Sûdenaz Yazıcı - LLM, RAG, Evaluation
- Şamil Giray Karaçay - Knowledge Graph, LLM, RAG
- İbrahim Baran Yıldız - Agent Integration

**Course**: BBM479 - Graduation Project  
**Year**: 2024-2025

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

## 📞 Contact

**Issues**: https://github.com/your-username/RepoWise/issues  
**Email**: canmehmetoguz@gmail.com

---

## 🙏 Acknowledgments

- LangChain, FastAPI, React, Tailwind CSS
- PyGithub, Hacettepe University

---

**Version**: 0.1.0 (Phase 1 Complete)  
**Status**: ✅ Production Ready  
**Last Updated**: November 14, 2025

---

<p align="center">
  <strong>Built with ❤️ by Hacettepe University CS Students</strong>
</p>
