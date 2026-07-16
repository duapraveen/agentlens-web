import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { DefaultLanding } from "./routes/DefaultLanding";
import { Overview } from "./routes/Overview";
import { Conversations } from "./routes/Conversations";
import { CallDetail } from "./routes/CallDetail";
import { Clusters } from "./routes/Clusters";
import { ReviewQueue } from "./routes/ReviewQueue";
import { FixWorkbench } from "./routes/FixWorkbench";
import { Jobs } from "./routes/Jobs";

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <DefaultLanding /> },
      { path: "/overview", element: <Overview /> },
      { path: "/conversations", element: <Conversations /> },
      { path: "/calls/:callId", element: <CallDetail /> },
      { path: "/clusters", element: <Clusters /> },
      { path: "/review-queue", element: <ReviewQueue /> },
      { path: "/fix-workbench", element: <FixWorkbench /> },
      { path: "/jobs", element: <Jobs /> },
    ],
  },
]);
