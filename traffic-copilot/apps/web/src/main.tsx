import React from "react";
import ReactDOM from "react-dom/client";

function App() {
  return (
    <div
      style={{
        fontFamily: "system-ui, -apple-system, sans-serif",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        backgroundColor: "#0f1117",
        color: "#e2e8f0",
        margin: 0,
        padding: "2rem",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          maxWidth: "560px",
          width: "100%",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          gap: "1.5rem",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "9999px",
            padding: "0.375rem 1rem",
            fontSize: "0.75rem",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "#94a3b8",
            alignSelf: "center",
          }}
        >
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: "#22c55e",
              display: "inline-block",
            }}
          />
          Backend API running at :8000
        </div>

        <h1
          style={{
            fontSize: "2.25rem",
            fontWeight: 700,
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
            margin: 0,
          }}
        >
          TrafficCopilot
        </h1>

        <p
          style={{
            fontSize: "1.125rem",
            color: "#94a3b8",
            margin: 0,
            lineHeight: 1.6,
          }}
        >
          Officer-in-the-Loop Incident Co-Pilot. The AI recommends — the human
          decides.
        </p>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
            alignItems: "center",
          }}
        >
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.75rem 1.5rem",
              backgroundColor: "#3b82f6",
              color: "#ffffff",
              borderRadius: "0.5rem",
              textDecoration: "none",
              fontWeight: 600,
              fontSize: "0.9375rem",
              transition: "background-color 0.15s ease",
            }}
            onMouseEnter={(e) =>
              ((e.target as HTMLElement).style.backgroundColor = "#2563eb")
            }
            onMouseLeave={(e) =>
              ((e.target as HTMLElement).style.backgroundColor = "#3b82f6")
            }
          >
            Open API Docs
            <span style={{ fontSize: "1rem" }}>→</span>
          </a>

          <a
            href="http://localhost:8000/health"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.75rem 1.5rem",
              backgroundColor: "transparent",
              color: "#94a3b8",
              border: "1px solid #334155",
              borderRadius: "0.5rem",
              textDecoration: "none",
              fontWeight: 500,
              fontSize: "0.9375rem",
            }}
          >
            Health Check
          </a>
        </div>

        <div
          style={{
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.75rem",
            padding: "1.25rem 1.5rem",
            textAlign: "left",
          }}
        >
          <p
            style={{
              margin: "0 0 0.75rem 0",
              fontSize: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "#64748b",
              fontWeight: 600,
            }}
          >
            Quick Links
          </p>
          <ul
            style={{
              margin: 0,
              padding: 0,
              listStyle: "none",
              display: "flex",
              flexDirection: "column",
              gap: "0.5rem",
            }}
          >
            {[
              { label: "Interactive API Docs (Swagger UI)", href: "http://localhost:8000/docs" },
              { label: "ReDoc API Reference", href: "http://localhost:8000/redoc" },
              { label: "Health / Readiness Probe", href: "http://localhost:8000/health" },
              { label: "Prometheus Metrics", href: "http://localhost:9090" },
              { label: "Grafana Dashboard", href: "http://localhost:3000" },
            ].map(({ label, href }) => (
              <li key={href}>
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: "#60a5fa",
                    textDecoration: "none",
                    fontSize: "0.875rem",
                  }}
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <p style={{ margin: 0, fontSize: "0.75rem", color: "#475569" }}>
          Dashboard UI is not yet implemented. The full backend is live at{" "}
          <code
            style={{
              backgroundColor: "#1e293b",
              padding: "0.125rem 0.375rem",
              borderRadius: "0.25rem",
              fontFamily: "monospace",
            }}
          >
            :8000
          </code>
          .
        </p>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
