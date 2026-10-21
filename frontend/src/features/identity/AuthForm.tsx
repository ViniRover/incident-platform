import { useState, type FormEvent } from 'react';
import { ApiError, errorMessage, type SessionInfo } from '../../shared/api/client';
import type { IdentityGateway } from './gateway';

export function AuthForm({ gateway, onAuthenticated }: { gateway: IdentityGateway; onAuthenticated: (session: SessionInfo) => void }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (key: string) => String(form.get(key) ?? '');
    setBusy(true); setError('');
    try {
      const input = { tenant_slug: text('tenant_slug'), email: text('email'), password: text('password') };
      const session = register
        ? await gateway.register({ ...input, tenant_name: text('tenant_name'), name: text('name') })
        : await gateway.login(input);
      onAuthenticated(session);
    } catch (failure) {
      setError(failure instanceof ApiError && failure.status === 401
        ? 'Organização, email ou senha inválidos.' : errorMessage(failure));
    } finally { setBusy(false); }
  }

  return <section className="auth-card" aria-labelledby="auth-title">
    <p className="eyebrow">SEU ESPAÇO DE MONITORAMENTO</p>
    <h2 id="auth-title">{register ? 'Crie sua organização' : 'Bem-vindo de volta'}</h2>
    <p>{register ? 'Seu primeiro usuário será o proprietário da organização.' : 'Entre para gerenciar os monitores da sua organização.'}</p>
    <form onSubmit={(event) => void submit(event)}>
      <fieldset disabled={busy}>
        {register && <><label>Seu nome<input name="name" autoComplete="name" maxLength={100} required /></label>
          <label>Nome da organização<input name="tenant_name" maxLength={100} required /></label></>}
        <label>Identificador da organização<input name="tenant_slug" autoComplete="organization" placeholder="minha-empresa" pattern="[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?" maxLength={63} required /></label>
        <small>Letras minúsculas, números e hífens. Use este identificador no login.</small>
        <label>Email<input name="email" type="email" autoComplete="username" maxLength={254} required /></label>
        <label>Senha<input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 15 : 1} maxLength={128} required /></label>
        {register && <small>Use pelo menos 15 caracteres. Espaços e frases são permitidos.</small>}
        {error && <p role="alert" className="notice error">{error}</p>}
        <button className="primary full" type="submit">{busy ? 'Aguarde…' : register ? 'Criar organização' : 'Entrar'}</button>
      </fieldset>
    </form>
    <button className="text-button" onClick={() => { setRegister(!register); setError(''); }} disabled={busy}>
      {register ? 'Já tenho uma conta' : 'Criar uma organização'}
    </button>
  </section>;
}
