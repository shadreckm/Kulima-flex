"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Json = Record<string, any>;

const EVENT_LABELS: Record<string, string> = {
  assessment_created: "Assessment Created",
  documents_uploaded: "Documents Uploaded",
  research_started: "Research Started",
  research_completed: "Research Completed",
  signals_generated: "Signals Generated",
  decision_generated: "Decision Generated",
  reports_exported: "Reports Exported",
  feedback_submitted: "Feedback Submitted",
  audit_event: "Audit Event",
};

export default function ActivityPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<Json[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fetch("/api/v1/assessments?limit=1").then((r) => r.json());
        const items = (list?.items ?? list?.assessments ?? list ?? []) as Json[];
        const latest = Array.isArray(items) ? items[0] : null;
        if (!latest?.id) throw new Error("No assessment found. Create an assessment first.");
        const res = await fetch(`/api/v1/governance/activity?assessment_id=${latest.id}`);
        if (!res.ok) throw new Error(`API ${res.status}`);
        const payload = await res.json();
        const list2: Json[] = payload?.events ?? payload?.items ?? payload ?? [];
        if (!cancelled) setEvents(Array.isArray(list2) ? list2 : []);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? "Failed to load activity");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold">Activity Timeline</h1>
      {loading && <p className="mt-4 text-sm opacity-70">Loading activity…</p>}
      {error && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}{" "}
          <button className="underline" onClick={() => router.push("/dashboard")}>
            Go to dashboard
          </button>
        </div>
      )}
      {!loading && !error && events.length === 0 && (
        <p className="mt-4 text-sm opacity-70">No activity yet.</p>
      )}
      {events.length > 0 && (
        <ol className="mt-6 space-y-4 border-l-2 border-gray-200 pl-6">
          {events.map((e, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full bg-blue-500" />
              <div className="text-sm font-medium">
                {EVENT_LABELS[String(e.event_type ?? e.type ?? "audit_event")] ?? String(e.title ?? e.event_type ?? e.type ?? "Event")}
              </div>
              <div className="text-xs opacity-70">
                {e.created_at ?? e.timestamp ?? ""}
                {e.detail ?? e.message ?? "" ? ` — ${String(e.detail ?? e.message)}` : ""}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
