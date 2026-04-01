# BlogForge — Frontend

React + TypeScript + Vite frontend for the BlogForge AI blog generation system.

---

## Prerequisites

- Node.js 18+ — verify with `node -v`
- FastAPI backend running on `http://localhost:8000`

---

## Project Structure

```
Frontend/
├── public/
│   └── quill.svg               # Favicon
├── src/
│   ├── components/
│   │   ├── AnimatedBackground.tsx  # Floating orbs + grid canvas
│   │   ├── ApprovalPanel.tsx       # Approve / reject with reason
│   │   ├── BlogCard.tsx            # Single blog card in list
│   │   ├── BlogList.tsx            # Filterable, date-grouped list
│   │   ├── BlogViewer.tsx          # Full detail view + live poll
│   │   ├── DownloadMenu.tsx        # MD / PDF / DOCX download
│   │   ├── EditModal.tsx           # Rename + content editor
│   │   ├── GenerateForm.tsx        # Topic input + submit
│   │   ├── StatsBar.tsx            # Live counts dashboard
│   │   └── StatusBadge.tsx         # Coloured status pill
│   ├── hooks/
│   │   ├── usePolling.ts           # Auto-refresh while workflow runs
│   │   └── useDownload.ts          # Download logic (MD/PDF/DOCX)
│   ├── api.ts                      # All fetch calls to FastAPI
│   ├── types.ts                    # Shared TypeScript types
│   ├── App.tsx                     # Root layout + navigation
│   ├── main.tsx                    # React entry point
│   └── index.css                   # Global styles + CSS variables
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
└── package.json
```

---

## Setup & Run

### Step 1 — Install dependencies

```bash
cd Frontend
npm install
```

### Step 2 — Start FastAPI backend (separate terminal)

```bash
# from your project root
uvicorn main:app --reload --port 8000
```

### Step 3 — Start the frontend dev server

```bash
# inside Frontend/
npm run dev
```

Open **http://localhost:3000** in your browser.

The Vite dev server proxies all `/blogs` and `/health` requests to
`http://localhost:8000` automatically — no CORS issues.

---

## Build for Production

```bash
# inside Frontend/
npm run build
```

Output goes to `../static/dist/`.

Then add this to `main.py` (FastAPI) to serve it:

```python
from fastapi.staticfiles import StaticFiles

# Add AFTER all your API routes — must be last
app.mount("/", StaticFiles(directory="static/dist", html=True), name="static")
```

Now visiting `http://localhost:8000` serves the React app directly.

---

## Features

| Feature | Description |
|---|---|
| **Generate** | Enter topic → AI writes full blog with images |
| **Live status** | Polls every 4s while workflow is running |
| **Review** | Read blog before approving or rejecting |
| **Approve** | Triggers image generation pipeline |
| **Reject** | Provide reason — saved to database |
| **Edit** | Rewrite any part of the blog in a modal editor |
| **Rename** | Change blog title independently |
| **Delete** | Permanently remove from database |
| **Download** | Export as Markdown, PDF, or DOCX |
| **Filter** | Filter blog list by status |
| **Date grouping** | Blogs grouped by creation date |
| **Stats bar** | Live counts: total / pending / published / rejected |
| **Animated background** | Floating orbs + dot grid |
| **Skeleton loaders** | While AI is writing |

---

## API Endpoints Used

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/blogs/generate` | Start generation |
| `GET` | `/blogs` | List all blogs |
| `GET` | `/blogs/{thread_id}` | Get single blog |
| `GET` | `/blogs/{thread_id}/status` | Workflow state |
| `POST` | `/blogs/approve` | Approve |
| `POST` | `/blogs/reject` | Reject with reason |
| `PUT` | `/blogs/{thread_id}` | Edit title / content |
| `DELETE` | `/blogs/{thread_id}` | Delete |
