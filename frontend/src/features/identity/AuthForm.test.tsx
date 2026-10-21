import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../shared/api/client';
import { identityGateway, session } from '../../test/fixtures';
import { AuthForm } from './AuthForm';

function fill(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }

describe('AuthForm', () => {
  it('logs in using tenant credentials without persisting the session token in browser storage', async () => {
    const gateway = identityGateway();
    const authenticated = vi.fn();
    render(<AuthForm gateway={gateway} onAuthenticated={authenticated} />);
    fill('Identificador da organização', 'acme'); fill('Email', 'owner@example.com'); fill('Senha', 'a long passphrase');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    await waitFor(() => expect(authenticated).toHaveBeenCalledWith(session));
    expect(gateway.login).toHaveBeenCalledWith({ tenant_slug: 'acme', email: 'owner@example.com', password: 'a long passphrase' });
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('shows an authentication error and allows retry', async () => {
    const gateway = identityGateway();
    vi.mocked(gateway.login).mockRejectedValueOnce(new ApiError(401, 'Invalid credentials'));
    render(<AuthForm gateway={gateway} onAuthenticated={vi.fn()} />);
    fill('Identificador da organização', 'acme'); fill('Email', 'owner@example.com'); fill('Senha', 'wrong');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Organização, email ou senha inválidos.');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled();
  });

  it('registers an organization with its owner', async () => {
    const gateway = identityGateway();
    render(<AuthForm gateway={gateway} onAuthenticated={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Criar uma organização' }));
    fill('Seu nome', 'Owner'); fill('Nome da organização', 'Acme'); fill('Identificador da organização', 'acme');
    fill('Email', 'owner@example.com'); fill('Senha', 'a long passphrase');
    fireEvent.click(screen.getByRole('button', { name: 'Criar organização' }));
    await waitFor(() => expect(gateway.register).toHaveBeenCalledWith(expect.objectContaining({ name: 'Owner', tenant_name: 'Acme' })));
  });
});
