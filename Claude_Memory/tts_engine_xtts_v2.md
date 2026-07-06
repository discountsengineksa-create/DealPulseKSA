---
name: Local TTS Engine — XTTS v2 (REMOVED 2026-07-06)
description: The local XTTS v2 TTS engine + Reels Studio page were built then fully removed — Arabic quality too weak; do not rebuild free-local, go premium API
type: project
originSessionId: ce97ea79-0034-4f51-b8fb-e7e36536ea26
---
**STATUS: REMOVED 2026-07-06.** The local Coqui XTTS v2 TTS engine (`tts/` dir) and the «🎬 استوديو الريلز» dashboard page were deleted from root at the user's explicit request ("احذف استديو الريل ... من جذوره"). Do NOT rebuild the free-local approach.

**Why it was removed:** After getting XTTS v2 installed and generating on Python 3.13 (the install itself was a hard 5-layer fight — see git history commits 01ed10b/32d6c27), the user judged the actual **voice output** 0/100: it sounded robotic/"AI", not the «فخم» broadcast quality he pictured, and nowhere near his real vision of a **طبق الأصل (near-identical) replica of a real voice** that he could then remix/tune. Param tuning (temperature/repetition_penalty), voice-clone upload + ffmpeg extraction, and a planned Demucs vocal-isolation step were all built or offered — none of it changes the fundamental ceiling.

**The honest lesson (do not relitigate):** In 2026 there is **no free, fully-local Arabic TTS engine that sounds premium**. XTTS zero-shot cloning from a short clip captures rough timbre only, never a طبق-الأصل replica, and its Arabic is a notch below its English. The user's two requirements — (1) fully local/free, (2) premium/replica voice — are mutually exclusive with open-source tools. The real path to his vision is a **premium neural API**: ElevenLabs (incl. Professional Voice Cloning, needs ~30 min clean audio) for closest-to-replica, or **Azure Neural Arabic** (Hamed/Zariyah) / Amazon Polly (Hala/Zayd) for premium narration at ~fractions of a cent per reel. If TTS is ever revisited, start there — not local. See [[feedback_output_over_engineering]].

**What still exists on the machine (not in repo):** ffmpeg was installed via `winget install Gyan.FFmpeg` (general-purpose, harmless to keep). The ~2.1GB XTTS model cache at `%LOCALAPPDATA%\tts\` is now orphaned — safe to delete to reclaim disk. Kokoro was rejected earlier for zero Arabic support (still true).
