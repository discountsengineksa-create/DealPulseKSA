"""
Offline smoke test — synthesize Arabic + English clips without FastAPI.

Run:  python -m tts.smoke_test
Expect: two MP3s in generated_audio/, with durations printed.
"""

from __future__ import annotations

from tts.service import (
    DEFAULT_SPEED,
    DEFAULT_VOICE,
    OUTPUT_DIR,
    SAMPLE_RATE,
    encode_mp3,
    synthesize,
)

ARABIC_SCRIPT = (
    "أهلاً بكم في نبض الصفقات. "
    "اليوم نستعرض أبرز الخصومات الموثّقة من المتاجر السعودية الرائدة. "
    "كل كود يُعرض هنا مرّ بمراجعة دقيقة قبل النشر."
)

ENGLISH_SCRIPT = (
    "DealPulse deal-drop bulletin. "
    "Today's featured stores include curated offers with verified discount codes. "
    "Every voucher on this feed is checked against the source before publication."
)


def run(script: str, language: str, tag: str) -> None:
    audio = synthesize(script, voice=DEFAULT_VOICE, language=language, speed=DEFAULT_SPEED)
    out = OUTPUT_DIR / f"smoke_{tag}_{language}.mp3"
    encode_mp3(audio, out)
    print(f"OK  lang={language}  file={out}  duration={round(len(audio)/SAMPLE_RATE, 2)}s")


def main() -> None:
    run(ARABIC_SCRIPT, "ar", "dealpulse")
    run(ENGLISH_SCRIPT, "en", "dealpulse")


if __name__ == "__main__":
    main()
