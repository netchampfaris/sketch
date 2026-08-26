# Design the Fixture API and the stubbed resources

Type: grilling
Status: closed (out of scope)
Blocked by: 

## Question

How does an agent declare Fixtures, and how do createResource, createListResource, and createDocumentResource resolve against them in the Runtime? Decide: fixture file name and shape, how a resource key maps to a fixture, what insert/update/delete do (mutate in-memory only), and what an unknown resource returns. The answer must be simple enough to fit in the served skill.

## Answer

Closed out of scope, 2026-08-26. There is no Fixture API and no stubbed
resource. Prototype data lives in plain `ref`s.

The question assumed frappe-ui components fetch their own data. They do not.
Across `frappe-ui@1.0.0-beta.55` `src/` and `experimental/`, only three files
touch the network, and all three are file upload:

- `src/components/FileUploader` (POSTs `/api/method/upload_file`)
- `src/molecules/editor/extensions/shared/media-upload-engine.ts`
- `experimental/TextEditor/extensions/content-paste-extension.ts`

Every list, table, select, and form control takes plain props.
`frappe-ui/list` is composition-based: `<ListRows :items="tasks">` over an
array. The config-driven `experimental/ListView` has no resource code.

The ticket also under-counted the work. frappe-ui beta.55 ships two public
data layers with no shared seam:

- v1 `createResource` / `createListResource` / `createDocumentResource`.
  Reads `getConfig('resourceFetcher')`, falls back to `request`
  (`src/resources/resources.js:57-58`). Dotted methods:
  `frappe.client.get_list`, `.get`, `.insert`, `.set_value`, `.delete`,
  `run_doc_method`.
- v2 `useCall` / `useDoc` / `useList` / `useDoctype` / `useNewDoc`. Calls the
  global `fetch` inside a `createFetch` wrapper
  (`src/data-fetching/useFrappeFetch.ts:64-76`). URLs are
  `/api/v2/document/<Doctype>[/<name>][/method/<m>]`.

`grep getConfig src/data-fetching/` returns nothing, so
`setConfig('resourceFetcher', ...)` stubs v1 only. Stubbing both would mean
patching `fetch`, shimming two wire formats, and writing an in-memory engine
for Frappe's filter language. That is the largest single piece of Runtime
work in the MVP, and it buys only async states (three lines of `setTimeout`)
and copy-pasteable code (not a stated goal).

Rejected alternatives: doctype-table fixtures over a patched `fetch`; an
msw service worker; a Sketch-owned `useFixture()` helper.

Work this pushes elsewhere:

- Ticket 04 (Runtime): stub `/api/method/upload_file` inside the Viewer so
  FileUploader and the editor do not throw.
- Ticket 11 (served skill): teach the `ref` pattern; forbid `useList`,
  `useDoc`, `createResource` and friends in Prototype code.
