import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_BASE_URL || '/api'
const CATEGORIES = ['Food', 'Transport', 'Home', 'Health', 'Salary', 'Other']
const money = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
})

async function request(path, { token, ...options } = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(result.error || 'Something went wrong.')
  return result
}

function AuthScreen({ onLogin }) {
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function sendCode(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await request('/auth/otp/send', {
        method: 'POST',
        body: JSON.stringify({ phone }),
      })
      setSent(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function verifyCode(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await request('/auth/otp/verify', {
        method: 'POST',
        body: JSON.stringify({ phone, code }),
      })
      onLogin(result.token, result.phone)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-shell">
      <div className="auth-art" aria-hidden="true">
        <span className="art-orbit orbit-one" />
        <span className="art-orbit orbit-two" />
        <span className="art-dot" />
        <span className="art-label">YOUR MONEY, IN GOOD SHAPE</span>
        <div className="art-note"><span>THIS MONTH</span><strong>More clarity.<br />Less guesswork.</strong><i>↗</i></div>
      </div>
      <section className="auth-panel">
        <div className="brand"><span className="brand-mark">+</span><span>pocket<span className="brand-light">note</span></span></div>
        <div className="auth-copy">
          <p className="eyebrow">A CLEARER WAY TO KEEP TRACK</p>
          <h1>Your money,<br />in balance.</h1>
          <p className="muted">A little more clarity for every day.</p>
        </div>
        <form className="auth-form" onSubmit={sent ? verifyCode : sendCode}>
          {!sent ? (
            <label>Mobile number
              <input autoComplete="tel" inputMode="tel" placeholder="+91 98765 43210" value={phone} onChange={(e) => setPhone(e.target.value)} required />
            </label>
          ) : (
            <>
              <label>Verification code
                <input autoComplete="one-time-code" inputMode="numeric" maxLength="6" placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} required />
              </label>
              <p className="form-hint">Sent to {phone}. <button className="text-button" type="button" onClick={() => { setSent(false); setCode('') }}>Change number</button></p>
            </>
          )}
          {error && <p className="error-message" role="alert">{error}</p>}
          <button className="primary-button" disabled={busy} type="submit">{busy ? 'Please wait…' : sent ? 'Verify & continue' : 'Send a one-time code'} <span aria-hidden="true">↗</span></button>
        </form>
        <p className="auth-foot">Secure sign-in powered by MiniMoth OTP</p>
      </section>
    </main>
  )
}

function Dashboard({ token, phone, onLogout }) {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ description: '', amount: '', type: 'expense', category: 'Food' })
  const [saving, setSaving] = useState(false)

  async function loadTransactions() {
    try {
      const result = await request('/transactions', { token })
      setTransactions(result.transactions)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTransactions() }, [token])

  const income = transactions.filter((item) => item.type === 'income').reduce((sum, item) => sum + item.amount, 0)
  const spending = transactions.filter((item) => item.type === 'expense').reduce((sum, item) => sum + item.amount, 0)
  const balance = income - spending

  async function addTransaction(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await request('/transactions', { token, method: 'POST', body: JSON.stringify(form) })
      setForm({ ...form, description: '', amount: '' })
      await loadTransactions()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function removeTransaction(id) {
    try {
      await request(`/transactions/${id}`, { token, method: 'DELETE' })
      setTransactions((items) => items.filter((item) => item.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">+</span><span>pocket<span className="brand-light">note</span></span></div>
        <div className="account"><span className="account-phone">{phone}</span><button className="logout-button" onClick={onLogout}>Sign out</button></div>
      </header>
      <section className="welcome-row">
        <div><p className="eyebrow">YOUR PERSONAL FINANCE DASHBOARD</p><h1>Good to see you.</h1><p className="muted">The small picture and the big picture, together.</p></div>
        <div className="date-chip"><span className="date-dot" /> LIVE OVERVIEW</div>
      </section>
      <section className="summary-grid" aria-label="Finance summary">
        <article className="summary-card balance-card"><p>Available balance</p><strong>{money.format(balance)}</strong><span>Income minus spending</span><b className="summary-spark">↗</b></article>
        <article className="summary-card"><p>Money in</p><strong>{money.format(income)}</strong><span className="green-text">Across {transactions.filter((item) => item.type === 'income').length} entries</span><span className="card-symbol">＋</span></article>
        <article className="summary-card"><p>Money out</p><strong>{money.format(spending)}</strong><span className="coral-text">Across {transactions.filter((item) => item.type === 'expense').length} entries</span><span className="card-symbol coral-text">−</span></article>
      </section>
      <div className="content-grid">
        <section className="activity-section">
          <div className="section-heading"><div><p className="eyebrow">YOUR RECENT MOVEMENT</p><h2>Transactions</h2></div><span className="count-pill">{transactions.length} TOTAL</span></div>
          {error && <p className="error-message page-error" role="alert">{error}</p>}
          <div className="transaction-list">
            {loading ? <p className="empty-state">Loading your transactions…</p> : transactions.length === 0 ? <p className="empty-state">Nothing here yet. Add your first transaction to get started.</p> : transactions.map((item) => (
              <article className="transaction-row" key={item.id}>
                <span className={`transaction-icon ${item.type}`}>{item.type === 'income' ? '↙' : '↗'}</span>
                <div className="transaction-detail"><strong>{item.description}</strong><span>{item.category} <i>·</i> {new Date(`${item.date}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</span></div>
                <strong className={`transaction-amount ${item.type}`}>{item.type === 'income' ? '+' : '−'}{money.format(item.amount)}</strong>
                <button className="delete-button" title="Delete transaction" aria-label={`Delete ${item.description}`} onClick={() => removeTransaction(item.id)}>×</button>
              </article>
            ))}
          </div>
        </section>
        <aside className="add-section">
          <p className="eyebrow">KEEP IT UP TO DATE</p><h2>Add a transaction</h2>
          <form className="transaction-form" onSubmit={addTransaction}>
            <fieldset className="type-toggle"><legend className="sr-only">Transaction type</legend>{['expense', 'income'].map((type) => <button type="button" key={type} className={form.type === type ? `active ${type}` : ''} onClick={() => setForm({ ...form, type })}>{type === 'expense' ? 'Money out' : 'Money in'}</button>)}</fieldset>
            <label>Description<input maxLength="80" placeholder="e.g. Weekly groceries" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required /></label>
            <label>Amount<input type="number" min="0.01" step="0.01" placeholder="0.00" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></label>
            <label>Category<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATEGORIES.map((category) => <option key={category}>{category}</option>)}</select></label>
            <button className="primary-button add-button" disabled={saving} type="submit">{saving ? 'Adding…' : 'Add to your activity'} <span aria-hidden="true">＋</span></button>
          </form>
        </aside>
      </div>
      <footer className="page-footer"><span>pocketnote</span><span>Keep a little closer to your money.</span></footer>
    </main>
  )
}

export default function App() {
  const [auth, setAuth] = useState(() => ({ token: localStorage.getItem('finance_token'), phone: localStorage.getItem('finance_phone') || '' }))

  function login(token, phone) {
    localStorage.setItem('finance_token', token)
    localStorage.setItem('finance_phone', phone)
    setAuth({ token, phone })
  }

  function logout() {
    localStorage.removeItem('finance_token')
    localStorage.removeItem('finance_phone')
    setAuth({ token: null, phone: '' })
  }

  return auth.token ? <Dashboard token={auth.token} phone={auth.phone} onLogout={logout} /> : <AuthScreen onLogin={login} />
}