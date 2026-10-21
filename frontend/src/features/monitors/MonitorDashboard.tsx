import { useEffect, useState } from 'react';
import { errorMessage, type Monitor, type SessionInfo } from '../../shared/api/client';
import { MonitorEditor } from './MonitorEditor';
import type { MonitorGateway } from './gateway';

export function MonitorDashboard({ gateway, session }: { gateway: MonitorGateway; session: SessionInfo }) {
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState<Monitor | 'new' | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canWrite = session.role !== 'viewer';
  useEffect(() => {
    const controller = new AbortController();
    void gateway.list(offset, controller.signal).then((rows) => {
      if (!controller.signal.aborted) { setMonitors(rows); setLoading(false); }
    }, (failure) => {
      if (!controller.signal.aborted) { setError(errorMessage(failure)); setLoading(false); }
    });
    return () => controller.abort();
  }, [gateway, offset, revision]);

  function refresh() {
    setLoading(true); setError(''); setRevision((value) => value + 1);
  }

  async function remove(monitor: Monitor) {
    setBusy(true); setError('');
    try {
      await gateway.remove(monitor, session.csrf_token);
      setDeleting(null); setMessage('Monitor removido.'); refresh();
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  }

  return <section aria-labelledby="monitors-title">
    <div className="section-heading"><div><p className="eyebrow">DISPONIBILIDADE / CONFIGURAÇÃO</p>
      <h1 id="monitors-title">Monitores</h1><p>Gerencie os endpoints da sua organização.</p></div>
      <div className="actions"><button className="secondary" disabled={loading} onClick={refresh}>Atualizar lista</button>
        {canWrite && <button className="primary" onClick={() => setEditing('new')}>+ Novo monitor</button>}</div>
    </div>
    <div className="notice">M1 · Configuração disponível. Coleta de disponibilidade e incidentes serão habilitados nos próximos marcos.</div>
    {error && <p role="alert" className="notice error">{error}</p>}
    {message && <p role="status" className="notice success">{message}</p>}
    {editing && <MonitorEditor key={editing === 'new' ? 'new' : `${editing.id}-${editing.config_version}`}
      monitor={editing === 'new' ? null : editing} onCancel={() => setEditing(null)} onSave={async (input) => {
        if (editing === 'new') await gateway.create(input, session.csrf_token);
        else await gateway.update(editing, input, session.csrf_token);
        setEditing(null); setOffset(0); setMessage('Monitor salvo.'); refresh();
      }} />}
    <div aria-busy={loading} className="monitor-list">
      {loading && <p role="status">Carregando monitores…</p>}
      {!loading && !error && monitors.length === 0 && <div className="empty-state"><span className="empty-icon">◎</span>
        <h2>{offset ? 'Fim da lista' : 'Seus endpoints começam aqui'}</h2>
        <p>{canWrite ? 'Cadastre uma URL pública para preparar seu primeiro monitor.' : 'Ainda não há monitores nesta organização.'}</p></div>}
      {monitors.map((monitor) => <article key={monitor.id} className="monitor-row">
        <span className={`status-dot ${monitor.is_active ? 'active' : ''}`} aria-hidden="true" />
        <div className="monitor-identity"><h3>{monitor.name}</h3><span className="url">{monitor.url}</span></div>
        <div className="monitor-detail"><span>A cada {monitor.interval_seconds}s</span><small>Timeout {monitor.timeout_seconds}s · HTTP {monitor.expected_status}</small></div>
        <span className="badge">{monitor.is_active ? 'Configurado' : 'Pausado'}</span>
        {canWrite && <div className="actions"><button className="secondary" onClick={() => setEditing(monitor)}>Editar</button>
          {deleting === monitor.id ? <><button className="danger" disabled={busy} onClick={() => void remove(monitor)}>Confirmar remoção</button>
            <button className="secondary" disabled={busy} onClick={() => setDeleting(null)}>Cancelar remoção</button></>
            : <button className="text-button danger-text" onClick={() => setDeleting(monitor.id)}>Remover</button>}</div>}
      </article>)}
    </div>
    <nav className="pagination" aria-label="Paginação de monitores">
      <button className="secondary" disabled={offset === 0 || loading} onClick={() => { setLoading(true); setOffset(Math.max(0, offset - 20)); }}>Anterior</button>
      <span>Página {Math.floor(offset / 20) + 1}</span>
      <button className="secondary" disabled={monitors.length < 20 || loading} onClick={() => { setLoading(true); setOffset(offset + 20); }}>Próxima</button>
    </nav>
  </section>;
}
