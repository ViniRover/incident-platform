import createClient from 'openapi-fetch';
import { describe, expect, it, vi } from 'vitest';
import type { paths } from './schema';
import { ApiError, errorMessage } from './client';
import { createMonitorGateway } from '../../features/monitors';
import { monitor } from '../../test/fixtures';

describe('generated API client', () => {
  it('sends the monitor version and CSRF token using the generated contract', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(monitor), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const client = createClient<paths>({ baseUrl: 'http://localhost', fetch: fetcher });
    const gateway = createMonitorGateway(client);
    await gateway.update(monitor, { name: 'Changed', url: monitor.url }, 'anti-csrf');
    const request = fetcher.mock.calls[0][0] as Request;
    expect(request.url).toBe('http://localhost/api/v1/monitors/monitor-id');
    expect(request.headers.get('X-CSRF-Token')).toBe('anti-csrf');
    expect(await request.json()).toEqual({ name: 'Changed', url: monitor.url, config_version: 1 });
  });

  it('turns HTTP authentication errors into typed application errors', async () => {
    const client = createClient<paths>({ baseUrl: 'http://localhost', fetch: vi.fn().mockResolvedValue(new Response('{"detail":"Authentication required"}', { status: 401, headers: { 'Content-Type': 'application/json' } })) });
    await expect(createMonitorGateway(client).list(0)).rejects.toBeInstanceOf(ApiError);
    expect(errorMessage(new ApiError(401, ''))).toContain('sessão expirou');
    expect(errorMessage(new Error('offline'))).toContain('conectar');
  });
});
