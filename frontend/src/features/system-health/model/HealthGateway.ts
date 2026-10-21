export type HealthReport = {
  status: 'ok' | 'unavailable';
  checks: Record<string, boolean>;
};

export interface HealthGateway {
  check(signal: AbortSignal): Promise<HealthReport>;
}
