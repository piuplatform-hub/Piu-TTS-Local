# SECURITY ARCHITECTURE & WINDOWS DEPLOYMENT STRATEGY (REVISION R1)
**Project:** AI Voice Studio — Professional Modular AI Platform  
**Document ID:** ARCH-SEC-001-R1  
**Status:** R1.1 — PROPOSED / PENDING OWNER APPROVAL (documentation revision only)  
**Date:** October 2026  

> **Canonical contract:** [CANONICAL_CONTRACTS.md](CANONICAL_CONTRACTS.md). This R1.1 text is a design proposal, not evidence of implementation or measured performance. For contradictions, canonical contracts and accepted ADRs take precedence.

---

## 1. Threat Modeling for Desktop & Small Office LAN

| Threat Vector | Risk Level | Threat Scenario | Architectural Countermeasure |
| :--- | :--- | :--- | :--- |
| **Accidental WAN / Internet Exposure** | **Critical** | Binding to `0.0.0.0` on an unfirewalled router exposes local files, voice cloning, and GPU compute to external attackers. | **Safe Defaults:** Server binds exclusively to `127.0.0.1`. LAN mode requires explicit Admin activation, setting an Admin Master Password, and generating an authentication secret. |
| **Host Header & DNS Rebinding Attacks** | **High** | Malicious websites visited by the user attempt cross-origin requests to `http://localhost:8765` to hijack API. | **Host & Origin Whitelist:** FastAPI middleware validates the `Host` header (rejecting unknown domains) and blocks unauthorized CORS `Origin` headers. |
| **Unauthorized LAN Privilege Escalation** | **High** | An employee on the LAN crafts requests to delete other users' projects or alter engine settings. | **RBAC & Ownership Enforcement:** Every project, voice profile, and job record checks ownership (`owner_id == current_user.id`) unless the user holds the `admin` role. |
| **Voice Cloning Identity Impersonation** | **High** | Uploading unauthorized audio of company executives or public figures to generate fraudulent voice tracks. | **Mandatory Consent Gate & Audit Trail:** Voice creation requires checking an explicit authorization declaration; logs record user ID, timestamp, and client IP cryptographically. |
| **Arbitrary File Traversal via Audio Uploads** | **High** | Uploading file names containing `../../Windows/System32` to overwrite critical system binaries. | **Strict Storage Isolation:** Uploaded files are renamed to UUIDv4 strings. Target paths must satisfy `Path(p).resolve().is_relative_to(STUDIO_DATA_DIR)`. |
| **Privilege Abuse via LocalSystem** | **High** | Running the background service under `NT AUTHORITY\LocalSystem` gives potential exploits full SYSTEM control. | **Least-Privilege Windows Account:** Application must run as a standard non-elevated user or a dedicated local service account with limited rights. |

---

## 2. Authentication & Local Onboarding Flow

To eliminate the security flaw of "automatically granting full Admin privileges to any localhost request", the application introduces an explicit **First-Run Onboarding Flow**:

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Local or LAN)
    participant Client as Web / Desktop Client
    participant API as FastAPI Auth Gateway
    participant DB as SQLite User Store

    User->>Client: Open Application
    Client->>API: GET /api/v1/auth/status
    API->>DB: Check if any user exists
    alt Zero Users Exist (First Boot)
        DB-->>API: Total users = 0
        API-->>Client: { needs_onboarding: true }
        Client->>User: Display Onboarding Wizard (Create Admin Account)
        User->>Client: Enter Admin Username & Strong Password
        Client->>API: POST /api/v1/auth/onboard (username, password)
        API->>DB: Hash password with Argon2id; Save Admin User
        API-->>Client: 201 Created after atomic one-time local bootstrap + one-time secret validation
    else Users Already Exist
        DB-->>API: Total users > 0
        API-->>Client: { needs_onboarding: false }
        Client->>User: Display Standard Login Screen
        User->>Client: Enter Credentials
        Client->>API: POST /api/v1/auth/login
        API-->>Client: 200 OK + JWT Bearer Token
    end
```

### Role-Based Access Control (RBAC) Matrix
* **Admin:** Full system configuration, approving engine plugins, enabling LAN access, user account management, viewing all jobs.
* **Editor:** Create/edit personal projects, upload reference audio for voice cloning, submit inference jobs, export audio.
* **Viewer:** Read-only access to assigned projects, listen to rendered audio, download master tracks.

---

## 3. Secure LAN Deployment & Reverse Proxy Strategy

When sharing the host PC over the local office network (example subnet only):

```
                                  OFFICE LAN (192.168.1.0/24)
                                                │
                                                ▼  HTTPS (Port 8443) / WSS
                       ┌─────────────────────────────────────────────────┐
                       │  Trusted LAN Reverse Proxy (Caddy / Nginx)      │
                       │  - Terminate TLS (Self-signed or local CA)       │
                       │  - Enforce Host Header: voice-studio.local       │
                       │  - Rate Limiting: 60 req/min per IP             │
                       └─────────────────────────────────────────────────┘
                                                │
                                                │ Loopback HTTP (127.0.0.1:8765)
                                                ▼
                       ┌─────────────────────────────────────────────────┐
                       │  AI Voice Studio Core Server (FastAPI)          │
                       │  - Validates Bearer JWT                         │
                       │  - Enforces User Ownership & RBAC               │
                       └─────────────────────────────────────────────────┘
```

* **TLS Strategy:** In pure plaintext HTTP across LAN, session tokens and audio files are exposed to LAN packet sniffing. For production LAN deployment, we recommend packaging a lightweight binary of **Caddy** that automatically provisions an internal self-signed certificate, or providing an HTTPS reverse proxy guide for the office network.
* **Windows Defender Firewall Rule:** LAN firewall rules must use the **actual approved office subnet**, not automatically trust all RFC1918 networks. Any rule change requires explicit admin approval and rollback instructions.

---

## 4. Software & AI Model Licensing Compliance Matrix

| Asset | Repository / Origin | License | Commercial Usage | Compliance Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **VieNeu-TTS Code & Weights** | `pnnbao97/VieNeu-TTS` | **Apache 2.0** | **Permitted** | Retain copyright notice and Apache 2.0 license text in redistributed distributions. |
| **Qwen3-TTS Code & Weights** | `QwenLM/Qwen3-TTS` | **Apache 2.0** | **Permitted** | Alibaba Cloud open-source license allows commercial modification and deployment. |
| **FFmpeg Binary** | `FFmpeg.org` | **Build-dependent LGPL 2.1+ or GPL** | **Subject to exact build review** | Execute as an external CLI subprocess (no dynamic linking into Python); provide build script or download link for LGPL compliance. |
| **FastAPI, React, Vite** | Open Source | **MIT** | **Permitted** | Standard MIT attribution. |
| **SQLite 3** | Official | **Public Domain** | **Permitted** | Completely unencumbered. |

---

## 5. Backup, Disaster Recovery & Restoration Verification

### 5.1 Automated Online Database Backup
Using SQLite’s online backup API, the database can be backed up while read and write queries are actively occurring without risking database corruption:
```python
# Pseudocode for the controlled backup service (not runnable without paths/locking).
# Prefer Python sqlite3.Connection.backup(destination) for the live database.
# Include a versioned manifest and a consistent snapshot strategy for audio assets.
# Verify restore into a temporary isolated data root before asserting backup health.
```

**Consistency requirement:** A SQLite backup is not a complete application backup: snapshot the associated voice samples, projects and audio artifacts with a manifest. Test restore (metadata + playable audio), not just `PRAGMA integrity_check`. Store backup copies outside the mutable working data directory where feasible.

### 5.2 Backup Restoration Test Procedure
To ensure backups are not corrupt, an automated test in the maintenance suite executes monthly:
1. Copy the latest backup snapshot to a temporary directory (`temp_restore.db`).
2. Run `PRAGMA integrity_check;` on the restored database.
3. Verify that all relational tables exist and can query the latest project ID.
4. Clean up temporary files and log success in `AUDIT_LOG`.


## 6. R1.1 Bootstrap and session hardening

- First-run administrator creation is local-only and requires a randomly generated, one-use setup secret emitted to a restricted local launcher/console. **No** network-accessible public bootstrap.
- Implement atomic one-admin initialization in a `BEGIN IMMEDIATE` transaction with a singleton bootstrap gate/unique constraint. Concurrent requests must not create two administrators.
- Password recovery is a separate owner-approved flow. A recovery code must be presented only once through an authenticated/authorized local setup step and stored as a verifier, never plaintext in logs.
- LAN browser sessions use secure cookies with HttpOnly/Secure/SameSite and CSRF defenses when cookie authentication is chosen, or carefully managed bearer tokens (never localStorage by default). CORS alone is **not** CSRF protection.
- Authorization decisions occur at application service boundaries for project, job, cloned voice, sample and artifact access—not only in route decorators.
- Do not register Windows services, add firewall rules or enable LAN as part of docs completion.
