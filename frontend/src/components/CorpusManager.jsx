import { useRef, useState } from 'react'
import { uploadCorpus, deleteCompany } from '../api'

export default function CorpusManager({ companies, onChanged }) {
  const [companyName, setCompanyName] = useState('')
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState(null)
  const inputRef = useRef(null)

  async function handleUpload() {
    if (!companyName.trim() || files.length === 0) return
    setBusy(true)
    setNote(null)
    try {
      const res = await uploadCorpus({ company: companyName, files })
      setNote({ ok: true, text: `Indexed ${res.chunks_indexed} chunks from ${res.files_indexed} file(s).` })
      setCompanyName('')
      setFiles([])
      if (inputRef.current) inputRef.current.value = ''
      onChanged()
    } catch (e) {
      setNote({ ok: false, text: e.message })
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(name) {
    try {
      await deleteCompany(name)
      onChanged()
    } catch (e) {
      setNote({ ok: false, text: e.message })
    }
  }

  return (
    <div>
      <div className="company-list">
        {companies.length === 0 && (
          <div style={{ color: 'var(--text-faint)', fontSize: 12 }}>No corpora indexed yet.</div>
        )}
        {companies.map((c) => (
          <div className="company-row" key={c.name}>
            <span className="name">{c.name}</span>
            <span className="chunks">{c.chunk_count} chunks</span>
            <button onClick={() => handleDelete(c.name)} title="Remove corpus">
              remove
            </button>
          </div>
        ))}
      </div>

      <label htmlFor="new-company">New corpus name</label>
      <input
        id="new-company"
        type="text"
        placeholder="e.g. acme-support"
        value={companyName}
        onChange={(e) => setCompanyName(e.target.value)}
      />

      <label htmlFor="corpus-files">Docs (.md / .txt)</label>
      <div className="file-drop" onClick={() => inputRef.current?.click()}>
        {files.length > 0 ? `${files.length} file(s) selected` : 'Click to choose files'}
        <input
          ref={inputRef}
          id="corpus-files"
          type="file"
          multiple
          accept=".md,.txt"
          onChange={(e) => setFiles(Array.from(e.target.files))}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handleUpload}
        disabled={busy || !companyName.trim() || files.length === 0}
      >
        {busy ? 'Indexing…' : 'Upload & index'}
      </button>

      {note && (
        <div className={note.ok ? 'escalation-note' : 'error-note'} style={note.ok ? { borderLeftColor: 'var(--teal)', color: 'var(--teal)', background: 'rgba(77,217,176,0.08)' } : {}}>
          {note.text}
        </div>
      )}
    </div>
  )
}
