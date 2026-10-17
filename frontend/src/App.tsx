import { useEffect, useState } from "react";
import "./App.css";
import { ApplicationHomePage } from "./pages/ApplicationHomePage";
import { HealthCheckPage } from "./pages/HealthCheckPage";

function normalizePathname(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

export function App() {
  const [currentPath, setCurrentPath] = useState<string>(() =>
    normalizePathname(window.location.pathname)
  );

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(normalizePathname(window.location.pathname));
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (targetPath: string) => {
    window.history.pushState({}, "", targetPath);
    setCurrentPath(normalizePathname(targetPath));
  };

  if (currentPath === "/health-check") {
    return <HealthCheckPage />;
  }

  return <ApplicationHomePage onNavigate={navigate} />;
}

export default App;
