/*
This file used to contain a Node-only SSE test script that imported
`node-fetch` and `abort-controller`, which broke Next.js builds when
compiled as part of the App Router.

The script has been moved to `frontend/test-stream.ts` so it can be
run manually with ts-node or node without affecting the web app.

To run the SSE test, use:

  npx ts-node frontend/test-stream.ts

This stub exists only to avoid accidental imports in the Next.js app.
*/
