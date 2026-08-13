import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./auth/AuthProvider.jsx";
import { ThemeProvider } from "./theme/ThemeProvider.jsx";
import { PageTransitionProvider } from "./transitions/PageTransition.jsx";
import "./styles.css";
import "./anime.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          {/* Inside the router: the provider drives navigation itself. */}
          <PageTransitionProvider>
            <App />
          </PageTransitionProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
);
