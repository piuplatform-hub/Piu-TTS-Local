# Source register — official references

**Retrieved/checked:** 2026-10-08 · **Evidence:** official pages and user-supplied R1 report; no Windows benchmark reproduced.

| Topic | Authoritative reference | Document implications |
|---|---|---|
| SQLite UPDATE / optional LIMIT | https://www.sqlite.org/lang_update.html · https://www.sqlite.org/compile.html | Do not rely on `UPDATE ... LIMIT` without compile feature; use tested ID subquery claim |
| SQLite RETURNING | https://www.sqlite.org/lang_returning.html | Requires compatible runtime; `RETURNING` only in top-level DML |
| SQLite backups | https://www.sqlite.org/backup.html | Use online backup API; include media consistency separately |
| Problem Details | https://www.rfc-editor.org/rfc/rfc9457 | Error response content type `application/problem+json` |
| FFmpeg legal | https://www.ffmpeg.org/legal.html | Specific binary may be LGPL or GPL based on included features |
| MCP 2026-07-28 | https://modelcontextprotocol.io/specification/2026-07-28/basic/transports | MCP future POST+JSON/POST+SSE; no old GET stream/session |
| Qwen3-TTS official | https://github.com/QwenLM/Qwen3-TTS | Model 0.6B CustomVoice supports Mandarin and other declared languages; Windows 6GB measurement unverified |
| VieNeu-TTS official | https://github.com/pnnbao97/VieNeu-TTS | Vietnamese voice synthesis/voice clone; CPU/Windows details to verify per pinned revision |

## Source/assumption boundaries
- Gemini R1's host OS/CPU/GPU observations were provided as a report, not independently executed in this container. Treat VRAM free as a point-in-time observation.
- Exact upstream repo commit, weights license and FFmpeg build flags are **not yet pinned**; record them during separately authorized engine feasibility spike.
- Detailed external compliance interpretation is not legal advice; verify licenses per redistributed artifact.
