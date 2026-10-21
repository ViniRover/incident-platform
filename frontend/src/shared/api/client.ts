import createClient from 'openapi-fetch';
import type { paths, components } from './schema';

export type SessionInfo = components['schemas']['SessionResponse'];
export type Monitor = components['schemas']['MonitorResponse'];
export type MonitorInput = components['schemas']['MonitorInput'];
export type Member = components['schemas']['MemberResponse'];
export type Role = components['schemas']['Role'];

export const apiClient = createClient<paths>({
  credentials: 'same-origin',
  fetch: (request) => fetch(request, {
    signal: AbortSignal.any([request.signal, AbortSignal.timeout(12000)]),
  }),
});
export type ApiClient = typeof apiClient;

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

export function result<T>(data: T | undefined, error: unknown, response: Response): T {
  if (!response.ok) {
    const detail = error && typeof error === 'object' && 'detail' in error ? error.detail : null;
    throw new ApiError(response.status, typeof detail === 'string' ? detail : 'Verifique os dados e tente novamente.');
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Sua sessão expirou. Entre novamente.';
    if (error.status === 403) return 'Você não tem permissão para esta ação. Atualize a página se seu acesso mudou.';
    if (error.status === 409) return 'Os dados já existem ou foram alterados. Atualize a lista antes de salvar novamente.';
    if (error.status === 429) return 'Muitas tentativas. Aguarde um minuto e tente novamente.';
    if (error.status === 503) return 'Serviço temporariamente indisponível. Tente novamente em instantes.';
    return error.message;
  }
  return 'Não foi possível conectar à API. Verifique sua conexão e tente novamente.';
}
