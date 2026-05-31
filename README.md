# ◈ LexTrace | AI-Powered Content Intelligence

LexTrace is a multi-layered, automated similarity engine designed for publishers, legal teams, and creators. It utilizes local vector embeddings and asynchronous web scraping to detect unauthorized copies, near-duplicates, and paraphrased plagiarism across the web, culminating in an automated DMCA takedown generator.

Built for **Codorra 2026**.

---

## 🚀 Core Features

* **Global Source Discovery:** Asynchronous web scraping engine searches thousands of indexed pages to locate URLs containing potential intellectual property theft.
* **Semantic Fingerprinting:** Bypasses basic "keyword matching." LexTrace uses state-of-the-art NLP models to map text into vector space, detecting when content has been rewritten or modified to avoid traditional plagiarism checkers.
* **Granular Comparison Diff:** Highlights exact matches and modified sentences side-by-side for rapid visual verification.
* **Automated DMCA Generation:** Dynamically calculates threat thresholds and generates formal, legally actionable DMCA Takedown notices populated with exact infringement data.

## 🏗️ Architecture & Tech Stack

LexTrace uses a decoupled, async microservice architecture:

**Frontend (Client)**
* **React + Vite:** High-performance, reactive UI state management.
* **Tailwind CSS:** Custom dark-mode, cyberpunk-inspired component library.
* **Framer Motion:** Fluid, hardware-accelerated SVG animations and layout transitions.

**Backend (API & ML Engine)**
* **FastAPI (Python):** Lightning-fast async endpoints for real-time scraping and inference.
* **Sentence-Transformers (`all-MiniLM-L6-v2`):** Localized HuggingFace model running entirely on-metal to generate 384-dimensional dense vector embeddings.
* **Cosine Similarity Matrixing:** Calculates semantic distances between the original input and scraped webpage HTML chunks.
* **DuckDuckGo Search Integration:** Live, unauthenticated web reconnaissance.

---

## ⚙️ Local Setup & Deployment

Due to the heavy memory requirements of loading `sentence-transformers` models (500MB+ RAM), the backend is designed to run locally for development and inference, while the frontend UI can be hosted on edge networks like Vercel.

### 1. Start the Machine Learning Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000



The backend will initialize the NLP model and expose the /api/v1/scan endpoint.

2. Start the Frontend Dashboard
Bash
cd frontend
npm install
npm run dev
Navigate to http://localhost:5173 to access the LexTrace interface.
