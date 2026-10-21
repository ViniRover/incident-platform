import { useCallback, useEffect, useState } from 'react';
import type { HealthGateway, HealthReport } from '../model/HealthGateway';

export type HealthState =
  | { kind: 'loading' }
  | { kind: 'success'; report: HealthReport }
  | { kind: 'error'; message: string };

export function useSystemHealth(gateway: HealthGateway) {
  const [state, setState] = useState<HealthState>({ kind: 'loading' });
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => {
    setState({ kind: 'loading' });
    setRevision((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    let active = true;
    // Each request owns its cancellation and cannot update an unmounted screen.
    void gateway.check(controller.signal).then(
      (report) => { if (active) setState({ kind: 'success', report }); },
      () => { if (active) setState({ kind: 'error', message: 'Não foi possível consultar a API.' }); },
    ).finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [gateway, revision]);

  return { state, refresh };
}
