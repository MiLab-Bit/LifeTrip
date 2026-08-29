import { useCallback, useState } from "react";
import { BriefStage } from "./components/BriefStage";
import { DoneStage } from "./components/DoneStage";
import { LoadingStage } from "./components/LoadingStage";
import { MetroShell } from "./components/MetroShell";
import { RouteStage } from "./components/RouteStage";
import { WalkStage } from "./components/WalkStage";
import { planRoute } from "./lib/api";
import type { AppStage, BriefInput, LifeRoute } from "./types";
import "./styles/tokens.css";
import "./styles/metro.css";

const DEFAULT_BRIEF: BriefInput = {
  vibe: "neon",
  districtId: "anfu-wukang",
  durationMin: 90,
  pace: "normal",
};

export default function App() {
  const [stage, setStage] = useState<AppStage>("brief");
  const [brief, setBrief] = useState<BriefInput>(DEFAULT_BRIEF);
  const [route, setRoute] = useState<LifeRoute | null>(null);
  const [stopIndex, setStopIndex] = useState(0);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lineMeta = route
    ? { code: route.lineCode, label: route.lineName }
    : { code: undefined, label: undefined };

  const startCurate = useCallback(async () => {
    setError(null);
    setPlanning(true);
    setStage("loading");
    try {
      const planned = await planRoute(brief);
      setRoute(planned);
      setStopIndex(0);
      setStage("route");
    } catch (e) {
      setError(e instanceof Error ? e.message : "规划失败");
      setStage("brief");
    } finally {
      setPlanning(false);
    }
  }, [brief]);

  const restart = () => {
    setRoute(null);
    setStopIndex(0);
    setStage("brief");
    setError(null);
  };

  return (
    <MetroShell lineCode={lineMeta.code} lineLabel={lineMeta.label}>
      {stage === "brief" ? (
        <BriefStage
          value={brief}
          onChange={setBrief}
          onSubmit={() => void startCurate()}
          loading={planning}
          error={error}
        />
      ) : null}

      {stage === "loading" ? (
        <LoadingStage lineCode="L-??" title="正在拉取 OSM 实点并规划步行…" />
      ) : null}

      {stage === "route" && route ? (
        <RouteStage
          route={route}
          activeStopIndex={stopIndex}
          onSelectStop={setStopIndex}
          onStartWalk={() => setStage("walk")}
        />
      ) : null}

      {stage === "walk" && route ? (
        <WalkStage
          route={route}
          stopIndex={stopIndex}
          onPrev={() => setStopIndex((i) => Math.max(0, i - 1))}
          onNext={() =>
            setStopIndex((i) => Math.min(route.stops.length - 1, i + 1))
          }
          onFinish={() => setStage("done")}
        />
      ) : null}

      {stage === "done" && route ? (
        <DoneStage
          lineCode={route.lineCode}
          title={route.title}
          onRestart={restart}
        />
      ) : null}
    </MetroShell>
  );
}
