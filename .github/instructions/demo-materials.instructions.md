---
description: "Use when creating, capturing, editing, merging, or validating SRM demo-materials screenshot decks, PowerPoint presentations, and PDF fixtures."
applyTo: "docs/demo-materials/**"
---

# Demo Materials and Screenshot Decks

Follow [AGENTS.md](../../AGENTS.md). These instructions apply to
[demo materials](../../docs/demo-materials/), not to unrelated repository work.
Use the [demo script](../../docs/09-demo-script.md) for step order, prompts, timings,
and fallbacks, and the [PDF package guide](../../docs/demo-materials/pdf-analysis/README.md)
for fixture selection. Preserve requirement traceability, particularly `SRM-FIN-001`,
`SRM-NFR-001`, and the human-accountability boundary.

## Scope and Deliverables

- Read the current files, not just earlier chat summaries: users may have edited a deck
  between requests. Snapshot the current deck and its hash before modifying it.
- Confirm which sections and channel to capture. Microsoft Copilot with SRM Orchestrator
  is not interchangeable with generic Copilot chat or Copilot Studio Draft Preview.
  Never publish, install, reconfigure, or switch the agent/channel silently.
- Default to one genuine screenshot or focused UI crop per slide, with one concise
  tagline explaining the action or business value. Add a graphical overview only when
  requested; reproduce the script's node order and dotted human-decision handoff.
- Save requested final presentations in `docs/demo-materials/` with descriptive kebab-case
  names. Keep intermediate images, scripts, exports, package installs, browser profiles,
  and QA renders outside tracked source paths, such as the session workspace.
- Append requested sections without rewriting existing slides or the demo script.
  When merging into a newly named deck, preserve both originals unless told otherwise.
  Do not commit or push without a current request.

## Guest Browser and Capture

1. Launch a visible Guest browser with a task-specific profile. Wait for the user to
   complete login; never obtain credentials or reuse an unrelated personal profile.
2. Verify the intended account has access and that the visible agent is SRM Orchestrator.
   If it is unavailable, ask the user to open it, switch account, or provide its link.
   Do not submit to generic chat as a substitute.
3. Use the script's actual prompts and only the specified fictional attachments.
   Wait for upload completion before sending. Never upload presenter checks, seed CSVs,
   expected-results files, the manifest, or the script as evidence.
4. Preserve the digital conversation for later collateral and calculation steps.
   Use separate fresh conversations for the image-only and unreadable fixtures so
   readable evidence cannot contaminate the missing-value demonstration.
5. Capture complete, settled answers and explicit review gates. Respect the script's
   response timeout and disclose a timeout or fallback rather than silently rerunning.
   Never fabricate a response or present a prepared example as fresh execution.

### Browser Automation Learnings

- Prefer available browser tools. If their provider cannot start, use an available local
  Playwright/CDP path rather than repeatedly invoking the same broken provider. Bind any
  debugging endpoint to loopback, use an unused port, and verify browser responsiveness.
- Track the intended tab by target/page identity: submitting a message assigns a new
  conversation URL. Preserve this run's conversation links for continuation; do not
  open unrelated history or store account-wide snapshots.
- Bring the target tab to the foreground before screenshots. Background tabs caused
  screenshot timeouts; do not solve those by resubmitting the conversation.
- Wait on visible upload, response, and final-answer controls, not arbitrary sleeps.
  Intermediate copy buttons or status text can appear before tables finish rendering.
- Use a consistent viewport; `1600 x 900` worked for chat captures. Native PDF-viewer
  captures can behave differently under viewport emulation: inspect the actual image,
  including its active document and page, before using it.
- Stop only task-owned browser processes and remove their temporary profiles after
  closing them. Do not terminate shared browsers or leave an authenticated debug
  endpoint running after the task.

## Evidence, Privacy, and Live Writes

- Mask account avatars, real names/contact fields, creator bylines, and unrelated chat
  navigation. Inspect pixels as well as slide text, speaker notes, links, and metadata
  before sharing or committing. Do not retain an unmasked copy in tracked source.
- Do not retouch financial values, agent wording, errors, or approval states. Focused
  crops are allowed, but must not hide a limitation or make a failed run look successful.
- Check extracted figures, signs, units, periods, and physical page citations against
  the actual PDF locally. Keep interim separate and unreadable values missing, not zero.
  For the original FY2025 fixtures, scan pages 1-3 correspond to digital pages 7-9.
  Verify a PDF has no embedded text before describing it as image-only.
- Keep original filenames separate from processor-suffixed delivery aliases. Record
  unresolved provenance; do not claim independent filename verification from a prompt.
- Keep the 62%/68% collateral claims separate and unverified. Missing guarantees,
  leases, or arbitration evidence remain gaps, not proof of no exposure.
- Do not promote the agent's self-description of OCR, rendering, or verification into
  independently verified execution evidence. Verify calculations independently,
  including rounding; a reverse-check using rounded percentages is approximate.
- Microsoft Copilot uploads may create OneDrive copies and chat history. "No Dataverse
  save" does not mean "nothing stored anywhere." Explain this distinction in notes.
- Capture is read-only unless writes are explicitly authorized. Before a draft save,
  confirm DemoPRE and the exact generated request reference, not merely its display
  label. Keep seeded examples read-only. Check existing drafts and ask before replacing
  one, even if a save was authorized in general.
- Record baseline rating, confirmation, status, stage, narrative, and relevant evidence
  state. Use the existing save tool and current [contract](../../flows/save-review-analysis-draft/contract.json);
  do not bypass it with direct writes to manufacture successful screenshots.
- HTTP 502, a polling timeout, or missing `saved=true` means persistence is unconfirmed,
  not necessarily that nothing was written. Inspect the narrative, revision-specific
  working papers, unverified claims, and started/completed audit rows read-only.
  Never retry an uncertain write automatically. An explicitly authorized retry must
  reuse the same revision key and byte-for-byte identical payload.
- Match captions to observed results. Good: "Existing narrative - read-only fallback;
  not this run's saved draft." Wrong: calling a pre-existing narrative or the app's
  generic "Saved" header proof of the attempted save. Do not infer a root cause from
  an HTTP status alone or fix/deploy the flow as part of a screenshot task.
- Final ratings remain human-owned. Prefer a read-only hypothetical explanation when
  illustrating the final-rating boundary; never execute a rating write for a screenshot.
  A signed-in chat is not the implemented authenticated business-approval workflow.

## Readable Slides and Presenter Notes

- Match the existing deck: widescreen 16:9, charcoal `23343B`, white captions, mint
  `97D3C3` accents, and Calibri text. Screenshot taglines use approximately 20 pt.
  Preserve at least 0.5-inch margins and a 0.3-inch image-to-caption gap.
- Contain images without stretching. Crop unused UI only after checking complete
  headings, all relevant rows/columns, negative signs, and final lines remain visible.
- Wide chat tables can stay clipped even at larger viewport widths because their
  containers have a fixed maximum width. Ask for a layout-only reformat into narrower
  tables or bullets, without approving facts, calculations, ratings, or writes.
  Verify every reformatted value and citation is unchanged, and note the extra prompt.
- Do not include process chatter as a completed answer. If an answer contains an error,
  obtain a source-backed correction or disclose the limitation; do not edit the pixels.
- Put capture date, actual channel, script step, source/requirement references, seeded
  versus fresh status, privacy masks/crops, extra layout prompts, and verification limits
  in speaker notes. Include storage caveats and any save error or fallback.

## PowerPoint Editing and Verification Learnings

- Use the PowerPoint skill and existing installed tooling. Native PowerPoint COM is
  available on the project workstation for slide insertion and PNG export.
- `Slides.InsertFromFile` can lose imported backgrounds, making white captions invisible.
  Restore each imported slide's source background and verify the result; successful
  insertion alone does not establish formatting fidelity.
- Imported decks may have only one slide layout. Do not assume a blank layout at index
  6. Reuse an existing appropriate layout. Notes masters may lack body placeholders;
  preserve or clone the existing notes-body convention instead of dropping notes.
- Native PowerPoint rendering is the visual reference. After append/merge, compare each
  unchanged slide with a rendering of the current baseline at the same resolution.
  Preserve slide order, captions, notes, screenshot bytes, and visual appearance.
- Validate the PPTX ZIP/XML, slide count, embedded images, and notes. Check actual
  rendered text bounds against shape dimensions minus internal padding.
- Visually inspect every new/affected slide, using an independent reviewer when
  available. Look for clipped table columns, partial preceding/next lines, invisible
  text, account leaks, misleading captions, and empty grids whose row counts are cut off.
  Fix issues and re-render/recheck affected slides before delivery.
- Before replacing the target, verify its hash still matches the captured baseline.
  If it changed during the task, preserve the user's edits rather than overwriting them.
  Verify the persisted file matches the validated output, then clean only task-owned
  intermediates and report the deliverable and any unverified capability honestly.
