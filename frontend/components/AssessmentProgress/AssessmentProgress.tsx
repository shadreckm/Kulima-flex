import React from 'react'

type ProgressStep = {
  key: string
  label: string
  status: 'pending' | 'in_progress' | 'complete'
}

type AssessmentProgressProps = {
  steps: ProgressStep[]
}

const STATUS_STYLES = {
  pending: 'bg-slate-200 text-slate-500 border-slate-300',
  in_progress: 'bg-[#F79009] text-white border-[#F79009] animate-pulse',
  complete: 'bg-[#0B5D3B] text-white border-[#0B5D3B]',
}

export default function AssessmentProgress({ steps }: AssessmentProgressProps) {
  return (
    <div className="p-4 bg-white rounded-[12px] border border-[#DDE6F0] shadow-saas">
      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-3">
        Assessment Progress
      </div>
      <div className="flex flex-col gap-2">
        {steps.map((step, index) => (
          <div key={step.key} className="flex items-center gap-3">
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold border ${STATUS_STYLES[step.status]}`}
            >
              {step.status === 'complete' ? '✓' : index + 1}
            </div>
            <div className="flex-1">
              <div className="text-xs font-semibold text-slate-900">{step.label}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
