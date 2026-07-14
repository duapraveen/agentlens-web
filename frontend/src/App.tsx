import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RoleProvider } from "./context/RoleContext";
import { router } from "./router";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RoleProvider>
        <RouterProvider router={router} />
      </RoleProvider>
    </QueryClientProvider>
  );
}
