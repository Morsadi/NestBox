# NestBox
#### Local-First Personal Cloud & File Management

## 1. Overview
NestBox is a local-first file management app that runs on your own machine and stays entirely on your home network. It allows you to upload files directly from other devices on the same LAN and store them on USB drives connected to the host machine.

The app works offline and doesn’t rely on external services. It provides a simple, login-protected dashboard for uploading, browsing, and managing photos, videos, and files stored on local drives.

<img width="1912" height="876" alt="Screenshot 2026-01-19 064247" src="https://github.com/user-attachments/assets/495c3381-e822-4cd6-8166-eb8cdab32388" /><img width="1910" height="876" alt="Screenshot 2026-01-19 064705" src="https://github.com/user-attachments/assets/59d1c50c-f744-4076-bd95-3aee7e6eb6a1" />
<img width="1892" height="873" alt="Screenshot 2026-01-19 064423" src="https://github.com/user-attachments/assets/0bd0ed84-678b-43d8-bbd1-45adc551ee43" /><img width="1894" height="873" alt="Screenshot 2026-01-19 064553" src="https://github.com/user-attachments/assets/26d0687e-8ed6-4f1a-aa13-29db0ecef6ed" />




## 2. Architecture & Tech Stack
Uploads are designed to return quickly, with the frontend doing minimal work while background workers handle file processing and storage.

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
