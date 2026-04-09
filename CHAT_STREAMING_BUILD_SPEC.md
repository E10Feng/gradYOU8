# Chat Streaming Build Spec

## Goal
- Show clear live progress in chat while backend retrieval runs.
- Stream answer text incrementally so users can see ongoing work.
- Keep compatibility with current non-streaming `/chat` behavior.

## Scope
- Backend: add SSE endpoint at `POST /chat/stream`.
- Frontend: consume SSE in `ChatSidebar` and render status + streamed answer.
- Fallback: if SSE fails or is unavailable, automatically call existing `POST /chat`.

## Backend Contract (`POST /chat/stream`)
- **Request body:** same as `/chat`
  - `{ question: string, profile?: object, chat_history?: object[] }`
- **Response type:** `text/event-stream`
- **Event types:**
  - `status`: `{ "message": string }`
  - `answer_delta`: `{ "text": string }`
  - `sources`: `{ "sources": Source[], "doc_name": string }`
  - `error`: `{ "message": string }`
  - `done`: `{ "ok": boolean }`

## Frontend Behavior
- On submit:
  - add user bubble
  - add empty assistant bubble placeholder
  - open stream to `/chat/stream`
- While streaming:
  - update loading label with `status` events
  - append incoming `answer_delta.text` into assistant bubble
  - attach sources when `sources` event arrives
- On `done`:
  - stop loading state
- On stream failure:
  - fallback to `/chat` and replace placeholder with normal response

## UX Notes
- Stream progress should indicate activity but avoid exposing raw hidden model reasoning.
- Status language should be user-friendly (e.g. “Searching bulletin sections…”).

## Acceptance Criteria
- User sees at least one live status message before final answer.
- Assistant bubble fills incrementally for streamed requests.
- Existing chat still works when streaming endpoint is unavailable.
