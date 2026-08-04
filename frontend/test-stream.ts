/*
This file used to contain a Node-only SSE test script that imported
`node-fetch` and `abort-controller`, which broke Next.js type checking.

The script has been converted to plain JavaScript at
`frontend/test-stream.js` so it can be run manually without affecting
TypeScript builds.

To run the SSE test, use:

  node frontend/test-stream.js

This stub exists only to keep historical context; it is intentionally
free of imports so that Next.js type checking ignores it.
*/
