# SmartMap AI Travel Assistant

## 📌 About the App
SmartMap AI Travel Assistant is a web application that helps users find nearby places such as restaurants, hotels, cafes, and attractions. It combines AI recommendations using Ollama LLM and maps visualization using Leaflet. If Ollama is not available, it automatically falls back to Google Maps API or OpenStreetMap Nominatim.

---

## 🚀 Features

- AI-powered place suggestions using Ollama (LLaMA 3) or fallback to Google/Nominatim.
- Interactive map with markers for each location.
- Distance calculation from user's current location.
- Clickable links to Google Maps for each place.
- Supports searching in English and Indonesian.

---

## 💾 Download Ollama Models

> ⚠️ Important: Ollama model files are **not included in the repository** because of size. You must download them manually.
      Be sure to use llama3:latest 

1. Enter the Ollama container:

```bash
docker exec -it ollama bash

```
2. Pull the desired model (example: LLaMA 3):

```bash
ollama pull llama3

```

3. Exit the container. The model is now stored in the folder mapped to your host:
```bash
./ollama -> /root/.ollama

```


🛠 Requirements

 - Docker & Docker Compose
 - Python 3.10+ (for backend if running locally)
 - Google API Key (optional for more accurate geocoding)


📂 Project Folder Structure
```bash
root-folder/
├─ backend/
│  ├─ app.py
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ .env

├─ frontend/
│  ├─ index.html
│  ├─ script.js
│  └─ styles.css
├─ docker-compose.yml
└─ README.md
```

⚙️ Setup and Installation

1️⃣ Docker Compose Services

The project uses the following containers:

 - ollama → Ollama LLM service
 - openwebui → OpenWebUI interface (optional)
 - redis → Caching
 - backend → Flask backend
 - frontend → Nginx serving frontend files

```bash

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ./ollama:/root/.ollama
    command: serve

  openwebui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: openwebui
    restart: unless-stopped
    ports:
      - "3000:8080"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - WEBUI_AUTH=False
    depends_on:
      - ollama

  redis:
    image: redis:alpine
    container_name: redis
    restart: unless-stopped
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    container_name: map-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - OLLAMA_API=http://ollama:11434
      - GOOGLE_API_KEY=
      - CACHE_TTL=259200
    depends_on:
      - redis
      - ollama

  frontend:
    image: nginx:alpine
    container_name: map-frontend
    restart: unless-stopped
    ports:
      - "8080:80"
    volumes:
      - ./frontend:/usr/share/nginx/html
    depends_on:
      - backend

```
2️⃣ Create .env for Backend

Inside backend/ folder, create .env:
```bash

REDIS_URL=redis://redis:6379
OLLAMA_API=http://ollama:11434
GOOGLE_API_KEY=your_google_api_key_here
CACHE_TTL=259200

```

3️⃣ Build & Run All Services

Run the following command in your project root:

```bash

docker-compose up -d --build

```

This will:

 - Pull Docker images
 - Build the backend container
 - Start all services in detached mode

Check running containers:

```bash
docker ps
```
You should see ollama, openwebui, redis, map-backend, and map-frontend running.
<hr/>

🔎 Usage

1. Open frontend in your browser:

```bash
http://localhost:8080
```
2. Allow geolocation access to detect your position.
3. Enter a keyword (e.g., "restaurant in Jakarta") and click Search.
4. Map and sidebar will display results with markers, distance, and Google Maps links.


📝 Notes

- If OLLAMA_API is not reachable, the backend automatically falls back to Google/Nominatim.
- Marker popups include name, address, and link to Google Maps.
- Frontend

```bash
http://localhost:8080
```
- Backend

```bash
http://localhost:8000
```
- openwebui (optional)

```bash
http://localhost:3000
```
- ollama

```bash
http://localhost:11434
```
