import type { HealthGateway, HealthReport } from '../model/HealthGateway';

function isHealthReport(value: unknown): value is HealthReport {
  if (!value || typeof value !== 'object') return false;
  const report = value as Record<string, unknown>;
  return (report.status === 'ok' || report.status === 'unavailable')
    && !!report.checks && typeof report.checks === 'object' && !Array.isArray(report.checks)
    && Object.values(report.checks).every((item) => typeof item === 'boolean');
}

export function createHealthGateway(fetcher: typeof fetch = fetch): HealthGateway {
  return {
    async check(signal) {
      const response = await fetcher('/api/v1/health/ready', { signal });
      if (!response.ok && response.status !== 503) throw new Error('Falha ao consultar a API.');
      const report: unknown = await response.json();
      if (!isHealthReport(report)) throw new Error('Resposta inválida da API.');
      return report;
    },
  };
}
