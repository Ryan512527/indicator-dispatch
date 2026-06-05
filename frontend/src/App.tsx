import { useState } from 'react'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { OutageDetail } from './pages/OutageDetail'
import { AIChat } from './pages/AIChat'
import { ReportDetail } from './pages/ReportDetail'
import { WirelessOutageDetail } from './pages/WirelessOutageDetail'
import { PisiteFaultDetail } from './pages/PisiteFaultDetail'
import { AccessLayerFaultDetail } from './pages/AccessLayerFaultDetail'
import { EnterpriseBroadbandBacklog } from './pages/EnterpriseBroadbandBacklog'
import { DailyReportDetail } from './pages/DailyReportDetail'
import type { Page } from './types'


export default function App() {
  const [page, setPage] = useState<Page>({ name: 'dashboard' })

  return (
    <Layout
      currentPath={
        page.name === 'dashboard' ? '/dashboard' :
        page.name === 'ai-chat' ? '/ai' :
        page.name === 'report-detail' ? `/reports/${page.params?.id}` :
        page.name === 'wireless-outage-detail' ? '/wireless-outage' :
        page.name === 'pisite-fault-detail' ? '/pisite-fault' :
        page.name === 'access-layer-fault-detail' ? '/access-layer-fault' :
        page.name === 'enterprise-broadband-backlog' ? '/enterprise-broadband-backlog' :
        page.name === 'daily-report-detail' ? '/daily-report-detail' :
        ''
      }
      onNavigate={(p: string | Page) => {
        if (typeof p === 'string') {
          if (p === '/dashboard') setPage({ name: 'dashboard' })
          else if (p === '/ai') setPage({ name: 'ai-chat' })
        } else {
          setPage(p)
        }
      }}
    >
      {page.name === 'dashboard' && <Dashboard onNavigate={p => setPage(p)} />}
      {page.name === 'detail' && <OutageDetail params={page.params || {}} onBack={() => setPage({ name: 'dashboard' })} />}
      {page.name === 'ai-chat' && <AIChat />}
      {page.name === 'report-detail' && <ReportDetail reportTypeId={page.params?.id || 0} />}
      {page.name === 'wireless-outage-detail' && <WirelessOutageDetail onBack={() => setPage({ name: 'dashboard' })} />}
      {page.name === 'pisite-fault-detail' && <PisiteFaultDetail onBack={() => setPage({ name: 'dashboard' })} />}
      {page.name === 'access-layer-fault-detail' && <AccessLayerFaultDetail onBack={() => setPage({ name: 'dashboard' })} />}
      {page.name === 'enterprise-broadband-backlog' && <EnterpriseBroadbandBacklog onBack={() => setPage({ name: 'dashboard' })} />}
      {page.name === 'daily-report-detail' && <DailyReportDetail onBack={() => setPage({ name: 'dashboard' })} />}
    </Layout>
  )
}
