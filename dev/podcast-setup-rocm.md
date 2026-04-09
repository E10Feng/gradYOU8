# ROCm Setup for AMD 5500 XT (Podcast TTS)

## Goal
Get PyTorch using AMD 5500 XT GPU for Bark / Parler-TTS generation.
Currently: Bark and Parler-TTS fall back to CPU which is too slow (15-30 hrs for 15 min audio).

## What's needed
- ROCm runtime installed on Windows
- PyTorch built with ROCm support (`pip install torch --index-url https://download.pytorch.org/whl/rocm`)

## Current state
- Python 3.11.11 installed: `C:\Users\ethan\AppData\Local\Programs\Python\Python311`
- Virtual env: `C:\Users\ethan\.openclaw\workspace\podcast-env`
- Bark installed in venv (CPU fallback)
- Parler-TTS installed in venv (CPU fallback)
- Model: `parler-tts/parler-tts-mini-v1.1`
- Both models work but are too slow on CPU

## Next steps
1. Install ROCm on Windows (requires AMD driver + ROCm stack)
2. `pip uninstall torch` in podcast-env
3. `pip install torch --index-url https://download.pytorch.org/whl/rocm5.7` (or latest compatible)
4. Test GPU inference speed
5. If ROCm on Windows doesn't work, try Bark with smaller model or just pay for ElevenLabs

## Alternative (if ROCm fails)
- ElevenLabs Creator plan $11/mo → instant generation, 100 min/month
- Or keep text-only briefing, generate audio manually when needed
