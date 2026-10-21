import { useEffect, useState, type FormEvent } from 'react';
import { errorMessage, type Member, type Role, type SessionInfo } from '../../shared/api/client';
import type { IdentityGateway } from './gateway';

export function MemberManager({ gateway, session }: { gateway: IdentityGateway; session: SessionInfo }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [offset, setOffset] = useState(0);
  const roles: Role[] = session.role === 'owner' ? ['admin', 'operator', 'viewer'] : ['operator', 'viewer'];
  useEffect(() => {
    const controller = new AbortController();
    void gateway.members(offset, controller.signal).then((rows) => {
      if (!controller.signal.aborted) setMembers(rows);
    }, (failure) => {
      if (!controller.signal.aborted) setError(errorMessage(failure));
    });
    return () => controller.abort();
  }, [gateway, revision, offset]);

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true); setError(''); setMessage('');
    try {
      await gateway.addMember({ name: String(fields.get('name')), email: String(fields.get('email')),
        password: String(fields.get('password')), role: fields.get('role') as Role }, session.csrf_token);
      form.reset(); setRevision((value) => value + 1); setMessage('Membro criado. Compartilhe a senha por um canal seguro.');
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  }

  async function update(member: Member, role: Role, active: boolean) {
    setBusy(true); setError(''); setMessage('');
    try {
      await gateway.updateMember(member.id, role, active, session.csrf_token);
      setRevision((value) => value + 1); setMessage('Acesso atualizado. As sessões anteriores do membro foram encerradas.');
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  }

  return <section aria-labelledby="members-title">
    <h2 id="members-title">Pessoas e permissões</h2>
    <p>Admin gerencia membros e monitores; operator gerencia monitores; viewer apenas consulta.</p>
    {error && <p role="alert" className="notice error">{error}</p>}
    {message && <p role="status" className="notice">{message}</p>}
    <div className="member-list">{members.map((member) => {
      const editable = member.role !== 'owner' && (session.role === 'owner' || member.role !== 'admin');
      return <article className="member-row" key={member.id}>
        <div><strong>{member.name}</strong><small>{member.email}</small></div>
        <span className="badge">{member.is_active ? 'Ativo' : 'Desativado'}</span>
        {editable ? <>
          <label className="compact">Permissão de {member.name}<select value={member.role} disabled={busy}
            onChange={(event) => void update(member, event.target.value as Role, member.is_active)}>
            {roles.map((role) => <option key={role}>{role}</option>)}
          </select></label>
          <button className="secondary" disabled={busy} onClick={() => void update(member, member.role, !member.is_active)}>{member.is_active ? 'Desativar' : 'Reativar'}</button>
        </> : <span className="badge">{member.role}</span>}
      </article>;
    })}</div>
    <nav className="pagination" aria-label="Paginação de membros">
      <button className="secondary" disabled={offset === 0 || busy} onClick={() => setOffset(Math.max(0, offset - 20))}>Anterior</button>
      <span>Página {Math.floor(offset / 20) + 1}</span>
      <button className="secondary" disabled={members.length < 20 || busy} onClick={() => setOffset(offset + 20)}>Próxima</button>
    </nav>
    <form className="surface" onSubmit={(event) => void add(event)}>
      <h3>Adicionar membro</h3>
      <fieldset disabled={busy} className="form-grid">
        <label>Nome<input name="name" required maxLength={100} /></label>
        <label>Email<input name="email" type="email" required maxLength={254} /></label>
        <label>Senha inicial<input name="password" type="password" autoComplete="new-password" minLength={15} maxLength={128} required /></label>
        <label>Permissão<select name="role" defaultValue="viewer">{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
        <button className="primary" type="submit">Adicionar membro</button>
      </fieldset>
    </form>
  </section>;
}
