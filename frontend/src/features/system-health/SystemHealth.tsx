import { HealthPanel } from './components/HealthPanel';
import { useSystemHealth } from './hooks/useSystemHealth';
import type { HealthGateway } from './model/HealthGateway';

export function SystemHealth({ gateway }: { gateway: HealthGateway }) {
  const { state, refresh } = useSystemHealth(gateway);
  return <HealthPanel state={state} onRefresh={refresh} />;
}
