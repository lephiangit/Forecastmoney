import { notFound } from "next/navigation"
import type { Metadata } from "next"
import { getAsset } from "@/lib/forecast-data"
import { ForecastDetail } from "@/components/forecast/forecast-detail"

type Params = { ticker: string }

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>
}): Promise<Metadata> {
  const { ticker } = await params
  const asset = getAsset(ticker)
  if (!asset) return { title: "Asset not found" }
  return {
    title: `${asset.ticker} Forecast — ${asset.name}`,
    description: `AI price forecast, confidence bands and research for ${asset.name} (${asset.ticker}).`,
  }
}

export default async function ForecastPage({
  params,
}: {
  params: Promise<Params>
}) {
  const { ticker } = await params
  const asset = getAsset(ticker)
  if (!asset) notFound()

  return (
    <main className="min-h-screen">
      <ForecastDetail asset={asset} />
    </main>
  )
}
