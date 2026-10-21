import { vi } from 'vitest';
import type { IdentityGateway } from '../features/identity';
import type { MonitorGateway } from '../features/monitors';
import type { Monitor, SessionInfo } from '../shared/api/client';

export const session: SessionInfo = { user_id: 'owner-id', tenant_id: 'tenant-a', tenant_name: 'Acme',
  tenant_slug: 'acme', name: 'Owner', email: 'owner@example.com', role: 'owner', csrf_token: 'csrf' };

export const monitor: Monitor = { id: 'monitor-id', tenant_id: 'tenant-a', name: 'Store',
  url: 'https://example.com/', interval_seconds: 60, timeout_seconds: 10, expected_status: 200,
  is_active: true, config_version: 1, created_at: '2026-10-21T12:00:00Z', updated_at: '2026-10-21T12:00:00Z' };

export function identityGateway(): IdentityGateway {
  return { me: vi.fn().mockResolvedValue(session), login: vi.fn().mockResolvedValue(session),
    register: vi.fn().mockResolvedValue(session), logout: vi.fn().mockResolvedValue(undefined),
    members: vi.fn().mockResolvedValue([]), addMember: vi.fn(), updateMember: vi.fn() };
}

export function monitorGateway(): MonitorGateway {
  return { list: vi.fn().mockResolvedValue([monitor]), create: vi.fn().mockResolvedValue(monitor),
    update: vi.fn().mockResolvedValue(monitor), remove: vi.fn().mockResolvedValue(undefined) };
}
