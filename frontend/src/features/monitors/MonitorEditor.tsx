import { useState, type FormEvent } from 'react';
import { errorMessage, type Monitor, type MonitorInput } from '../../shared/api/client';

export function MonitorEditor({ monitor, onSave, onCancel }: {
  monitor: Monitor | null; onSave: (input: MonitorInput) => Promise<void>; onCancel: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try {
      await onSave({ name: String(form.get('name')), url: String(form.get('url')),
        interval_seconds: Number(form.get('interval')), timeout_seconds: Number(form.get('timeout')),
        expected_status: Number(form.get('status')), is_active: form.get('active') === 'on' });
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  }
  return <form className="surface editor" onSubmit={(event) => void submit(event)}>
    <h2>{monitor ? 'Editar monitor' : 'Novo monitor'}</h2>
    <fieldset disabled={busy}>
      <label>Nome do monitor<input name="name" defaultValue={monitor?.name} maxLength={100} required autoFocus /></label>
      <label>URL pública<input name="url" type="url" defaultValue={monitor?.url} placeholder="https://example.com" maxLength={2048} required /></label>
      <div className="form-grid">
        <label>Intervalo (segundos)<input name="interval" type="number" min={30} max={86400} defaultValue={monitor?.interval_seconds ?? 60} required /></label>
        <label>Timeout (segundos)<input name="timeout" type="number" min={1} max={30} defaultValue={monitor?.timeout_seconds ?? 10} required /></label>
        <label>Status HTTP esperado<input name="status" type="number" min={100} max={599} defaultValue={monitor?.expected_status ?? 200} required /></label>
      </div>
      <label className="checkbox"><input name="active" type="checkbox" defaultChecked={monitor?.is_active ?? true} /> Monitor ativo</label>
      <p className="hint">O intervalo deve ser maior que o timeout. As verificações HTTP serão habilitadas nos próximos marcos.</p>
      {error && <p role="alert" className="notice error">{error}</p>}
      <div className="actions"><button className="primary" type="submit">{busy ? 'Salvando…' : 'Salvar monitor'}</button>
        <button className="secondary" type="button" onClick={onCancel}>Cancelar</button></div>
    </fieldset>
  </form>;
}
