import { useEffect, useState } from 'react';
import { AuthForm, MemberManager, createIdentityGateway } from '../features/identity';
import { MonitorDashboard, createMonitorGateway } from '../features/monitors';
import { SystemHealth, createHealthGateway } from '../features/system-health';
import { ApiError, errorMessage, type SessionInfo } from '../shared/api/client';

const healthGateway = createHealthGateway();
const identityGateway = createIdentityGateway();
const monitorGateway = createMonitorGateway();

export function App() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [tab, setTab] = useState<'monitors' | 'members' | 'health'>('monitors');
  useEffect(() => {
    const controller = new AbortController();
    void identityGateway.me(controller.signal).then((current) => {
      if (!controller.signal.aborted) { setSession(current); setLoading(false); }
    }, (failure) => {
      if (!controller.signal.aborted) {
        if (!(failure instanceof ApiError && failure.status === 401)) setError(errorMessage(failure));
        setLoading(false);
      }
    });
    return () => controller.abort();
  }, [revision]);

  async function logout() {
    if (!session) return;
    try { await identityGateway.logout(session.csrf_token); setSession(null); setTab('monitors'); setError(''); }
    catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) { setSession(null); setTab('monitors'); }
      else setError(errorMessage(failure));
    }
  }

  if (loading) return <main className="boot-screen"><span className="brand">◉ pulse</span><p role="status">Abrindo seu espaço…</p></main>;
  if (!session) return <main className="auth-layout"><div className="auth-story">
    <span className="brand">◉ pulse</span><p className="eyebrow">MONITORAMENTO COM CONTEXTO</p>
    <h1>Um lugar para cuidar<br />da sua disponibilidade.</h1>
    <p>Organize seus endpoints, controle acessos e prepare sua operação para responder a incidentes.</p>
    <span className="milestone">M1 · Identidade e monitores</span>
  </div><div className="auth-form-wrap">
    {error && <div className="notice error" role="alert">{error}<button className="text-button" onClick={() => {
      setLoading(true); setError(''); setRevision((value) => value + 1);
    }}>Tentar novamente</button></div>}
    <AuthForm gateway={identityGateway} onAuthenticated={(current) => { setSession(current); setError(''); }} />
  </div></main>;

  return <div className="workspace"><aside className="sidebar">
    <span className="brand">◉ pulse</span><div className="tenant-card"><small>ORGANIZAÇÃO</small>
      <strong>{session.tenant_name}</strong><span>{session.tenant_slug}</span></div>
    <nav aria-label="Navegação principal">
      <button aria-current={tab === 'monitors' ? 'page' : undefined} onClick={() => setTab('monitors')}>◎ Monitores</button>
      {(session.role === 'owner' || session.role === 'admin') && <button aria-current={tab === 'members' ? 'page' : undefined} onClick={() => setTab('members')}>♙ Pessoas e acessos</button>}
      <button aria-current={tab === 'health' ? 'page' : undefined} onClick={() => setTab('health')}>↗ Diagnóstico</button>
    </nav><p className="sidebar-note">As configurações pertencem apenas à sua organização.</p>
  </aside><div className="workspace-body"><header className="topbar"><span className="workspace-label">Seu espaço de operação</span>
    <div className="user-menu"><div><strong>{session.name}</strong><small>{session.role}</small></div>
      <button className="secondary" onClick={() => void logout()}>Sair</button></div></header>
    <main className="content">{error && <p role="alert" className="notice error">{error}</p>}
      {tab === 'monitors' && <MonitorDashboard key={session.tenant_id} gateway={monitorGateway} session={session} />}
      {tab === 'members' && <MemberManager key={session.tenant_id} gateway={identityGateway} session={session} />}
      {tab === 'health' && <><h1>Diagnóstico da plataforma</h1><p>Disponibilidade das dependências da aplicação.</p><SystemHealth gateway={healthGateway} /></>}
    </main><footer>Pulse · M1 / Configuração de monitores e controle de acesso</footer>
  </div></div>;
}
