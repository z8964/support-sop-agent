import { FormEvent, useEffect, useMemo, useState } from "react";

import "./styles.css";

type Ticket = {
  id: string;
  user_id: string;
  order_id: string | null;
  message: string;
  intent: string;
  status: string;
  risk_level: string;
  need_human_review: boolean;
  final_reply: string | null;
};

type TraceStep = {
  node: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  status: string;
};

type AgentRun = {
  ticket_id: string;
  status: string;
  intent: string;
  risk_level: string;
  need_human_review: boolean;
  decision: {
    decision?: string;
    reason?: string;
    next_actions?: string[];
    policy_refs?: Array<{ source: string; section: string }>;
  };
  final_reply: string | null;
  trace: TraceStep[];
};

type PendingReview = {
  ticket_id: string;
  message: string;
  intent: string;
  risk_level: string;
  agent_reply: string | null;
  reason: string | null;
};

type Scenario = {
  label: string;
  user_id: string;
  order_id?: string;
  message: string;
};

const scenarios: Scenario[] = [
  {
    label: "Shipped refund",
    user_id: "U1001",
    order_id: "OD2026001",
    message: "我买的耳机已经发货了，但是我现在不想要了，帮我退款。"
  },
  {
    label: "High-value refund",
    user_id: "U1003",
    order_id: "OD2026003",
    message: "这个订单我要退款"
  },
  {
    label: "Logistics no update",
    user_id: "U1004",
    order_id: "OD2026004",
    message: "我的快递三天没有更新了，什么时候能到？"
  },
  {
    label: "Invoice reissue",
    user_id: "U1005",
    order_id: "OD2026005",
    message: "发票抬头写错了，能帮我重开吗？"
  }
];

const api = {
  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      },
      ...init
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`${response.status} ${response.statusText}: ${detail}`);
    }

    return response.json() as Promise<T>;
  }
};

export function App() {
  const [userId, setUserId] = useState(scenarios[0].user_id);
  const [orderId, setOrderId] = useState(scenarios[0].order_id ?? "");
  const [message, setMessage] = useState(scenarios[0].message);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [pendingReviews, setPendingReviews] = useState<PendingReview[]>([]);
  const [reviewReply, setReviewReply] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPendingReview = useMemo(() => {
    if (!ticket) return null;
    return pendingReviews.find((item) => item.ticket_id === ticket.id) ?? null;
  }, [pendingReviews, ticket]);

  useEffect(() => {
    void loadPendingReviews();
  }, []);

  async function loadPendingReviews() {
    const response = await api.request<{ items: PendingReview[] }>(
      "/api/reviews/pending"
    );
    setPendingReviews(response.items);
  }

  function applyScenario(scenario: Scenario) {
    setUserId(scenario.user_id);
    setOrderId(scenario.order_id ?? "");
    setMessage(scenario.message);
    setTicket(null);
    setAgentRun(null);
    setReviewReply("");
    setError(null);
  }

  async function createTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setAgentRun(null);
    setReviewReply("");

    try {
      const created = await api.request<Ticket>("/api/tickets", {
        method: "POST",
        body: JSON.stringify({
          user_id: userId,
          order_id: orderId.trim() || null,
          message
        })
      });
      setTicket(created);
      await loadPendingReviews();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create ticket");
    } finally {
      setLoading(false);
    }
  }

  async function runAgent() {
    if (!ticket) return;
    setLoading(true);
    setError(null);

    try {
      const run = await api.request<AgentRun>(`/api/tickets/${ticket.id}/run`, {
        method: "POST"
      });
      const updated = await api.request<Ticket>(`/api/tickets/${ticket.id}`);
      setAgentRun(run);
      setTicket(updated);
      setReviewReply(run.final_reply ?? "");
      await loadPendingReviews();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run agent");
    } finally {
      setLoading(false);
    }
  }

  async function submitReview(action: "approve" | "edit" | "escalate") {
    if (!ticket) return;
    setLoading(true);
    setError(null);

    try {
      const result = await api.request<{ ticket: Ticket }>(
        `/api/reviews/${ticket.id}`,
        {
          method: "POST",
          body: JSON.stringify({
            action,
            final_reply: action === "edit" ? reviewReply : undefined,
            comment: `Reviewed from web demo with action: ${action}`
          })
        }
      );
      setTicket(result.ticket);
      await loadPendingReviews();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Support SOP Agent</p>
          <h1>Ticket workflow demo</h1>
        </div>
        <div className="status-chip">{loading ? "Working" : "Ready"}</div>
      </header>

      <section className="layout">
        <aside className="sidebar">
          <section className="panel">
            <h2>Scenarios</h2>
            <div className="scenario-list">
              {scenarios.map((scenario) => (
                <button
                  className="scenario-button"
                  key={scenario.label}
                  type="button"
                  onClick={() => applyScenario(scenario)}
                >
                  {scenario.label}
                </button>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>Create Ticket</h2>
            <form className="ticket-form" onSubmit={createTicket}>
              <label>
                User ID
                <input value={userId} onChange={(e) => setUserId(e.target.value)} />
              </label>
              <label>
                Order ID
                <input
                  value={orderId}
                  onChange={(e) => setOrderId(e.target.value)}
                  placeholder="Optional"
                />
              </label>
              <label>
                Message
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={5}
                />
              </label>
              <button className="primary" disabled={loading} type="submit">
                Create Ticket
              </button>
            </form>
          </section>
        </aside>

        <section className="workspace">
          {error ? <div className="error-banner">{error}</div> : null}

          <section className="panel action-panel">
            <div>
              <h2>Current Ticket</h2>
              {ticket ? (
                <div className="meta-grid">
                  <Metric label="Ticket" value={ticket.id} />
                  <Metric label="Intent" value={ticket.intent} />
                  <Metric label="Status" value={ticket.status} />
                  <Metric label="Risk" value={ticket.risk_level} />
                </div>
              ) : (
                <p className="muted">Create a ticket to start the workflow.</p>
              )}
            </div>
            <button
              className="primary"
              disabled={!ticket || loading}
              type="button"
              onClick={runAgent}
            >
              Run Agent
            </button>
          </section>

          {agentRun ? (
            <section className="panel">
              <h2>Decision</h2>
              <div className="decision-grid">
                <Metric label="Decision" value={agentRun.decision.decision ?? "-"} />
                <Metric label="Human Review" value={String(agentRun.need_human_review)} />
              </div>
              <p className="reason">{agentRun.decision.reason}</p>
              <ul className="action-list">
                {(agentRun.decision.next_actions ?? []).map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
              <div className="reply-box">{agentRun.final_reply}</div>
            </section>
          ) : null}

          {selectedPendingReview ? (
            <section className="panel review-panel">
              <h2>Human Review</h2>
              <p className="muted">{selectedPendingReview.reason}</p>
              <textarea
                value={reviewReply}
                onChange={(event) => setReviewReply(event.target.value)}
                rows={4}
              />
              <div className="button-row">
                <button type="button" onClick={() => submitReview("approve")}>
                  Approve
                </button>
                <button type="button" onClick={() => submitReview("edit")}>
                  Edit & Resolve
                </button>
                <button type="button" onClick={() => submitReview("escalate")}>
                  Escalate
                </button>
              </div>
            </section>
          ) : null}

          {agentRun ? (
            <section className="panel">
              <h2>Trace</h2>
              <ol className="trace-list">
                {agentRun.trace.map((step) => (
                  <li key={step.node}>
                    <div className="trace-node">{step.node}</div>
                    <pre>{JSON.stringify(step.output, null, 2)}</pre>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          <section className="panel">
            <h2>Pending Reviews</h2>
            {pendingReviews.length ? (
              <ul className="pending-list">
                {pendingReviews.map((item) => (
                  <li key={item.ticket_id}>
                    <strong>{item.ticket_id}</strong>
                    <span>{item.intent}</span>
                    <span>{item.risk_level}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No pending reviews.</p>
            )}
          </section>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

