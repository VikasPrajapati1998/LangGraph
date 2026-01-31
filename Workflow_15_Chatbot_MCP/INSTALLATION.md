# 🚀 Installation Guide

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Ollama (for local LLM)

## Step-by-Step Installation

### 1. Install Python Dependencies

```bash
# Using requirements.txt
pip install -r requirements.txt

# Or install manually
pip install streamlit langgraph langchain-ollama langchain-core psycopg psycopg-binary
```

### 2. Setup PostgreSQL Database

#### Option A: Using createdb (Recommended)
```bash
createdb langgraph_memory
```

#### Option B: Using psql
```bash
psql -U postgres
CREATE DATABASE langgraph_memory;
\q
```

#### Option C: Using pgAdmin
1. Open pgAdmin
2. Right-click on "Databases"
3. Create → Database
4. Name: `langgraph_memory`
5. Save

### 3. Install and Setup Ollama

#### Install Ollama
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download
```

#### Pull Required Model
```bash
# Default model (small and fast)
ollama pull qwen2.5:0.5b

# Or use a larger model
ollama pull llama3:8b
ollama pull mistral:7b
```

#### Start Ollama (if not running)
```bash
ollama serve
```

### 4. Configure Database Connection

Edit `backend.py` line 11:

```python
# Replace with your credentials
DB_URI = "postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE"

# Examples:
# Local default:
DB_URI = "postgresql://postgres:password@localhost:5432/langgraph_memory"

# With special characters in password:
DB_URI = "postgresql://postgres:abcd%401234@localhost:5432/langgraph_memory"
# Note: @ symbol is encoded as %40

# Remote database:
DB_URI = "postgresql://user:pass@192.168.1.100:5432/langgraph_memory"
```

### 5. Verify Installation

```bash
# Test database connection
psql -U postgres -d langgraph_memory -c "SELECT 1;"

# Test Ollama
ollama list

# Test Python imports
python -c "import streamlit, langgraph, psycopg; print('✅ All imports successful')"
```

### 6. Run the Application

```bash
streamlit run frontend.py
```

The app should open in your browser at `http://localhost:8501`

## 🎯 Quick Start After Installation

1. **App opens** → You'll see an empty chat
2. **Type a message** → Press Enter
3. **Get response** → AI responds in real-time
4. **Try strategies** → Use sidebar dropdown
5. **View metrics** → Check sidebar stats

## 🔧 Troubleshooting Installation

### Issue: PostgreSQL Connection Error

```bash
# Check if PostgreSQL is running
pg_isready

# If not running, start it:
# macOS (Homebrew)
brew services start postgresql

# Linux (systemd)
sudo systemctl start postgresql

# Check connection
psql -U postgres -c "SELECT version();"
```

### Issue: Ollama Model Not Found

```bash
# List available models
ollama list

# If empty, pull a model
ollama pull qwen2.5:0.5b

# Test model
ollama run qwen2.5:0.5b "Hello"
```

### Issue: Python Import Errors

```bash
# Upgrade pip
pip install --upgrade pip

# Reinstall all packages
pip install --upgrade --force-reinstall -r requirements.txt

# Check installations
pip list | grep -E "streamlit|langgraph|psycopg"
```

### Issue: Port Already in Use

```bash
# Streamlit default port (8501) in use
streamlit run frontend.py --server.port 8502

# Or kill the existing process
lsof -ti:8501 | xargs kill
```

### Issue: Database Tables Not Created

The tables are created automatically on first run. If they're not:

```python
# In Python shell
from database import ChatDatabase
db = ChatDatabase("postgresql://postgres:password@localhost:5432/langgraph_memory")
db.setup_database()
```

### Issue: Permission Denied (Database)

```bash
# Grant permissions to user
psql -U postgres
GRANT ALL PRIVILEGES ON DATABASE langgraph_memory TO your_username;
\q
```

## 🌐 Production Deployment

### Using Environment Variables

Create a `.env` file:
```bash
DB_URI=postgresql://user:pass@localhost:5432/langgraph_memory
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=qwen2.5:0.5b
```

Update `backend.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()
DB_URI = os.getenv("DB_URI")
model = ChatOllama(
    model=os.getenv("MODEL_NAME", "qwen2.5:0.5b"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)
```

### Using Docker (Optional)

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: langgraph_memory
      POSTGRES_PASSWORD: your_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  app:
    build: .
    ports:
      - "8501:8501"
    depends_on:
      - postgres
    environment:
      DB_URI: postgresql://postgres:your_password@postgres:5432/langgraph_memory

volumes:
  pgdata:
```

## 📦 Alternative Installation Methods

### Using Conda

```bash
conda create -n chatbot python=3.10
conda activate chatbot
pip install -r requirements.txt
```

### Using Poetry

```bash
poetry init
poetry add streamlit langgraph langchain-ollama psycopg
poetry install
poetry run streamlit run frontend.py
```

### Using venv

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## ✅ Verification Checklist

After installation, verify:

- [ ] PostgreSQL is running: `pg_isready`
- [ ] Database exists: `psql -l | grep langgraph_memory`
- [ ] Ollama is running: `ollama list`
- [ ] Model is available: `ollama list | grep qwen`
- [ ] Python packages installed: `pip list | grep streamlit`
- [ ] App runs: `streamlit run frontend.py`
- [ ] Can send messages
- [ ] Messages are saved (refresh app, history persists)
- [ ] Can switch between chats
- [ ] Strategies work
- [ ] Summary generates (for 30+ messages)

## 🎓 Post-Installation

### Recommended Next Steps

1. **Test basic chat** - Send a few messages
2. **Try strategies** - Switch between different modes
3. **Create multiple chats** - Test conversation management
4. **Test summarization** - Chat 30+ times
5. **Check database** - Verify data is being saved

### Database Inspection

```bash
# View all tables
psql -U postgres -d langgraph_memory -c "\dt"

# Check chat threads
psql -U postgres -d langgraph_memory -c "SELECT * FROM chat_threads;"

# Check messages
psql -U postgres -d langgraph_memory -c "SELECT COUNT(*) FROM chat_messages;"

# Check summaries
psql -U postgres -d langgraph_memory -c "SELECT * FROM conversation_summaries;"
```

## 🔐 Security Recommendations

### For Development:
- ✅ Use default local settings
- ✅ Simple passwords are fine
- ✅ Direct connection strings OK

### For Production:
- 🔒 Use environment variables
- 🔒 Strong database passwords
- 🔒 SSL/TLS connections
- 🔒 Firewall rules
- 🔒 Regular backups
- 🔒 User authentication

## 📊 Resource Requirements

### Minimum:
- CPU: 2 cores
- RAM: 4 GB
- Disk: 2 GB free
- PostgreSQL: 100 MB

### Recommended:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 10 GB free
- PostgreSQL: 500 MB

### For Large Scale:
- CPU: 8+ cores
- RAM: 16+ GB
- Disk: 50+ GB SSD
- PostgreSQL: 5+ GB

## 🎯 Installation Complete!

If all steps completed successfully, you should have:

✅ PostgreSQL database running
✅ Ollama with model installed
✅ Python environment with all packages
✅ Application running on http://localhost:8501
✅ Able to chat and save conversations

**You're ready to start chatting! 🎉**

---

Need help? Check README.md or QUICK_REFERENCE.md
