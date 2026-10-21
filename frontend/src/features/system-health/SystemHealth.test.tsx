import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SystemHealth } from './SystemHealth';
import { createHealthGateway } from './api/httpHealthGateway';
import type { HealthGateway } from './model/HealthGateway';

describe('SystemHealth', () => {
  it('uses the injected gateway and allows recovery after a network failure', async () => {
    const check = vi.fn<HealthGateway['check']>()
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue({ status: 'ok', checks: { postgres: true, redis: true } });
    render(<SystemHealth gateway={{ check }} />);
    expect(await screen.findByText('Não foi possível consultar a API.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Verificar novamente' }));
    expect(await screen.findByText('Plataforma disponível')).toBeInTheDocument();
    expect(check).toHaveBeenCalledTimes(2);
  });

  it('renders real HTTP adapter data including a 503 dependency failure', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      status: 'unavailable', checks: { postgres: true, redis: false },
    }), { status: 503 }));
    render(<SystemHealth gateway={createHealthGateway(fetcher)} />);
    expect(await screen.findByText('Dependências indisponíveis')).toBeInTheDocument();
    expect(screen.getByText('Indisponível')).toBeInTheDocument();
    await waitFor(() => expect(fetcher).toHaveBeenCalledOnce());
  });

  it('rejects malformed API data', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('{"checks":42}'));
    await expect(createHealthGateway(fetcher).check(new AbortController().signal))
      .rejects.toThrow('Resposta inválida');
  });

  it('cancels requests on unmount', () => {
    let signal: AbortSignal | undefined;
    const { unmount } = render(<SystemHealth gateway={{ check: (input) => {
      signal = input;
      return new Promise(() => {});
    } }} />);
    unmount();
    expect(signal?.aborted).toBe(true);
  });
});
