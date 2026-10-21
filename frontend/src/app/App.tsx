import { SystemHealth, createHealthGateway } from '../features/system-health';
import { PageLayout } from '../shared/ui/PageLayout';

const healthGateway = createHealthGateway();

export function App() {
  return (
    <PageLayout>
      <header>
        <p className="eyebrow">PULSE / M0</p>
        <h1>Uma base para observar.</h1>
        <p>Preparação da plataforma de monitoramento de disponibilidade e incidentes.</p>
      </header>
      <SystemHealth gateway={healthGateway} />
      <p className="footnote">Cadastro de monitores e autenticação serão implementados no M1.</p>
    </PageLayout>
  );
}
