# OpenAI TTS acceptance checklist

Run this checklist against a non-production OpenAI API project before changing
the TTS budget or enabling long-book processing in production.

## Verified short sample

**2026-09-18 automated live check:** `gpt-4o-mini-tts` with voice `alloy`
returned a valid 7.65-second WAV (367,244 bytes) in 3.43 seconds. At the
configured planning rate of $0.90 per generated audio hour, its estimated TTS
cost is approximately $0.0019. This verifies provider access, request latency,
WAV compatibility, and duration measurement; subjective speech-quality review
still requires listening.

1. Generate a 30-60 second English prose sample with `gpt-4o-mini-tts`.
2. Record time to the first ready segment, total request time, audio duration,
   configured voice, model, and the estimated TTS cost.
3. Listen for pronunciation, natural pauses, clipped endings, and stable voice
   delivery across at least three segments.

## PDF integration

Use separate small PDFs for prose, code, tables, diagrams, formulas, a
two-column layout, and a scan without a text layer. Before paid synthesis,
inspect the extracted source and narration for each block type. Then verify:

- audio text follows saved narration;
- segment and chapter order are correct;
- the next-ready segment can play before full processing completes;
- playback position survives a page reload;
- a worker restart preserves ready chunks and retries only missing chunks.

## Cost protection

1. Set `AI_READER_TTS_MAX_BOOK_COST_USD` to a low value.
2. Start processing a PDF whose TTS estimate is above that value.
3. Confirm that the book pauses before the next provider request would exceed
   the cap, while ready audio remains playable.
4. Increase the cap, resume the book, and confirm that processing continues
   without re-generating completed chunks.

Record the measured result and date in the project checklist only after these
steps pass with the intended provider account and browser targets.
