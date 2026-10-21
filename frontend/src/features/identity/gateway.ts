import { apiClient, result, type ApiClient, type SessionInfo, type Member, type Role } from '../../shared/api/client';

export type LoginInput = { tenant_slug: string; email: string; password: string };
export type RegisterInput = LoginInput & { tenant_name: string; name: string };
export type NewMember = { name: string; email: string; password: string; role: Role };

export interface IdentityGateway {
  me(signal?: AbortSignal): Promise<SessionInfo>;
  login(input: LoginInput): Promise<SessionInfo>;
  register(input: RegisterInput): Promise<SessionInfo>;
  logout(csrf: string): Promise<void>;
  members(offset: number, signal?: AbortSignal): Promise<Member[]>;
  addMember(input: NewMember, csrf: string): Promise<Member>;
  updateMember(id: string, role: Role, isActive: boolean, csrf: string): Promise<Member>;
}

export function createIdentityGateway(client: ApiClient = apiClient): IdentityGateway {
  return {
    async me(signal) {
      const { data, error, response } = await client.GET('/api/v1/auth/me', { signal });
      return result(data, error, response);
    },
    async login(body) {
      const { data, error, response } = await client.POST('/api/v1/auth/login', { body });
      return result(data, error, response);
    },
    async register(body) {
      const { data, error, response } = await client.POST('/api/v1/auth/register', { body });
      return result(data, error, response);
    },
    async logout(csrf) {
      const { error, response } = await client.POST('/api/v1/auth/logout', { headers: { 'X-CSRF-Token': csrf } });
      result(undefined, error, response);
    },
    async members(offset, signal) {
      const { data, error, response } = await client.GET('/api/v1/members', { signal, params: { query: { offset, limit: 20 } } });
      return result(data, error, response);
    },
    async addMember(body, csrf) {
      const { data, error, response } = await client.POST('/api/v1/members', { body, headers: { 'X-CSRF-Token': csrf } });
      return result(data, error, response);
    },
    async updateMember(id, role, isActive, csrf) {
      const { data, error, response } = await client.PATCH('/api/v1/members/{user_id}', {
        params: { path: { user_id: id } }, body: { role, is_active: isActive }, headers: { 'X-CSRF-Token': csrf },
      });
      return result(data, error, response);
    },
  };
}
