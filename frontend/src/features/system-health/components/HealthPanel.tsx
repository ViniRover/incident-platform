import type { HealthState } from '../hooks/useSystemHealth';

export function HealthPanel({ state, onRefresh }: { state: HealthState; onRefresh: () => void }) {
  return (
    <section className="panel" aria-labelledby="health-title">
      <h2 id="health-title">Diagnóstico da plataforma</h2>
      <div role="status" aria-live="polite">
        {state.kind === 'loading' && <p>Consultando dependências…</p>}
        {state.kind === 'error' && <p className="bad">{state.message}</p>}
        {state.kind === 'success' && <>
          <p className={state.report.status === 'ok' ? 'good' : 'bad'}>
            {state.report.status === 'ok' ? 'Plataforma disponível' : 'Dependências indisponíveis'}
          </p>
          <ul className="checks">
            {Object.entries(state.report.checks).map(([name, healthy]) => (
              <li key={name}><span>{name}</span><span className={healthy ? 'good' : 'bad'}>
                {healthy ? 'Disponível' : 'Indisponível'}
              </span></li>
            ))}
          </ul>
        </>}
      </div>
      <button onClick={onRefresh} disabled={state.kind === 'loading'}>Verificar novamente</button>
    </section>
  );
}
