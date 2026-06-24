"use client"

type HorizonSliderProps = {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
}

export function HorizonSlider({
  value,
  onChange,
  min = 1,
  max = 60,
}: HorizonSliderProps) {
  const pct = ((value - min) / (max - min)) * 100

  return (
    <section
      aria-label="Forecast horizon selector"
      className="rounded-xl border border-border bg-card p-5"
    >
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            Forecast Horizon
          </p>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="font-mono text-3xl font-semibold tabular-nums text-primary">
              {value}
            </span>
            <span className="text-sm text-muted-foreground">
              {value === 1 ? "day" : "days"}
            </span>
          </p>
        </div>
        <p className="text-right text-xs text-muted-foreground">
          Drag to project
          <br />
          {min}–{max} days ahead
        </p>
      </div>

      <div className="relative py-2">
        <div className="relative h-2 w-full rounded-full bg-secondary">
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-primary"
            style={{ width: `${pct}%` }}
          />
        </div>
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label="Forecast horizon in days"
          aria-valuetext={`${value} days`}
          className="horizon-range absolute inset-0 h-full w-full cursor-pointer appearance-none bg-transparent"
        />
      </div>

      <div className="mt-2 flex justify-between text-[11px] font-medium text-muted-foreground">
        {[1, 14, 30, 45, 60].map((tick) => (
          <span key={tick}>{tick}d</span>
        ))}
      </div>

      <style jsx>{`
        .horizon-range::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          height: 22px;
          width: 22px;
          border-radius: 9999px;
          background: var(--primary);
          border: 3px solid var(--card);
          box-shadow: 0 0 0 1px var(--primary);
          cursor: pointer;
          margin-top: 0;
        }
        .horizon-range::-moz-range-thumb {
          height: 22px;
          width: 22px;
          border-radius: 9999px;
          background: var(--primary);
          border: 3px solid var(--card);
          box-shadow: 0 0 0 1px var(--primary);
          cursor: pointer;
        }
        .horizon-range:focus-visible::-webkit-slider-thumb {
          box-shadow: 0 0 0 4px color-mix(in oklch, var(--primary) 35%, transparent);
        }
      `}</style>
    </section>
  )
}
