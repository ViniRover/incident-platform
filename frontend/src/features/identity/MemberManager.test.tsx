import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { identityGateway, session } from '../../test/fixtures';
import { MemberManager } from './MemberManager';

describe('MemberManager', () => {
  it('does not offer administrator promotion to an administrator', async () => {
    const gateway = identityGateway();
    vi.mocked(gateway.members).mockResolvedValue([{ id: 'operator', name: 'Operator', email: 'operator@example.com', role: 'operator', is_active: true }]);
    render(<MemberManager gateway={gateway} session={{ ...session, role: 'admin' }} />);
    await screen.findByText('Operator');
    expect(screen.queryByRole('option', { name: 'admin' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Permissão de Operator')).toHaveValue('operator');
  });

  it('creates a member through the injected gateway using the session CSRF token', async () => {
    const gateway = identityGateway();
    vi.mocked(gateway.addMember).mockResolvedValue({ id: 'new', name: 'Reader', email: 'reader@example.com', role: 'viewer', is_active: true });
    render(<MemberManager gateway={gateway} session={session} />);
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Reader' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader@example.com' } });
    fireEvent.change(screen.getByLabelText('Senha inicial'), { target: { value: 'a long initial passphrase' } });
    fireEvent.click(screen.getByRole('button', { name: 'Adicionar membro' }));
    await waitFor(() => expect(gateway.addMember).toHaveBeenCalledWith({ name: 'Reader', email: 'reader@example.com', password: 'a long initial passphrase', role: 'viewer' }, 'csrf'));
    expect(await screen.findByRole('status')).toHaveTextContent('Membro criado');
  });
});
