import { apiClient, result, type ApiClient, type Monitor, type MonitorInput } from '../../shared/api/client';

export interface MonitorGateway {
  list(offset: number, signal?: AbortSignal): Promise<Monitor[]>;
  create(input: MonitorInput, csrf: string): Promise<Monitor>;
  update(monitor: Monitor, input: MonitorInput, csrf: string): Promise<Monitor>;
  remove(monitor: Monitor, csrf: string): Promise<void>;
}

export function createMonitorGateway(client: ApiClient = apiClient): MonitorGateway {
  return {
    async list(offset, signal) {
      const { data, error, response } = await client.GET('/api/v1/monitors', { params: { query: { offset, limit: 20 } }, signal });
      return result(data, error, response);
    },
    async create(body, csrf) {
      const { data, error, response } = await client.POST('/api/v1/monitors', { body, headers: { 'X-CSRF-Token': csrf } });
      return result(data, error, response);
    },
    async update(monitor, input, csrf) {
      const { data, error, response } = await client.PUT('/api/v1/monitors/{monitor_id}', {
        params: { path: { monitor_id: monitor.id } }, body: { ...input, config_version: monitor.config_version },
        headers: { 'X-CSRF-Token': csrf },
      });
      return result(data, error, response);
    },
    async remove(monitor, csrf) {
      const { error, response } = await client.DELETE('/api/v1/monitors/{monitor_id}', {
        params: { path: { monitor_id: monitor.id }, query: { config_version: monitor.config_version } },
        headers: { 'X-CSRF-Token': csrf },
      });
      result(undefined, error, response);
    },
  };
}
