# NestBox
#### Local-First Personal Cloud & File Management
**Video Demo:** <https://www.youtube.com/watch?v=Cz2ETY16rG8>

## 1. Overview
NestBox is a local-first file management system designed to regain control over your data. In an era where subscription costs for cloud storage are rising and privacy concerns are prevalent, NestBox offers a self-hosted alternative. It turns connected USB drives into a private, secure "personal cloud" accessible via any device on your LAN (phones, VR headsets, laptops).

NestBox runs entirely offline, giving you full control over your data and avoiding reliance on external internet services. The application includes a simple, login-protected dashboard that allows you to upload and browse photos, videos, and files from any device on your home network.

## 2. Architecture & Tech Stack
I built the application logic on a robust separation of concerns between the synchronous web server and asynchronous background workers.

**The Core Flow:**
1.  **Frontend:** Dropzone.js handles chunked file uploads, ensuring reliability.
2.  **Server:** Flask receives chunks, manages user sessions, and enforces HTTPS.
3.  **Async Processing:** Redis acts as a message broker; Celery executes heavy lifting (merging files, scanning drives) in the background to prevent UI freezing.
4.  **Storage:** SQLite indexes metadata for fast browsing, while local USB drives store the actual assets.

| Component | Technology Used | Purpose |
| :--- | :--- | :--- |
| **Backend** | **Flask** (Python) | Handles routing, session management, and the HTTPS server logic. |
| **Async Tasks** | **Celery** + **Redis** | Manages background processing for heavy tasks like merging large files and recursively scanning drives. |
| **Frontend** | **Jinja2** + **Dropzone.js** | Provides server-side rendering and handles reliable, chunked file uploads via JavaScript. |
| **Security** | **Cryptography** | Programmatically generates self-signed SSL certs to enable secure LAN data transfer. |
| **Media** | **Pillow** | Performs on-the-fly image resizing and optimization to speed up the gallery view. |
| **Database** | **SQLite** | Stores lightweight metadata (User credentials & File Index) to avoid file-system lag. |

## 3. Project Structure
A high-level view of the application codebase.

```text
NestBox/
├── app.py                 # Main entry point: App factory, DB setup, SSL launch.
├── celery_worker.py       # Background worker: Scans drives, merges file chunks.
├── run_all.py             # Script to launch Redis, Celery, and Flask simultaneously.
├── .env                   # Configuration (e.g., INVITATION_CODE).
├── helpers.py             # Utilities: Auth, DB connections, Path safety.
├── storage_utils.py       # IO operations: Drive detection, file type mapping.
├── cert_utils.py          # SSL: Generates 'nestbox.crt' & 'nestbox.key'.
├── requirements.txt       # Dependencies (Flask, Redis, Pillow, etc).
│
├── routes/                # Blueprint Definitions
│   ├── auth.py            # Login/Logout logic
│   ├── browse.py          # Directory navigation
│   ├── media.py           # Image serving via Pillow
│   └── upload.py          # Chunk ingestion logic
│
├── instance/              # Local Data Storage
│   ├── users.db           # User credentials
│   └── file_index.db      # Indexed file metadata
│
└── static/ & templates/   # Frontend Assets
    ├── js/dashboard.js    # Handles drive scanning, dashboard UI updates
    ├── js/upload.js       # Client-side chunking & progress UI
    ├── js/media.js        # Controls the Files and Gallery views. Handles thumbnail loading, video poster loading.
    └── templates/*.html   # Jinja2 views (Dashboard, Login, Browser)
```

## 4. Key Design Decisions

### Chunked Uploads
Large uploads often fail on unstable connections or mobile browsers. Chunking makes uploads reliable by splitting files into small pieces, allowing retries only for failed parts. This approach supports smooth multi-gigabyte uploads from any device.

### Celery for Background Tasks
Drive indexing and chunk merging are heavy operations. Running them directly in Flask would freeze the UI. Celery processes these tasks asynchronously, keeping the interface responsive while offloading long-running work.

### Local-First Architecture
NestBox runs entirely inside your local network. This provides:
- Complete privacy  
- No dependence on cloud services  
- Much faster transfers than the internet  
- Full functionality even without internet access  

This architecture gives users total control over their data.

### Pillow for Media Processing
The project originally used an external tool for thumbnails, but Pillow offered a simpler, cross-platform, fully Python solution. It allows generating image previews on demand with fewer dependencies.

### Cryptography for HTTPS
Mobile browsers restrict advanced file APIs on non-HTTPS connections. A self-signed SSL certificate is required for secure uploads across devices. The `cryptography` library generates these certificates automatically, providing a consistent setup on Windows, macOS, and Linux.

## 5. Setup Guide
For installation and step-by-step setup, see the full setup guide:
[setup_guide.md](./setup_guide.md)
