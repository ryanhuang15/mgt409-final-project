import React from "react";
import {
  BarChart,
  Bar,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Info } from "lucide-react";
import { money, human } from "./ui.jsx";

export default function PremiumChart({ envelope, onEvidence }) {
  const analytics = envelope.analytics;
  if (!analytics) return null;
  const rows = analytics.segments
    .map((row) => ({
      ...row,
      contribution: Number(row.premium_contribution_usd),
    }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 12);
  return (
    <section className="panel premium-contribution">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">PREMIUM CONTRIBUTION</p>
          <h2>Where the premium dollars move</h2>
        </div>
        <strong className="rose-text">
          {money(analytics.premium_change_usd)}
        </strong>
      </div>
      {analytics.status === "available" ? (
        <>
          <p className="small-text muted">
            Portfolio premium change at fixed exposures ·{" "}
            {Number(analytics.total_exposure).toLocaleString()} annual vehicle
            exposures. Showing up to 12 largest absolute dollar contributions;
            all segments remain in the exhibit below.
          </p>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rows}
                margin={{ left: 18, right: 15, top: 12, bottom: 8 }}
              >
                <CartesianGrid stroke="#262a34" vertical={false} />
                <XAxis
                  dataKey="segment_id"
                  tick={{ fill: "#97a5bd", fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tickFormatter={(value) =>
                    Number(value).toLocaleString("en-US", {
                      notation: "compact",
                      style: "currency",
                      currency: "USD",
                    })
                  }
                  tick={{ fill: "#97a5bd", fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ fill: "#ffffff05" }}
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="chart-tooltip">
                        <strong>{payload[0].payload.segment_id}</strong>
                        <div>
                          Premium contribution <b>{money(payload[0].value)}</b>
                        </div>
                      </div>
                    ) : null
                  }
                />
                <Bar
                  dataKey="contribution"
                  maxBarSize={32}
                  radius={[3, 3, 0, 0]}
                  isAnimationActive={false}
                  onClick={(row) => onEvidence(`calc:${row.segment_id}`)}
                  cursor="pointer"
                >
                  {rows.map((row) => (
                    <Cell
                      key={row.segment_id}
                      fill={row.contribution < 0 ? "#8cd3b4" : "#9f98c9"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="chart-note">
            Calculated in Python: exposure × change in modeled rate. Select a
            bar to inspect its rate inputs. Dollar contributions are distinct
            from percentage rate changes.
          </p>
        </>
      ) : (
        <div className="notice warning">
          <Info size={18} />
          <p>
            Premium contributions are unavailable: {human(analytics.reason)}. No
            weights were substituted.
          </p>
        </div>
      )}
    </section>
  );
}
