import { useCallback, useEffect, useState } from "react";
import { BriefStage } from "./components/BriefStage";
import { ConfirmStage } from "./components/ConfirmStage";
import { DoneStage } from "./components/DoneStage";
import { LoadingStage } from "./components/LoadingStage";
import { MetroShell } from "./components/MetroShell";
import { ResumeBanner } from "./components/ResumeBanner";
import { RouteStage } from "./components/RouteStage";
import { WalkStage } from "./components/WalkStage";
import {
  advanceWalk,
  applyReroute,
  completeWalk,
  fetchProactive,
  planWalk,
  rerollWalk,
  resumeWalk,
  skipWalk,
  startWalk,
} from "./lib/api";
import type { AppStage, BriefInput, PendingAction, RerouteProposal, RouteEnvelope, WalkTask } from "./types";
import "./styles/tokens.css";
import "./styles/metro.css";

const DEFAULT_BRIEF: BriefInput = {
  vibe: "coffee",
  districtId: "anfu-wukang",
  durationMin: 90,
  pace: "normal",
  intentText: "今晚安福咖啡慢逛 90 分钟",
};

export default function App() {
  const [stage, setStage] = useState<AppStage>("brief");
  const [brief, setBrief] = useState<BriefInput>(DEFAULT_BRIEF);
  const [task, setTask] = useState<WalkTask | null>(null);
  const [resumable, setResumable] = useState<WalkTask | null>(null);
  const [proposal, setProposal] = useState<RerouteProposal | null>(null);
  const [planning, setPlanning] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const route: RouteEnvelope | null = task?.route ?? null;
  const stopIndex = task?.current_stop_index ?? 0;
  const pending = task?.pending_action ?? null;

  const lineMeta = route
    ? { code: route.lineCode, label: route.lineName }
    : { code: undefined, label: undefined };

  useEffect(() => {
    resumeWalk().then(setResumable).catch(() => setResumable(null));
  }, []);

  const syncTask = useCallback((next: WalkTask) => {
    setTask(next);
    if (next.pending_action) {
      setStage("confirm");
    }
  }, []);

  const startCurate = useCallback(async () => {
    setError(null);
    setPlanning(true);
    setStage("loading");
    setResumable(null);
    try {
      const result = await planWalk(brief);
      syncTask(result.task);
      if (result.resumed) {
        setStage(result.task.status === "walking" ? "walk" : "route");
      } else {
        setStage("route");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "规划失败");
      setStage("brief");
    } finally {
      setPlanning(false);
    }
  }, [brief, syncTask]);

  const handleResume = () => {
    if (!resumable) return;
    setTask(resumable);
    setResumable(null);
    setStage(resumable.status === "walking" ? "walk" : "route");
  };

  const handleStartWalk = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      const next = await startWalk(task.id);
      syncTask(next);
      setStage("walk");
      const p = await fetchProactive(next.id);
      setProposal(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "开走失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleNext = async () => {
    if (!task || !route) return;
    if (stopIndex >= route.stops.length - 1) return;
    setActionLoading(true);
    try {
      const next = await advanceWalk(task.id);
      syncTask(next);
      const p = await fetchProactive(next.id);
      setProposal(p);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSkip = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      syncTask(await skipWalk(task.id, false));
    } finally {
      setActionLoading(false);
    }
  };

  const handleReroll = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      syncTask(await rerollWalk(task.id, false));
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirm = async (action: PendingAction) => {
    if (!task) return;
    setActionLoading(true);
    try {
      let next = task;
      if (action.kind === "skip") {
        next = await skipWalk(task.id, true);
      } else if (action.kind === "reroll") {
        next = await rerollWalk(task.id, true);
      } else if (action.kind === "apply_reroute" && proposal) {
        next = await applyReroute(task.id, proposal.proposed_route, true);
        setProposal(null);
      }
      syncTask(next);
      setStage("walk");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelConfirm = async () => {
    setStage(task?.status === "walking" ? "walk" : "route");
    if (task) {
      setTask({ ...task, pending_action: null });
    }
  };

  const handleApplyProposal = async () => {
    if (!task || !proposal) return;
    setActionLoading(true);
    try {
      const next = await applyReroute(task.id, proposal.proposed_route, false);
      syncTask(next);
    } finally {
      setActionLoading(false);
    }
  };

  const handleFinish = async () => {
    if (!task) return;
    setActionLoading(true);
    try {
      await completeWalk(task.id);
      setStage("done");
    } finally {
      setActionLoading(false);
    }
  };

  const restart = () => {
    setTask(null);
    setProposal(null);
    setStage("brief");
    setError(null);
    resumeWalk().then(setResumable).catch(() => setResumable(null));
  };

  return (
    <MetroShell lineCode={lineMeta.code} lineLabel={lineMeta.label}>
      {stage === "brief" && resumable ? (
        <ResumeBanner task={resumable} onResume={handleResume} onDismiss={() => setResumable(null)} />
      ) : null}

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
        <LoadingStage lineCode="L-??" title="正在理解任务、拉取 POI 并规划步行…" />
      ) : null}

      {stage === "route" && route && task ? (
        <RouteStage
          route={route}
          activeStopIndex={stopIndex}
          onSelectStop={() => {}}
          onStartWalk={() => void handleStartWalk()}
          startLoading={actionLoading}
        />
      ) : null}

      {stage === "walk" && route && task ? (
        <>
          {proposal ? (
            <aside className="proactive-banner" role="alert">
              <p>{proposal.message}</p>
              <button
                type="button"
                className="metro-btn metro-btn--primary metro-btn--sm"
                onClick={() => void handleApplyProposal()}
                disabled={actionLoading}
              >
                查看改线方案
              </button>
            </aside>
          ) : null}
          <WalkStage
            route={route}
            stopIndex={stopIndex}
            onPrev={() => setTask({ ...task, current_stop_index: Math.max(0, stopIndex - 1) })}
            onNext={() => void handleNext()}
            onSkip={() => void handleSkip()}
            onReroll={() => void handleReroll()}
            onFinish={() => void handleFinish()}
            loading={actionLoading}
          />
        </>
      ) : null}

      {stage === "confirm" && pending ? (
        <ConfirmStage
          action={pending}
          onConfirm={() => void handleConfirm(pending)}
          onCancel={() => void handleCancelConfirm()}
          loading={actionLoading}
        />
      ) : null}

      {stage === "done" && route ? (
        <DoneStage
          lineCode={route.lineCode}
          title={route.title}
          verified={task?.verify_passed ?? undefined}
          onRestart={restart}
        />
      ) : null}
    </MetroShell>
  );
}
