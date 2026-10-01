
  import { createRoot } from "react-dom/client";
import { ThemeProvider } from "next-themes";
  import App from "./app/App.tsx";
  import { ErrorBoundary } from "./app/components/ErrorBoundary.tsx";
  import "./styles/index.css";

  createRoot(document.getElementById("root")!).render(
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem storageKey="hc-studio-theme" disableTransitionOnChange>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </ThemeProvider>,
  );
  