import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App.jsx";
import { AuthProvider } from "./auth/AuthProvider.jsx";
import { ThemeProvider } from "./theme/ThemeProvider.jsx";
import { ToastProvider } from "./components/ToastProvider.jsx";
import { PageTransitionProvider } from "./transitions/PageTransition.jsx";
import { queryClient } from "./lib/queryClient.js";
import "./styles.css";
import "./anime.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {/* Outermost: the cache has to outlive every route that reads from it. */}
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        {/* Above the router so a toast survives the navigation that raised it. */}
        <ToastProvider>
          <BrowserRouter>
            <AuthProvider>
              {/* Inside the router: the provider drives navigation itself. */}
              <PageTransitionProvider>
                <App />
              </PageTransitionProvider>
            </AuthProvider>
          </BrowserRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
