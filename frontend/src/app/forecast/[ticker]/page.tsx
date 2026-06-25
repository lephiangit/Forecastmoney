import type { Metadata } from "next"
import { ForecastDetail } from "@/components/forecast/forecast-detail"

type Params = { ticker: string }

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>
}): Promise<Metadata> {
  const { ticker } = await params
  const upperTicker = ticker.toUpperCase()
  return {
    title: `${upperTicker} Forecast — AI Price Engine`,
    description: `AI price forecast, confidence bands and research for ${upperTicker}.`,
  }
}

export default async function ForecastPage({
  params,
}: {
  params: Promise<Params>
}) {
  const { ticker } = await params

  return (
    <main className="min-h-screen">
      <ForecastDetail ticker={ticker.toUpperCase()} />
    </main>
  )
}
