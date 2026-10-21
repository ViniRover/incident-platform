import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../shared/api/client';
import { monitor, monitorGateway, session } from '../../test/fixtures';
import { MonitorDashboard } from './MonitorDashboard';

describe('MonitorDashboard', () => {
  it('shows a read-only list to viewers', async () => {
    const gateway = monitorGateway();
    render(<MonitorDashboard gateway={gateway} session={{ ...session, role: 'viewer' }} />);
    expect(await screen.findByText('Store')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Novo monitor/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remover' })).not.toBeInTheDocument();
  });

  it('creates a monitor and refreshes the list', async () => {
    const gateway = monitorGateway();
    render(<MonitorDashboard gateway={gateway} session={session} />);
    await screen.findByText('Store');
    fireEvent.click(screen.getByRole('button', { name: /Novo monitor/ }));
    fireEvent.change(screen.getByLabelText('Nome do monitor'), { target: { value: 'API' } });
    fireEvent.change(screen.getByLabelText('URL pública'), { target: { value: 'https://api.example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar monitor' }));
    await waitFor(() => expect(gateway.create).toHaveBeenCalledWith(expect.objectContaining({ name: 'API', url: 'https://api.example.com', is_active: true }), 'csrf'));
    expect(await screen.findByText('Monitor salvo.')).toBeInTheDocument();
  });

  it('keeps edits visible on a stale-version conflict', async () => {
    const gateway = monitorGateway();
    vi.mocked(gateway.update).mockRejectedValue(new ApiError(409, 'Reload'));
    render(<MonitorDashboard gateway={gateway} session={session} />);
    await screen.findByText('Store');
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }));
    fireEvent.change(screen.getByLabelText('Nome do monitor'), { target: { value: 'Unsaved edit' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar monitor' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Atualize a lista');
    expect(screen.getByLabelText('Nome do monitor')).toHaveValue('Unsaved edit');
  });

  it('requires confirmation before deleting and includes session CSRF', async () => {
    const gateway = monitorGateway();
    render(<MonitorDashboard gateway={gateway} session={session} />);
    await screen.findByText('Store');
    fireEvent.click(screen.getByRole('button', { name: 'Remover' }));
    expect(gateway.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar remoção' }));
    await waitFor(() => expect(gateway.remove).toHaveBeenCalledWith(monitor, 'csrf'));
  });

  it('paginates the bounded list', async () => {
    const gateway = monitorGateway();
    vi.mocked(gateway.list).mockResolvedValueOnce(Array.from({ length: 20 }, (_, i) => ({ ...monitor, id: String(i), name: `Monitor ${i}` }))).mockResolvedValue([]);
    render(<MonitorDashboard gateway={gateway} session={session} />);
    await screen.findByText('Monitor 0');
    fireEvent.click(screen.getByRole('button', { name: 'Próxima' }));
    await waitFor(() => expect(gateway.list).toHaveBeenLastCalledWith(20, expect.any(AbortSignal)));
    expect(await screen.findByText('Fim da lista')).toBeInTheDocument();
  });
});
