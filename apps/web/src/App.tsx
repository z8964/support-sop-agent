import "./styles.css";

const roadmap = [
  "Ticket intake",
  "Intent classification",
  "SOP retrieval",
  "Business tool calling",
  "Human review",
  "Trace and evaluation"
];

export function App() {
  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Support SOP Agent</p>
        <h1>Customer support workflows that follow SOPs, not vibes.</h1>
        <p className="summary">
          A practical business Agent template for ticket intent detection, SOP
          retrieval, tool calling, human review, and execution traces.
        </p>
      </section>

      <section className="panel" aria-labelledby="status-heading">
        <div>
          <h2 id="status-heading">Phase 0 Skeleton</h2>
          <p>
            The repository now has API and web entry points. Next phases will
            add mock tools, ticket CRUD, and the LangGraph workflow.
          </p>
        </div>

        <ul className="roadmap">
          {roadmap.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}

