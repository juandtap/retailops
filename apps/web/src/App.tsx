import AppLayout from "@/components/layout/app-layout";
import FoundationPage from "@/pages/main/foundation";
import { Route, Routes } from "react-router";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<FoundationPage />} />
        <Route path="*" element={<FoundationPage />} />
      </Route>
    </Routes>
  );
}
