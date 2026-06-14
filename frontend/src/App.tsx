import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { ChatPage } from "./pages/ChatPage";
import { AgentLogsPage } from "./pages/AgentLogsPage";
import { DocumentListPage } from "./pages/DocumentListPage";
import { EvidenceViewerPage } from "./pages/EvidenceViewerPage";
import { UploadDocumentPage } from "./pages/UploadDocumentPage";

export function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <span className="app-header__title">Document Agent</span>
          <nav className="app-nav" aria-label="Primary navigation">
            <NavLink
              className={({ isActive }) =>
                `app-nav__link${isActive ? " app-nav__link--active" : ""}`
              }
              to="/upload"
            >
              Upload
            </NavLink>
            <NavLink
              className={({ isActive }) =>
                `app-nav__link${isActive ? " app-nav__link--active" : ""}`
              }
              to="/documents"
            >
              Documents
            </NavLink>
            <NavLink
              className={({ isActive }) =>
                `app-nav__link${isActive ? " app-nav__link--active" : ""}`
              }
              to="/chat"
            >
              Chat
            </NavLink>
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<UploadDocumentPage />} />
          <Route path="/documents" element={<DocumentListPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/agent-logs" element={<AgentLogsPage />} />
          <Route
            path="/agent-logs/:agentRunId"
            element={<AgentLogsPage />}
          />
          <Route
            path="/evidence/:agentRunId"
            element={<EvidenceViewerPage />}
          />
          <Route path="*" element={<Navigate to="/upload" replace />} />
        </Routes>
      </main>
    </div>
  );
}
