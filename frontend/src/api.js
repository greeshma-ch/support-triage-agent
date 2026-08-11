const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return res.json()
}

export async function fetchCompanies() {
  const res = await fetch(`${API_BASE}/api/companies`)
  return handle(res)
}

export async function triageTicket({ issue, subject, company }) {
  const res = await fetch(`${API_BASE}/api/triage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue, subject, company }),
  })
  return handle(res)
}

export async function uploadCorpus({ company, files }) {
  const form = new FormData()
  form.append('company', company)
  for (const f of files) form.append('files', f)
  const res = await fetch(`${API_BASE}/api/companies/upload`, {
    method: 'POST',
    body: form,
  })
  return handle(res)
}

export async function deleteCompany(name) {
  const res = await fetch(`${API_BASE}/api/companies/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  return handle(res)
}
