Kulima Frontend Prototype (Phase 1)

This is a mock Next.js + TypeScript + Tailwind prototype for the Chat-First UX.

Run instructions:
1. Open a terminal in frontend/ (Windows PowerShell or cmd)
2. npm install
3. npm run dev
4. Open http://localhost:3000/flex and /signals

Notes:
- This is mock-only UI. No backend integration.
- Uses Tailwind for styles.
- Components:
  - ChatShell
  - MessageList
  - Composer
  - AttachmentPills
  - ContextPanel

Design goals:
- Chat-first UX similar to Microsoft Copilot
- Composer fixed at bottom; attachments shown as pills
- Context panel is secondary on the right
